from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

import pytest

from mn_blueprint_support import AgentTemplateError, render_agent_node, validate_agent_library


AGENTS_ROOT = Path(__file__).resolve().parents[1]
LEGACY_TEMPLATE_IDS = {
    "mn-agents.control_approval_gate",
    "mn-agents.control_checkpoint",
    "mn-agents.control_input_listener",
    "mn-agents.control_join",
    "mn-agents.control_lifecycle",
    "mn-agents.control_message_filter",
    "mn-agents.control_output_fanout",
    "mn-agents.control_retry",
    "mn-agents.control_router",
    "mn-agents.control_tick_source",
    "mn-agents.control_web_output",
    "mn-agents.data_edge_model",
    "mn-agents.data_llm_decision",
    "mn-agents.data_llm_tool",
    "mn-agents.data_module",
    "mn-agents.data_observer",
    "mn-agents.data_openshell_service",
    "mn-agents.data_python_executor",
    "mn-agents.data_python_workflow",
    "mn-agents.data_sandboxed_codegen",
}
EXPECTED_TEMPLATE_IDS = {
    "mn-agents.worker.python_host",
    "mn-agents.worker.python_docker",
    "mn-agents.worker.llm_host",
    "mn-agents.control.terminal_sink",
    "mn-agents.control.message_router",
    "mn-agents.module.beam_module",
    "mn-agents.service.openshell",
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

    assert {item["template_id"] for item in _indexed_agents()} == EXPECTED_TEMPLATE_IDS


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
                "uses": "mn-agents.control.terminal_sink@1",
                "with": {
                    "stereotype": "terminal_report_sink",
                },
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
    provenance = rendered["metadata"]["agent_templates"]["rendered"][0]
    assert provenance["template_id"] == "mn-agents.control.terminal_sink"
    assert provenance["stereotype"] == "terminal_report_sink"


def test_stereotype_defaults_merge_before_instance_overrides():
    instance = {
        "node_id": "research",
        "uses": "mn-agents.worker.python_docker@1",
        "with": {
            "stereotype": "public_browser_worker",
            "script": "scripts/run_blueprint.py",
            "upload_path": "document_workflow",
            "docker_worker_image": "document_workflow/docker_worker",
            "image": "mirror-neuron/custom:local",
            "side_effect": "read",
            "environment": {"WEB_BROWSER_TIMEOUT_SECONDS": "99"},
        },
    }

    rendered = render_agent_node(instance, AGENTS_ROOT)

    assert rendered["config"]["side_effect"] == "read"
    assert rendered["config"]["environment"]["W3M_BROWSER_MAX_CHARS"] == "6000"
    assert rendered["config"]["environment"]["WEB_BROWSER_TIMEOUT_SECONDS"] == "99"
    assert "stereotype" not in rendered["config"]


def test_unknown_stereotype_fails_rendering():
    instance = {
        "node_id": "worker",
        "uses": "mn-agents.worker.python_host@1",
        "with": {
            "stereotype": "not_a_real_stereotype",
            "script": "scripts/run_blueprint.py",
            "upload_path": "document_workflow",
        },
    }

    with pytest.raises(AgentTemplateError, match="not_a_real_stereotype"):
        render_agent_node(instance, AGENTS_ROOT)
