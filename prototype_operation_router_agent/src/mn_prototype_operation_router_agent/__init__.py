from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from importlib.resources import files
from typing import Any, Callable, Mapping


AGENT_ID = "mn-agents.prototype.operation_router"
AGENT_VERSION = 1
Handler = Callable[..., Any]


@dataclass(frozen=True)
class OperationBinding:
    handler: Handler
    bound_kwargs: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OperationRouterSpec:
    operations: Mapping[str, Handler | OperationBinding]
    selector: str = "operation"
    label: str = "operation"


def load_agent_definition() -> dict[str, Any]:
    return json.loads(files(__package__).joinpath("resources/agent.json").read_text(encoding="utf-8"))


def create_agent(spec: OperationRouterSpec | Mapping[str, Handler | OperationBinding], **options: Any) -> Handler:
    if isinstance(spec, OperationRouterSpec):
        resolved = spec
    else:
        resolved = OperationRouterSpec(
            operations=spec,
            selector=str(options.pop("selector", "operation")),
            label=str(options.pop("label", "operation")),
        )
    operations = {}
    for name, binding in resolved.operations.items():
        operation = str(name).strip()
        if not operation:
            raise ValueError("operation names must not be empty")
        selected = binding if isinstance(binding, OperationBinding) else OperationBinding(binding)
        if not callable(selected.handler):
            raise TypeError(f"operation {operation!r} handler must be callable")
        operations[operation] = selected

    def run(context: Any, **parameters: Any) -> Any:
        selected_name = parameters.pop(resolved.selector, None)
        if selected_name is None and isinstance(context, Mapping):
            selected_name = context.get(resolved.selector)
        if selected_name is None:
            selected_name = getattr(context, resolved.selector, None)
        selected_key = str(selected_name or "").strip()
        binding = operations.get(selected_key)
        if binding is None:
            available = ", ".join(sorted(operations))
            raise ValueError(f"unknown {resolved.label} {selected_key!r}; expected one of: {available}")
        call_kwargs = {**dict(binding.bound_kwargs), **parameters}
        return binding.handler(context, **call_kwargs)

    run.__name__ = "run"
    run.__doc__ = f"Dispatch a {resolved.label} to a configured strategy."
    return run


__all__ = [
    "AGENT_ID",
    "AGENT_VERSION",
    "OperationBinding",
    "OperationRouterSpec",
    "create_agent",
    "load_agent_definition",
]
