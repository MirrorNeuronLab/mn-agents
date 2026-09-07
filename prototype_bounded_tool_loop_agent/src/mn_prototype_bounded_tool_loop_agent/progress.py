"""Checkpointed progress accounting independent of model wording and log volume."""

from __future__ import annotations

import hashlib
import json


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()
    ).hexdigest()


class ProgressGuard:
    def __init__(self, state, *, repeated_errors=3, idle_decisions=12):
        self.state = state.setdefault(
            "progress_guard",
            {
                "processed": 0,
                "idle": 0,
                "last_error": "",
                "error_count": 0,
                "progress": "",
                "seen": [],
                "recovery": None,
            },
        )
        self.repeated_errors = repeated_errors
        self.idle_decisions = idle_decisions

    def observe(self, record, progress=None):
        """Return a transition event. The enclosing checkpoint saves it atomically."""
        state = self.state
        state["processed"] += 1
        result = record.get("result", {})
        error = result.get("error") if isinstance(result, dict) else None
        action = record.get("action", {})
        key = digest(
            {
                "name": action.get("name"),
                "arguments": action.get("arguments"),
                "result": result,
            }
        )
        if progress is not None:
            current = digest(progress)
            advanced = not error and current != state["progress"]
            state["progress"] = current
        else:
            advanced = not error and bool(result) and key not in state["seen"]
        if advanced:
            state["seen"].append(key)
            state["seen"] = state["seen"][-512:]
        state["idle"] = 0 if advanced else state["idle"] + 1
        state["error_count"] = (
            state["error_count"] + 1
            if error and key == state["last_error"]
            else int(bool(error))
        )
        state["last_error"] = key if error else ""
        recovery = state["recovery"]
        if recovery:
            recovered = advanced or (
                recovery["kind"] == "repeated_invalid_action" and not error
            )
            if recovered:
                state["recovery"] = None
                state["error_count"] = 0
                return {"type": "agent_recovery_completed", "reason": recovery["kind"]}
            recovery["remaining"] -= 1
            if recovery["remaining"] <= 0:
                return {"type": "agent_stalled", "reason": recovery["kind"]}
        elif (
            state["error_count"] >= self.repeated_errors
            or state["idle"] >= self.idle_decisions
        ):
            kind = (
                "repeated_invalid_action"
                if state["error_count"] >= self.repeated_errors
                else "no_substantive_progress"
            )
            state["recovery"] = {
                "kind": kind,
                "remaining": 1 if kind == "repeated_invalid_action" else 2,
                "instruction": "Use only currently allowed actions. Correct the latest error; do not repeat rejected actions. Collect new information or explicitly report inability to proceed.",
            }
            return {"type": "agent_recovery_started", "reason": kind}
        return None
