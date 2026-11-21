"""Stateful step agent metadata and public factory API."""

from __future__ import annotations

import json
from importlib import import_module
from importlib.resources import files
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .contracts import (
        AgentHandlerOutput as AgentHandlerOutput,
        DomainErrorHook as DomainErrorHook,
        DomainHandler as DomainHandler,
        DomainOperationSpec as DomainOperationSpec,
        DomainResultAdapter as DomainResultAdapter,
        FinalizeHook as FinalizeHook,
        MessageAgentSpec as MessageAgentSpec,
        MessageInputResolver as MessageInputResolver,
        PrepareHook as PrepareHook,
        RuntimeFactory as RuntimeFactory,
        StatefulStepContext as StatefulStepContext,
        StatefulStepSpec as StatefulStepSpec,
    )
    from .messages import (
        create_domain_message_agent as create_domain_message_agent,
        create_message_agent as create_message_agent,
        require_child_step_input as require_child_step_input,
    )
    from .steps import (
        create_agent as create_agent,
    )


AGENT_ID = "mn-agents.prototype.stateful_step"

AGENT_VERSION = 1


def load_agent_definition() -> dict[str, Any]:
    return json.loads(
        files(__package__).joinpath("resources/agent.json").read_text(encoding="utf-8")
    )


__all__ = [
    "AGENT_ID",
    "AGENT_VERSION",
    "AgentHandlerOutput",
    "DomainOperationSpec",
    "MessageAgentSpec",
    "StatefulStepContext",
    "StatefulStepSpec",
    "create_agent",
    "create_domain_message_agent",
    "create_message_agent",
    "load_agent_definition",
    "require_child_step_input",
]


_MODULES = {
    "RuntimeFactory": "contracts",
    "DomainHandler": "contracts",
    "PrepareHook": "contracts",
    "FinalizeHook": "contracts",
    "MessageInputResolver": "contracts",
    "DomainResultAdapter": "contracts",
    "DomainErrorHook": "contracts",
    "StatefulStepContext": "contracts",
    "StatefulStepSpec": "contracts",
    "AgentHandlerOutput": "contracts",
    "MessageAgentSpec": "contracts",
    "DomainOperationSpec": "contracts",
    "create_agent": "steps",
    "create_message_agent": "messages",
    "create_domain_message_agent": "messages",
    "require_child_step_input": "messages",
}


def __getattr__(name: str):
    """Load execution types only when a caller requests them."""
    if name not in _MODULES:
        raise AttributeError(name)
    value = getattr(import_module(f".{_MODULES[name]}", __name__), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | _MODULES.keys())
