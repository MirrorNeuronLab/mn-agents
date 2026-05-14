from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from mn_blueprint_support import load_agent_template, parse_agent_ref, render_agent_node


BEHAVIOR_SCHEMA_VERSION = "mn.agent.behavior.v1"
SUPPORTED_ROUTING_CONDITIONS = frozenset({"always", "from_message_type", "tool_called", "context_equals"})
SUPPORTED_ROUTING_TARGETS = frozenset({"terminate"})
DEFAULT_DELEGATION = {"enabled": False, "inherits_tools": False, "allow_recursive": False}


class AgentBehaviorError(ValueError):
    pass


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def find_agents_root(path: str | Path) -> Path:
    current = Path(path).resolve()
    for parent in (current if current.is_dir() else current.parent, *current.parents):
        if (parent / "index.json").exists():
            return parent
    raise AgentBehaviorError(f"could not find mn-agents root for {path}")


def load_behavior(agent_dir: str | Path) -> dict[str, Any]:
    agent = load_json(Path(agent_dir) / "agent.json")
    behavior = agent.get("behavior")
    if not isinstance(behavior, dict):
        raise AgentBehaviorError(f"{agent_dir}/agent.json.behavior is required")
    return behavior


def validate_behavior(agent: dict[str, Any], *, field: str = "agent.json.behavior") -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    behavior = agent.get("behavior")
    if not isinstance(behavior, dict):
        return [{"severity": "error", "field": field, "message": "behavior block is required"}]

    if behavior.get("schema_version") != BEHAVIOR_SCHEMA_VERSION:
        issues.append({"severity": "error", "field": f"{field}.schema_version", "message": "unsupported behavior schema version"})
    if not isinstance(behavior.get("summary"), str) or not behavior.get("summary"):
        issues.append({"severity": "error", "field": f"{field}.summary", "message": "summary is required"})

    lifecycle = behavior.get("lifecycle_events")
    if not isinstance(lifecycle, dict):
        issues.append({"severity": "error", "field": f"{field}.lifecycle_events", "message": "lifecycle events are required"})
    else:
        _require_string_list(lifecycle.get("success"), f"{field}.lifecycle_events.success", issues)
        _require_string_list(lifecycle.get("failure"), f"{field}.lifecycle_events.failure", issues)

    _require_string_list(behavior.get("required_config"), f"{field}.required_config", issues, allow_empty=True)
    _validate_emits(behavior.get("emits"), field, issues)
    _validate_routing(behavior.get("routing", {}), field, issues)
    _validate_delegation(behavior.get("delegation", {}), field, issues)
    return issues


def simulate_fixture(fixture_path: str | Path, agents_root: str | Path | None = None) -> dict[str, Any]:
    path = Path(fixture_path)
    root = Path(agents_root) if agents_root else find_agents_root(path)
    return simulate_agent_instance(load_json(path), root)


def simulate_agent_instance(instance_node: dict[str, Any], agents_root: str | Path) -> dict[str, Any]:
    if "uses" not in instance_node:
        raise AgentBehaviorError("agent instance must include a uses reference")

    root = Path(agents_root)
    ref = parse_agent_ref(str(instance_node["uses"]))
    template = load_agent_template(ref, root)
    behavior_issues = validate_behavior(template, field=f"{template.get('template_id', '<unknown>')}.behavior")
    if behavior_issues:
        messages = "; ".join(f"{issue['field']}: {issue['message']}" for issue in behavior_issues)
        raise AgentBehaviorError(messages)

    behavior = template["behavior"]
    rendered = render_agent_node(instance_node, root)
    _assert_required_config(rendered, behavior.get("required_config", []))

    success_events = behavior["lifecycle_events"]["success"]
    events = [
        {
            "type": event_type,
            "node_id": rendered.get("node_id"),
            "template_id": ref.template_id,
            "template_category": template.get("template_category"),
            "version": ref.version,
        }
        for event_type in success_events
    ]

    return {
        "node_id": rendered.get("node_id"),
        "template_id": ref.template_id,
        "template_category": template.get("template_category"),
        "version": ref.version,
        "status": "completed",
        "rendered_node": rendered,
        "events": events,
        "messages": _simulate_messages(behavior, instance_node, rendered),
        "artifacts": copy.deepcopy((behavior.get("emits") or {}).get("artifacts", [])),
        "routing": copy.deepcopy(behavior.get("routing", {})),
        "delegation": _delegation_settings(behavior),
    }


