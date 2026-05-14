from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from mn_blueprint_support import render_agent_node, validate_agent_library


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


def _agent_index() -> dict:
    return _read_json(AGENTS_ROOT / "index.json")


def _indexed_agents() -> list[dict]:
    return _agent_index()["agents"]


def test_index_entries_are_unique_and_paths_match_agent_files():
    seen: set[tuple[str, str]] = set()

    for item in _indexed_agents():
        key = (item["template_id"], item["version"])
        assert key not in seen
        seen.add(key)

        agent_dir = AGENTS_ROOT / item["path"]
        agent = _read_json(agent_dir / "agent.json")
        assert agent_dir.is_dir()
        assert not Path(item["path"]).is_absolute()
        assert ".." not in Path(item["path"]).parts
        assert agent["template_id"] == item["template_id"]
        assert agent["template_id"] not in LEGACY_TEMPLATE_IDS
        assert agent["version"] == item["version"]
        assert agent["kind"] == item["kind"]
        assert agent["template_category"] == item["template_category"]
        assert item["template_category"] in {"control", "data"}
        assert agent["behavior"]["schema_version"] == "mn.agent.behavior.v1"


def test_agent_templates_match_schema():
    schema = _read_json(AGENTS_ROOT / "schemas" / "agent.template.schema.json")
    validator = Draft202012Validator(schema)

    for item in _indexed_agents():
        agent_path = AGENTS_ROOT / item["path"] / "agent.json"
        errors = sorted(validator.iter_errors(_read_json(agent_path)), key=lambda error: list(error.path))
        assert errors == [], f"{agent_path}: {[error.message for error in errors]}"


def test_agent_fixture_instances_match_schema():
    schema = _read_json(AGENTS_ROOT / "schemas" / "agent.instance.schema.json")
    validator = Draft202012Validator(schema)

    for item in _indexed_agents():
        fixture_path = AGENTS_ROOT / item["path"] / "fixtures" / "minimal.instance.json"
        errors = sorted(validator.iter_errors(_read_json(fixture_path)), key=lambda error: list(error.path))
        assert errors == [], f"{fixture_path}: {[error.message for error in errors]}"


def test_agent_library_validator_passes_for_catalog():
    assert validate_agent_library(AGENTS_ROOT) == []


def test_every_agent_fixture_renders_to_expected_node():
    for item in _indexed_agents():
        agent_dir = AGENTS_ROOT / item["path"]
        fixture = _read_json(agent_dir / "fixtures" / "minimal.instance.json")
        expected = _read_json(agent_dir / "fixtures" / "rendered.node.json")

        assert render_agent_node(fixture, AGENTS_ROOT) == expected


def test_validate_agents_cli_outputs_json_without_issues():
    result = subprocess.run(
        [sys.executable, "tools/validate_agents.py", "--json"],
        cwd=AGENTS_ROOT,
        check=False,
        capture_output=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert json.loads(result.stdout) == {"issues": []}


def test_render_agent_templates_cli_expands_manifest(tmp_path: Path):
    manifest = {
        "metadata": {"name": "unit"},
        "nodes": [
            {
                "node_id": "report_sink",
                "uses": "mn-agents.control_join@1.0.0",
                "with": {"complete_on_message": True},
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "tools/render_agent_templates.py", str(manifest_path)],
        cwd=AGENTS_ROOT,
        check=False,
        capture_output=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    rendered = json.loads(result.stdout)
    assert rendered["nodes"][0]["node_id"] == "report_sink"
    assert rendered["nodes"][0]["agent_type"] == "aggregator"
    assert "uses" not in rendered["nodes"][0]
    assert rendered["metadata"]["agent_templates"]["rendered"][0]["template_id"] == "mn-agents.control_join"
