from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib.resources import files
from typing import Any, Callable, Mapping


AGENT_ID = "mn-agents.prototype.bounded_tool_loop"
AGENT_VERSION = 1


@dataclass(frozen=True)
class ToolAction:
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    kind: str = "tool"


@dataclass(frozen=True)
class ToolObservation:
    name: str
    value: Any = None
    error: str = ""


@dataclass(frozen=True)
class ToolLoopResult:
    trace: tuple[dict[str, Any], ...]
    stop_reason: str
    iterations: int
    tool_calls: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "completed",
            "trace": list(self.trace),
            "stop_reason": self.stop_reason,
            "iterations": self.iterations,
            "tool_calls": self.tool_calls,
        }


@dataclass(frozen=True)
class ToolLoopSpec:
    propose_action: Callable[..., ToolAction | None]
    execute_action: Callable[..., Any]
    observe_result: Callable[..., ToolObservation | Any] | None = None
    validate_action: Callable[..., bool] | None = None
    max_iterations: int = 8
    max_tool_calls: int = 16
    partial_on_limit: bool = True


def load_agent_definition() -> dict[str, Any]:
    return json.loads(files(__package__).joinpath("resources/agent.json").read_text(encoding="utf-8"))


def create_agent(spec: ToolLoopSpec) -> Callable[..., dict[str, Any]]:
    if spec.max_iterations < 1 or spec.max_tool_calls < 1:
        raise ValueError("bounded tool loop limits must be positive")

    def run(context: Any, **options: Any) -> dict[str, Any]:
        trace: list[dict[str, Any]] = []
        tool_calls = 0
        for iteration in range(1, spec.max_iterations + 1):
            action = spec.propose_action(context, trace, **options)
            if action is None:
                return ToolLoopResult(tuple(trace), "completed", iteration - 1, tool_calls).to_dict()
            if not isinstance(action, ToolAction):
                raise TypeError("propose_action must return ToolAction or None")
            if action.kind == "final":
                trace.append({"iteration": iteration, "action": action.name, "kind": "final"})
                return ToolLoopResult(tuple(trace), "completed", iteration, tool_calls).to_dict()
            if spec.validate_action is not None and not spec.validate_action(context, action, **options):
                raise ValueError(f"tool action is not allowed: {action.name}")
            if tool_calls >= spec.max_tool_calls:
                reason = "tool_call_budget_exhausted"
                if not spec.partial_on_limit:
                    raise RuntimeError(reason)
                return ToolLoopResult(tuple(trace), reason, iteration - 1, tool_calls).to_dict()
            record: dict[str, Any] = {"iteration": iteration, "action": action.name, "arguments": dict(action.arguments)}
            try:
                value = spec.execute_action(context, action, **options)
                observation = spec.observe_result(context, action, value, **options) if spec.observe_result else ToolObservation(action.name, value=value)
                if isinstance(observation, ToolObservation):
                    record["observation"] = {"name": observation.name, "value": observation.value, "error": observation.error}
                else:
                    record["observation"] = observation
            except Exception as exc:
                record["error"] = str(exc)
                trace.append(record)
                raise
            trace.append(record)
            tool_calls += 1
        reason = "iteration_limit_exhausted"
        if not spec.partial_on_limit:
            raise RuntimeError(reason)
        return ToolLoopResult(tuple(trace), reason, spec.max_iterations, tool_calls).to_dict()

    run.__name__ = "run"
    return run


__all__ = [
    "AGENT_ID",
    "AGENT_VERSION",
    "ToolAction",
    "ToolLoopResult",
    "ToolLoopSpec",
    "ToolObservation",
    "create_agent",
    "load_agent_definition",
]
