from __future__ import annotations

import json
from importlib.resources import files
from typing import Any


AGENT_ID = "mn-agents.control.terminal_sink"
AGENT_VERSION = 1


def load_agent_definition() -> dict[str, Any]:
    return json.loads(files(__package__).joinpath("resources/agent.json").read_text(encoding="utf-8"))
