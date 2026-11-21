"""State, message and callback contracts for stateful agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from mn_sdk.blueprint_support import (
    StepLifecycleHooks,
    WorkflowStateStore,
)
from mn_sdk.step_runtime import (
    AgentInput,
    StepContext,
)

RuntimeFactory = Callable[..., Mapping[str, Any] | Any]


DomainHandler = Callable[..., Any]


PrepareHook = Callable[..., Mapping[str, Any] | None]


FinalizeHook = Callable[..., Any]


MessageInputResolver = Callable[[AgentInput], Mapping[str, Any] | None]


DomainResultAdapter = Callable[..., "AgentHandlerOutput | Mapping[str, Any]"]


DomainErrorHook = Callable[..., Any]


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


@dataclass(frozen=True)
class DomainOperationSpec:
    """Bind one injected domain operation to the standard message lifecycle."""

    stateful: StatefulStepSpec
    operation: DomainHandler
    input_resolver: MessageInputResolver | None = None
    result_adapter: DomainResultAdapter | None = None
    on_error: DomainErrorHook | None = None
    idempotency_state_dir: str = "agent_invocations"
    include_default_artifacts: bool = True
