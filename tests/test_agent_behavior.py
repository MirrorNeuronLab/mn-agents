from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools.agent_behavior import (
    SUPPORTED_ROUTING_CONDITIONS,
    SUPPORTED_ROUTING_TARGETS,
    AgentBehaviorError,
    simulate_agent_instance,
    simulate_fixture,
    validate_behavior,
)


AGENTS_ROOT = Path(__file__).resolve().parents[1]
LEGACY_TEMPLATE_IDS = {
    "mn-agents.python_executor",
    "mn-agents.python_workflow",
    "mn-agents.report_aggregator",
    "mn-agents.module_agent",
    "mn-agents.router_agent",
    "mn-agents.stream_tick_source",
    "mn-agents.input_skill_listener",
    "mn-agents.output_skill_fanout",
    "mn-agents.llm_agent",
    "mn-agents.openshell_service",
    "mn-agents.web_ui_output",
}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _indexed_agents() -> list[dict]:
    return _read_json(AGENTS_ROOT / "index.json")["agents"]


def _agent_dir(item: dict) -> Path:
    return AGENTS_ROOT / item["path"]


def test_every_indexed_agent_has_valid_behavior_metadata():
    for item in _indexed_agents():
        agent = _read_json(_agent_dir(item) / "agent.json")
        assert validate_behavior(agent, field=f"{item['path']}/agent.json.behavior") == []


def test_every_indexed_agent_has_template_category():
    for item in _indexed_agents():
        agent = _read_json(_agent_dir(item) / "agent.json")
        assert item["template_category"] in {"control", "data"}
        assert agent["template_category"] == item["template_category"]


def test_legacy_template_ids_are_not_cataloged():
    template_ids = {item["template_id"] for item in _indexed_agents()}
    assert template_ids.isdisjoint(LEGACY_TEMPLATE_IDS)


def test_behavior_validator_reports_missing_required_lists():
    agent = _read_json(AGENTS_ROOT / "data_python_executor" / "agent.json")
    broken = copy.deepcopy(agent)
    broken["behavior"].pop("required_config")
    broken["behavior"]["emits"].pop("events")

    issues = validate_behavior(broken, field="data_python_executor/agent.json.behavior")

    assert {
        "severity": "error",
        "field": "data_python_executor/agent.json.behavior.required_config",
        "message": "must be a list of strings",
    } in issues
    assert {
        "severity": "error",
        "field": "data_python_executor/agent.json.behavior.emits.events",
        "message": "must be a list of strings",
    } in issues


def test_every_minimal_fixture_simulates_successfully():
    for item in _indexed_agents():
        agent_dir = _agent_dir(item)
        agent = _read_json(agent_dir / "agent.json")
        fixture_path = agent_dir / "fixtures" / "minimal.instance.json"

        result = simulate_fixture(fixture_path, AGENTS_ROOT)

        assert result["status"] == "completed"
        assert result["template_id"] == item["template_id"]
        assert result["template_category"] == item["template_category"]
        assert result["version"] == item["version"]
        assert result["rendered_node"]["node_id"] == result["node_id"]
        assert [event["type"] for event in result["events"]] == agent["behavior"]["lifecycle_events"]["success"]
        assert result["messages"], f"{item['path']} should emit at least one simulated message"
        assert result["artifacts"], f"{item['path']} should emit at least one simulated artifact"


def test_required_config_checks_fail_on_broken_fixture_copy():
    fixture = _read_json(AGENTS_ROOT / "data_python_executor" / "fixtures" / "minimal.instance.json")
    broken = copy.deepcopy(fixture)
    broken["config"] = {"command": None}

    with pytest.raises(AgentBehaviorError, match="command"):
        simulate_agent_instance(broken, AGENTS_ROOT)


def test_routing_declarations_use_supported_vocabulary():
    for item in _indexed_agents():
        behavior = _read_json(_agent_dir(item) / "agent.json")["behavior"]
        for transition in behavior.get("routing", {}).get("transitions", []):
            assert transition["when"]["type"] in SUPPORTED_ROUTING_CONDITIONS
            assert transition["then"]["type"] in SUPPORTED_ROUTING_TARGETS


def test_delegation_is_non_recursive_by_default():
    for item in _indexed_agents():
        delegation = _read_json(_agent_dir(item) / "agent.json")["behavior"].get("delegation", {})
        assert delegation.get("allow_recursive") is False


def test_simulate_agent_cli_outputs_json():
    fixture_path = AGENTS_ROOT / "data_python_executor" / "fixtures" / "minimal.instance.json"

    result = subprocess.run(
        [sys.executable, "tools/simulate_agent.py", str(fixture_path)],
        cwd=AGENTS_ROOT,
        check=False,
        capture_output=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["template_id"] == "mn-agents.data_python_executor"
    assert payload["template_category"] == "data"
    assert payload["messages"][0]["message_type"] == "blueprint_report"
    assert [event["type"] for event in payload["events"]] == ["agent_started", "agent_completed"]
