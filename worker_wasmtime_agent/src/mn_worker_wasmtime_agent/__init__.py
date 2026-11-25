from __future__ import annotations

import copy
from typing import Any

from mn_sdk.blueprint_support import render_agent_node_from_definition

from .definition import AGENT_ID, AGENT_VERSION, load_agent_definition


def create_agent(instance: dict[str, Any] | None = None) -> dict[str, Any]:
    definition = load_agent_definition()
    if instance is None:
        return copy.deepcopy(definition)
    return render_agent_node_from_definition(instance, definition)


__all__ = ["AGENT_ID", "AGENT_VERSION", "create_agent", "load_agent_definition"]