def _validate_emits(value: Any, field: str, issues: list[dict[str, str]]) -> None:
    if not isinstance(value, dict):
        issues.append({"severity": "error", "field": f"{field}.emits", "message": "emits block is required"})
        return
    _require_string_list(value.get("events"), f"{field}.emits.events", issues, allow_empty=True)
    messages = value.get("messages")
    if not isinstance(messages, list):
        issues.append({"severity": "error", "field": f"{field}.emits.messages", "message": "messages must be a list"})
    else:
        for index, message in enumerate(messages):
            if not isinstance(message, dict) or not isinstance(message.get("message_type"), str):
                issues.append(
                    {
                        "severity": "error",
                        "field": f"{field}.emits.messages[{index}].message_type",
                        "message": "message_type is required",
                    }
                )
    artifacts = value.get("artifacts")
    if not isinstance(artifacts, list):
        issues.append({"severity": "error", "field": f"{field}.emits.artifacts", "message": "artifacts must be a list"})
    else:
        for index, artifact in enumerate(artifacts):
            if not isinstance(artifact, dict) or not isinstance(artifact.get("artifact_id"), str):
                issues.append(
                    {
                        "severity": "error",
                        "field": f"{field}.emits.artifacts[{index}].artifact_id",
                        "message": "artifact_id is required",
                    }
                )


def _validate_routing(value: Any, field: str, issues: list[dict[str, str]]) -> None:
    if value in (None, {}):
        return
    if not isinstance(value, dict):
        issues.append({"severity": "error", "field": f"{field}.routing", "message": "routing must be an object"})
        return
    transitions = value.get("transitions", [])
    if not isinstance(transitions, list):
        issues.append({"severity": "error", "field": f"{field}.routing.transitions", "message": "transitions must be a list"})
        return
    for index, transition in enumerate(transitions):
        if not isinstance(transition, dict):
            issues.append({"severity": "error", "field": f"{field}.routing.transitions[{index}]", "message": "transition must be an object"})
            continue
        condition_type = ((transition.get("when") or {}).get("type") if isinstance(transition.get("when"), dict) else None)
        target_type = ((transition.get("then") or {}).get("type") if isinstance(transition.get("then"), dict) else None)
        if condition_type not in SUPPORTED_ROUTING_CONDITIONS:
            issues.append(
                {
                    "severity": "error",
                    "field": f"{field}.routing.transitions[{index}].when.type",
                    "message": f"unsupported routing condition: {condition_type}",
                }
            )
        if target_type not in SUPPORTED_ROUTING_TARGETS:
            issues.append(
                {
                    "severity": "error",
                    "field": f"{field}.routing.transitions[{index}].then.type",
                    "message": f"unsupported routing target: {target_type}",
                }
            )


def _validate_delegation(value: Any, field: str, issues: list[dict[str, str]]) -> None:
    if value in (None, {}):
        return
    if not isinstance(value, dict):
        issues.append({"severity": "error", "field": f"{field}.delegation", "message": "delegation must be an object"})
        return
    for key in ("enabled", "inherits_tools", "allow_recursive"):
        if key in value and not isinstance(value[key], bool):
            issues.append({"severity": "error", "field": f"{field}.delegation.{key}", "message": "must be a boolean"})
    if value.get("allow_recursive") is True:
        issues.append({"severity": "error", "field": f"{field}.delegation.allow_recursive", "message": "recursive delegation is not allowed"})


def _require_string_list(value: Any, field: str, issues: list[dict[str, str]], *, allow_empty: bool = False) -> None:
    if not isinstance(value, list) or (not allow_empty and not value) or any(not isinstance(item, str) for item in value):
        issues.append({"severity": "error", "field": field, "message": "must be a list of strings"})


def _assert_required_config(rendered: dict[str, Any], required_config: list[str]) -> None:
    config = rendered.get("config") or {}
    missing = [key for key in required_config if key not in config]
    if missing:
        node_id = rendered.get("node_id") or "<unknown>"
        raise AgentBehaviorError(f"node {node_id} missing required rendered config keys: {', '.join(missing)}")


def _simulate_messages(behavior: dict[str, Any], instance_node: dict[str, Any], rendered: dict[str, Any]) -> list[dict[str, Any]]:
    messages = []
    for message in (behavior.get("emits") or {}).get("messages", []):
        message_type = _resolve_value(message.get("message_type"), instance_node, rendered)
        if message_type is None:
            message_type = message.get("fallback_message_type")
        if message_type is None:
            continue
        messages.append(
            {
                "message_type": message_type,
                "node_id": rendered.get("node_id"),
                "status": "simulated",
            }
        )
    return messages


def _delegation_settings(behavior: dict[str, Any]) -> dict[str, bool]:
    settings = dict(DEFAULT_DELEGATION)
    settings.update(copy.deepcopy(behavior.get("delegation") or {}))
    return settings


def _resolve_value(value: Any, instance_node: dict[str, Any], rendered: dict[str, Any]) -> Any:
    if not isinstance(value, str):
        return value
    if value.startswith("with."):
        return _resolve_path(instance_node.get("with") or {}, value.removeprefix("with."))
    if value.startswith("config."):
        return _resolve_path(rendered.get("config") or {}, value.removeprefix("config."))
    if value.startswith("node."):
        return _resolve_path(rendered, value.removeprefix("node."))
    return value


def _resolve_path(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current
