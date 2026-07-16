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
from mn_sdk.step_runtime import (
    AgentInput,
    StepContext,
    StepResult,
    find_message_payload,
    receive_input,
    send_output,
)


AGENT_ID = "mn-agents.prototype.stateful_step"
AGENT_VERSION = 1
RuntimeFactory = Callable[..., Mapping[str, Any] | Any]
DomainHandler = Callable[..., Any]
PrepareHook = Callable[..., Mapping[str, Any] | None]
FinalizeHook = Callable[..., Any]
MessageInputResolver = Callable[[AgentInput], Mapping[str, Any] | None]


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


@dataclass(frozen=True)
class AgentHandlerOutput:
    """Route-neutral result returned by a domain handler.

    Mapping results remain accepted as a convenience and are treated as the
    payload with no additional artifacts or metrics.
    """

    payload: Mapping[str, Any]
    artifacts: tuple[Mapping[str, Any], ...] = ()
    metrics: Mapping[str, Any] = field(default_factory=dict)
    status: str = "completed"


@dataclass(frozen=True)
class MessageAgentSpec:
    """Message/replay policy layered around a :class:`StatefulStepSpec`."""

    stateful: StatefulStepSpec
    input_resolver: MessageInputResolver | None = None
    idempotency_state_dir: str = "agent_invocations"
    include_default_artifacts: bool = True


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


def create_message_agent(
    spec: MessageAgentSpec,
    handler: DomainHandler | None = None,
) -> DomainHandler:
    """Create a route-neutral, idempotent message-driven agent handler.

    Durable replay state is written before the result is returned to the SDK,
    so the outer Redis delivery may ACK only after the handler output and its
    idempotency record are available.
    """

    if handler is None:
        raise TypeError("message agent handler is required")

    def run(step_context: StepContext, **parameters: Any) -> StepResult:
        agent_input = receive_input(step_context)
        resolved_inputs = (
            spec.input_resolver(agent_input)
            if spec.input_resolver is not None
            else None
        )

        def invoke(
            context: StatefulStepContext,
            *,
            llm_client: Any | None = None,
            **options: Any,
        ) -> dict[str, Any]:
            invocation_id = (
                step_context.invocation_id
                or f"{step_context.step_id}__{step_context.agent_id}"
            )
            marker_name = (
                f"{spec.idempotency_state_dir.strip('/')}/{invocation_id}.json"
            )
            cached = context.state_store.read(marker_name, {})
            if (
                agent_input.idempotency_key
                and isinstance(cached, dict)
                and cached.get("idempotency_key") == agent_input.idempotency_key
                and isinstance(cached.get("result"), dict)
            ):
                return dict(cached["result"])

            raw = handler(
                context,
                llm_client=llm_client,
                agent_input=agent_input,
                **options,
            )
            output = _normalize_agent_handler_output(raw)
            serialized = {
                "payload": dict(output.payload),
                "artifacts": [dict(item) for item in output.artifacts],
                "metrics": dict(output.metrics),
                "status": output.status,
            }
            context.state_store.write(f"{invocation_id}_result.json", serialized)
            context.state_store.write(
                marker_name,
                {
                    "agent_id": step_context.agent_id,
                    "invocation_id": invocation_id,
                    "idempotency_key": agent_input.idempotency_key,
                    "result": serialized,
                    "status": "completed",
                },
            )
            return serialized

        managed_handler = create_agent(spec.stateful, invoke)
        result = managed_handler(
            step_context,
            inputs=dict(resolved_inputs or {}) if resolved_inputs is not None else None,
            **parameters,
        )
        serialized = (
            result.get("result")
            if isinstance(result.get("result"), dict)
            else result
        )
        payload = serialized.get("payload")
        if not isinstance(payload, Mapping):
            payload = serialized.get("outputs")
        if not isinstance(payload, Mapping):
            payload = {}
        artifacts = [
            dict(item)
            for item in serialized.get("artifacts", [])
            if isinstance(item, Mapping)
        ]
        invocation_id = (
            step_context.invocation_id
            or f"{step_context.step_id}__{step_context.agent_id}"
        )
        if spec.include_default_artifacts:
            artifacts.extend(
                [
                    {
                        "kind": "agent_result",
                        "path": f"workflow_state/{invocation_id}_result.json",
                        "invocation_id": invocation_id,
                    },
                    {
                        "kind": "agent_idempotency_record",
                        "path": (
                            "workflow_state/"
                            f"{spec.idempotency_state_dir.strip('/')}/"
                            f"{invocation_id}.json"
                        ),
                        "invocation_id": invocation_id,
                    },
                ]
            )
        return send_output(
            payload,
            artifacts=artifacts,
            metrics=(
                serialized.get("metrics")
                if isinstance(serialized.get("metrics"), Mapping)
                else None
            ),
            status=str(serialized.get("status") or "completed"),
        )

    run.__name__ = "run"
    return run


def _normalize_agent_handler_output(value: Any) -> AgentHandlerOutput:
    if isinstance(value, AgentHandlerOutput):
        return value
    if isinstance(value, Mapping):
        return AgentHandlerOutput(payload=dict(value))
    raise TypeError(
        "message agent handler must return AgentHandlerOutput or a mapping"
    )


__all__ = [
    "AGENT_ID",
    "AGENT_VERSION",
    "AgentHandlerOutput",
    "MessageAgentSpec",
    "StatefulStepContext",
    "StatefulStepSpec",
    "create_agent",
    "create_message_agent",
    "load_agent_definition",
]
