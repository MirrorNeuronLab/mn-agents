from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Any, Callable, Mapping

from mn_sdk.blueprint_support import (
    StepLifecycleHooks,
    WorkflowStateStore,
    execute_step_handler,
)
from mn_sdk.step_runtime import StepContext, find_message_payload


AGENT_ID = "mn-agents.prototype.stateful_step"
AGENT_VERSION = 1
RuntimeFactory = Callable[..., Mapping[str, Any] | Any]
DomainHandler = Callable[..., Any]
PrepareHook = Callable[..., Mapping[str, Any] | None]
FinalizeHook = Callable[..., Any]


@dataclass
class StatefulStepContext:
    step_context: StepContext
    runtime_context: Mapping[str, Any]
    state_store: WorkflowStateStore
    state: Any = None
    inputs: dict[str, Any] = field(default_factory=dict)
    services: dict[str, Any] = field(default_factory=dict)
    llm_client: Any | None = None

    def __getitem__(self, key: str) -> Any:
        if key == "state":
            return self.state
        if key == "state_store":
            return self.state_store
        if key == "inputs":
            return self.inputs
        if key == "services":
            return self.services
        return self.runtime_context[key]

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except (KeyError, TypeError):
            return default

    @property
    def config(self) -> Mapping[str, Any]:
        return self.runtime_context.get("config", {})

    @property
    def run_id(self) -> str:
        return str(self.runtime_context.get("run_id") or self.step_context.run_id)

    def to_mapping(self) -> dict[str, Any]:
        return {
            **dict(self.runtime_context),
            "state": self.state,
            "state_store": self.state_store,
            "inputs": self.inputs,
            "services": self.services,
        }


@dataclass(frozen=True)
class StatefulStepSpec:
    context_factory: RuntimeFactory
    input_keys: frozenset[str] = frozenset()
    state_name: str | None = None
    state_default: Any = field(default_factory=dict)
    hooks: StepLifecycleHooks = field(default_factory=StepLifecycleHooks)
    prepare: PrepareHook | None = None
    finalize: FinalizeHook | None = None


def load_agent_definition() -> dict[str, Any]:
    return json.loads(
        files(__package__).joinpath("resources/agent.json").read_text(encoding="utf-8")
    )


def create_agent(
    spec: StatefulStepSpec, handler: DomainHandler | None = None
) -> DomainHandler:
    if handler is None:
        raise TypeError("stateful step handler is required")

    def run(step_context: StepContext, **parameters: Any) -> dict[str, Any]:
        inputs = parameters.pop("inputs", None)
        runs_root = parameters.pop("runs_root", None)
        llm_client = parameters.pop("llm_client", None)
        if not isinstance(inputs, dict):
            inputs = find_message_payload(
                step_context.message, required_keys=spec.input_keys
            )
        config = step_context.config or None
        selected_step_id = step_context.invocation_id or step_context.step_id
        bound_parameters = dict(parameters)

        def build_context(
            *,
            inputs: dict[str, Any] | None = None,
            config: dict[str, Any] | None = None,
            runs_root: Any = None,
            run_id: str | None = None,
        ) -> Mapping[str, Any] | Any:
            return spec.context_factory(
                inputs=inputs or {},
                config=config,
                runs_root=runs_root,
                run_id=run_id,
            )

        def invoke(
            runtime_context: Mapping[str, Any] | Any,
            *,
            llm_client: Any | None = None,
            **options: Any,
        ) -> Any:
            mapping = (
                runtime_context.to_mapping()
                if hasattr(runtime_context, "to_mapping")
                else dict(runtime_context)
            )
            run_dir = Path(mapping["run_dir"])
            store = WorkflowStateStore(run_dir)
            state = (
                store.read(spec.state_name, spec.state_default)
                if spec.state_name
                else None
            )
            managed = StatefulStepContext(
                step_context=step_context,
                runtime_context=mapping,
                state_store=store,
                state=state,
                inputs=dict(inputs or {}),
                llm_client=llm_client,
            )
            call_options = {**bound_parameters, **options}
            result: Any = None
            error: BaseException | None = None
            try:
                if spec.prepare is not None:
                    prepared = spec.prepare(
                        managed, llm_client=llm_client, **call_options
                    )
                    if prepared is not None:
                        if not isinstance(prepared, Mapping):
                            raise TypeError(
                                "stateful step prepare hook must return a mapping or None"
                            )
                        managed.services.update(dict(prepared))
                result = handler(managed, llm_client=llm_client, **call_options)
                if spec.state_name and managed.state is not None:
                    store.write(spec.state_name, managed.state)
                return result
            except BaseException as exc:
                error = exc
                raise
            finally:
                if spec.finalize is not None:
                    spec.finalize(
                        managed,
                        result=result,
                        error=error,
                        llm_client=llm_client,
                        **call_options,
                    )

        return execute_step_handler(
            selected_step_id,
            invoke,
            context_factory=build_context,
            inputs=inputs,
            config=config,
            runs_root=runs_root,
            run_id=step_context.run_id or None,
            llm_client=llm_client,
            hooks=spec.hooks,
        )

    run.__name__ = "run"
    return run


__all__ = [
    "AGENT_ID",
    "AGENT_VERSION",
    "StatefulStepContext",
    "StatefulStepSpec",
    "create_agent",
    "load_agent_definition",
]
