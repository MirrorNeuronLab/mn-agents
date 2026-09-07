"""Durable one-action-at-a-time composition over the bounded tool loop."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
import hashlib
import json
from pathlib import Path
import signal
import threading
import time

from . import ToolAction, ToolLoopSpec, ToolPlan, create_agent
from .progress import ProgressGuard


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False)
        stream.flush()
        import os

        os.fsync(stream.fileno())
    temporary.replace(path)


class DeadlineExceeded(TimeoutError):
    pass


@contextmanager
def deadline(seconds):
    """POSIX workers enforce deadlines even during blocking model/tool calls."""
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError(
            "durable loop requires the worker main thread for deadline enforcement"
        )
    previous = signal.getsignal(signal.SIGALRM)

    def expired(*_):
        raise DeadlineExceeded("time_budget_exhausted")

    signal.signal(signal.SIGALRM, expired)
    old_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, *old_timer)
        signal.signal(signal.SIGALRM, previous)


class CheckpointLoop:
    """Persist decisions before dispatch and observations before another model call.

    Only completed observations are replayed. An interrupted in-flight operation
    can execute again; callers must use read-only or idempotent handlers.
    """

    def __init__(
        self,
        path,
        binding,
        *,
        max_decisions=40,
        max_invocations=24,
        seconds=600,
        finalization_decisions=0,
    ):
        if any(type(v) is not int or v <= 0 for v in (max_decisions, max_invocations)):
            raise ValueError("loop budgets must be positive integers")
        if seconds is not None and (type(seconds) is not int or seconds <= 0):
            raise ValueError("seconds must be a positive integer or None")
        self.path = Path(path)
        if (
            type(finalization_decisions) is not int
            or not 0 <= finalization_decisions <= max_decisions
        ):
            raise ValueError("invalid finalization reserve")
        self.limits = dict(
            max_decisions=max_decisions,
            max_invocations=max_invocations,
            seconds=seconds,
            finalization_decisions=finalization_decisions,
        )
        if not finalization_decisions:
            self.limits.pop("finalization_decisions")
        identity = fingerprint({"binding": binding, "limits": self.limits, "progress_policy": 1})
        self.state = (
            json.loads(self.path.read_text())
            if self.path.exists()
            else {
                "binding": identity,
                "records": [],
                "elapsed": 0.0,
                "stop_reason": "",
                "data": {},
            }
        )
        if self.state["binding"] != identity:
            raise ValueError(
                "checkpoint binding mismatch: evidence or execution configuration changed"
            )
        self.save()

    def save(self):
        clock = getattr(self, "_clock", None)
        if clock is not None:
            self.state["elapsed"] = clock[1] + time.monotonic() - clock[0]
        atomic_json(self.path, self.state)

    def run(self, propose, execute, *, cancelled=lambda: False, allowed_actions=None, progress=None, event_sink=None):
        if self.state["stop_reason"]:
            return self.state
        guard = ProgressGuard(self.state)
        if progress is not None and not guard.state["progress"]:
            from .progress import digest
            guard.state["progress"] = digest(progress(self.state))

        def observe_progress(record):
            event = guard.observe(record, progress(self.state) if progress else None)
            if event and event["type"] == "agent_stalled" and not self.state["stop_reason"]:
                self.state["stop_reason"] = "investigation_stalled"
            self.save()
            if event and event_sink:
                event_sink(event)

        started = time.monotonic()
        self._clock = (started, self.state["elapsed"])
        remaining_seconds = (
            self.limits["seconds"] - self.state["elapsed"]
            if self.limits["seconds"] is not None
            else None
        )

        def next_action(_context, _trace):
            if cancelled():
                return ToolPlan(stop_reason="cancelled")
            records = self.state["records"]
            if records and "result" not in records[-1]:
                return ToolAction("dispatch", {"index": len(records) - 1})
            if len(records) >= self.limits["max_decisions"]:
                return ToolPlan(stop_reason="iteration_limit_exhausted")
            if (
                sum(r["action"].get("name") == "invoke_skill" for r in records)
                >= self.limits["max_invocations"]
            ):
                reserve = self.limits.get("finalization_decisions", 0)
                if not reserve:
                    return ToolPlan(stop_reason="tool_call_budget_exhausted")
                start = self.state.setdefault("finalization_started", len(records))
                if len(records) - start >= reserve:
                    return ToolPlan(stop_reason="tool_call_budget_exhausted")
            try:
                action = propose(self.state)
                if not isinstance(action, dict) or set(action) != {
                    "name",
                    "arguments",
                    "reason",
                }:
                    raise ValueError("action requires name, arguments, reason")
                if (
                    not isinstance(action["name"], str)
                    or not isinstance(action["arguments"], dict)
                    or not isinstance(action["reason"], str)
                    or not action["reason"].strip()
                ):
                    raise ValueError("invalid action fields")
                if len(json.dumps(action)) > 32000:
                    raise ValueError("model action exceeds byte limit")
            except DeadlineExceeded:
                raise
            except (ValueError, TypeError) as exc:
                records.append(
                    {
                        "action": {"name": "invalid_response"},
                        "result": {"error": str(exc)[:1000]},
                    }
                )
                observe_progress(records[-1])
                return ToolAction("noop")
            records.append({"action": action})
            self.save()
            return ToolAction("dispatch", {"index": len(records) - 1})

        def dispatch(_context, action):
            if action.name == "noop":
                return None
            record = self.state["records"][action.arguments["index"]]
            try:
                if allowed_actions is not None and record["action"]["name"] not in allowed_actions(self.state):
                    raise ValueError("action unavailable in current phase; choose from allowed_actions")
                if (
                    record["action"]["name"] == "invoke_skill"
                    and sum(
                        r["action"].get("name") == "invoke_skill"
                        for r in self.state["records"][:-1]
                    )
                    >= self.limits["max_invocations"]
                ):
                    raise ValueError(
                        "tool budget exhausted; only finalization actions remain"
                    )
                record["result"] = execute(record["action"], self.state)
            except DeadlineExceeded:
                raise
            except Exception as exc:
                record["result"] = {"error": str(exc)[:1000]}
            if record["action"]["name"] == "finish" and "error" not in record["result"]:
                self.state["stop_reason"] = "completed"
            observe_progress(record)
            return record["result"]

        def planner(context, trace):
            if self.state["stop_reason"]:
                return ToolPlan(stop_reason=self.state["stop_reason"])
            return next_action(context, trace)

        try:
            if remaining_seconds is not None and remaining_seconds <= 0:
                raise DeadlineExceeded()
            with (
                deadline(remaining_seconds)
                if remaining_seconds is not None
                else nullcontext()
            ):
                result = create_agent(
                    ToolLoopSpec(
                        planner,
                        dispatch,
                        max_iterations=self.limits["max_decisions"] + 1,
                        max_tool_calls=self.limits["max_decisions"] + 1,
                    )
                )({})
                self.state["stop_reason"] = result["stop_reason"]
        except DeadlineExceeded:
            self.state["stop_reason"] = "time_budget_exhausted"
        finally:
            self.save()
            self._clock = None
        return self.state
