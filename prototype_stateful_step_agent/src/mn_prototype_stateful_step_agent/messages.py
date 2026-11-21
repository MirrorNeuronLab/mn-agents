"""Adapt domain operations to routed, idempotent message handlers."""

from __future__ import annotations

from typing import Any, Mapping

from mn_sdk.step_runtime import (
    AgentInput,
    StepContext,
    StepResult,
    receive_input,
    send_output,
)

from .contracts import (
    AgentHandlerOutput,
    DomainHandler,
    DomainOperationSpec,
    MessageAgentSpec,
    StatefulStepContext,
)
from .steps import create_agent


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
            result.get("result") if isinstance(result.get("result"), dict) else result
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


def create_domain_message_agent(spec: DomainOperationSpec) -> DomainHandler:
    """Create a message agent around an injected, domain-owned operation."""

    def invoke(
        context: StatefulStepContext,
        *,
        agent_input: AgentInput,
        llm_client: Any | None = None,
        **options: Any,
    ) -> AgentHandlerOutput | Mapping[str, Any]:
        try:
            result = spec.operation(
                context,
                agent_input=agent_input,
                llm_client=llm_client,
                **options,
            )
        except BaseException as exc:
            if spec.on_error is not None:
                spec.on_error(
                    context,
                    error=exc,
                    agent_input=agent_input,
                    llm_client=llm_client,
                    **options,
                )
            raise
        if spec.result_adapter is not None:
            return spec.result_adapter(
                context,
                result=result,
                agent_input=agent_input,
                llm_client=llm_client,
                **options,
            )
        return _normalize_agent_handler_output(result)

    return create_message_agent(
        MessageAgentSpec(
            stateful=spec.stateful,
            input_resolver=spec.input_resolver,
            idempotency_state_dir=spec.idempotency_state_dir,
            include_default_artifacts=spec.include_default_artifacts,
        ),
        invoke,
    )


def require_child_step_input(
    agent_input: AgentInput, *, marker: str = "_child"
) -> dict[str, Any]:
    """Return validated Core-owned child step input from a route-neutral message."""

    step_input = agent_input.payload.get("step_input")
    if not isinstance(step_input, Mapping):
        raise ValueError("child workflow message requires a step_input object")
    child = step_input.get(marker)
    if not isinstance(child, Mapping):
        raise ValueError(f"child workflow step_input requires a {marker} object")
    return dict(step_input)


def _normalize_agent_handler_output(value: Any) -> AgentHandlerOutput:
    if isinstance(value, AgentHandlerOutput):
        return value
    if isinstance(value, Mapping):
        return AgentHandlerOutput(payload=dict(value))
    raise TypeError("message agent handler must return AgentHandlerOutput or a mapping")
