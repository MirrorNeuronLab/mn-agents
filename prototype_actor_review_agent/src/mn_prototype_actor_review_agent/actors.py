from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from mn_sdk.blueprint_support.runtime import get_configured_actor_llm as _get_configured_actor_llm

from mn_sdk_common.events import agent_activity_event, compact_text, redact_observability_value
from mn_sdk.integrations.actor_models import get_llm_client
from mn_sdk.blueprint_support.utils import utc_now_iso


def resolve_actor_specs(
    config: dict[str, Any] | None,
    *,
    actor_ids: list[str] | tuple[str, ...] | set[str] | None = None,
    include_default: bool = False,
) -> dict[str, dict[str, Any]]:
    """Return actor specs from the standard config.llm.agents contract."""

    llm_config = (config or {}).get("llm") if isinstance((config or {}).get("llm"), dict) else {}
    raw_agents = llm_config.get("agents") if isinstance(llm_config.get("agents"), dict) else {}
    selected_ids = list(actor_ids or [])
    if not selected_ids:
        selected_ids = [key for key in raw_agents if include_default or key != "default"]

    specs: dict[str, dict[str, Any]] = {}
    default_spec = raw_agents.get("default") if isinstance(raw_agents.get("default"), dict) else {}
    for actor_id in selected_ids:
        raw = raw_agents.get(actor_id)
        if not isinstance(raw, dict):
            raw = {}
        merged = {**default_spec, **raw}
        merged.setdefault("llm_config", llm_config.get("default_config") or "primary")
        merged.setdefault("model", llm_config.get("model") or "default")
        merged.setdefault("role", _humanize_actor_id(actor_id))
        responsibilities = merged.get("responsibilities")
        if not isinstance(responsibilities, list) or not [item for item in responsibilities if str(item).strip()]:
            merged["responsibilities"] = [
                "Review the deterministic workflow state for domain-specific risks.",
                "Summarize evidence, caveats, and next review steps without inventing facts.",
                "Keep the output review-only and preserve the source workflow results.",
            ]
        specs[str(actor_id)] = merged
    return specs


def get_actor_llm_client(config: dict[str, Any] | None, llm_client: Any | None = None) -> Any:
    return _get_configured_actor_llm(config, llm_client, _get_actor_llm_client)


def _get_actor_llm_client(config: dict[str, Any] | None, llm_client: Any | None = None) -> Any:
    if llm_client is not None:
        return llm_client
    llm_config = (config or {}).get("llm") if isinstance((config or {}).get("llm"), dict) else {}
    if (
        os.environ.get("MN_BLUEPRINT_QUICK_TEST", "").strip().lower() in {"1", "true", "yes", "on"}
        and bool(llm_config.get("quick_test_uses_fake", False))
    ):
        return get_llm_client("fake")
    mode = str(llm_config.get("mock_mode") if llm_config.get("mode") in {"fake", "mock"} else llm_config.get("mode") or "live")
    return get_llm_client(
        "fake" if mode.lower() in {"fake", "mock", "deterministic"} else None,
        strict=bool(llm_config.get("strict_json", False)),
    )


def llm_usage(llm: Any) -> dict[str, Any]:
    return {
        "provider": getattr(llm, "provider", "unknown"),
        "model": getattr(llm, "model", "unknown"),
        "calls": int(getattr(llm, "calls", 0) or 0),
        "fallback_calls": int(getattr(llm, "fallback_calls", 0) or 0),
        "input_tokens": int(getattr(llm, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(llm, "output_tokens", 0) or 0),
        "total_tokens": int(getattr(llm, "total_tokens", 0) or 0),
        "estimated_tokens": int(getattr(llm, "estimated_tokens", 0) or 0),
        "last_usage": getattr(llm, "last_usage", {}) or {},
    }


def actor_findings(state: dict[str, Any] | None = None) -> dict[str, Any]:
    if state is None:
        return {}
    findings = state.get("actor_findings")
    if not isinstance(findings, dict):
        findings = {}
        state["actor_findings"] = findings
    return findings


def record_actor_finding(state: dict[str, Any], actor_id: str, finding: dict[str, Any]) -> dict[str, Any]:
    findings = actor_findings(state)
    findings[actor_id] = finding
    return findings


def actor_generate_json(
    llm: Any,
    config: dict[str, Any] | None,
    actor_id: str,
    *,
    task: str,
    context: dict[str, Any],
    fallback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    specs = resolve_actor_specs(config, actor_ids=[actor_id])
    spec = specs[actor_id]
    role = str(spec.get("role") or _humanize_actor_id(actor_id))
    responsibilities = [str(item) for item in spec.get("responsibilities") or [] if str(item).strip()]
    global_responsibilities = [
        str(item)
        for item in (((config or {}).get("llm") or {}).get("responsibilities") or [])
        if str(item).strip()
    ]
    default_fallback = {
        "actor_id": actor_id,
        "role": role,
        "summary": f"{role} reviewed the workflow state and found no blocker in deterministic outputs.",
        "findings": [],
        "risks": [],
        "recommended_next_step": "Review source evidence before downstream use.",
        "confidence": 0.72,
    }
    merged_fallback = {**default_fallback, **(fallback or {})}
    merged_fallback["actor_id"] = actor_id
    merged_fallback["role"] = role

    system_prompt = "\n".join(
        [
            f"You are {role}.",
            "Act as a domain actor inside a MirrorNeuron blueprint, not as a generic function.",
            "Your output is review-only: explain, classify, summarize, and flag risks without changing deterministic workflow results.",
            "Responsibilities:",
            *[f"- {item}" for item in responsibilities + global_responsibilities],
            "Return only compact JSON matching the fallback shape.",
        ]
    )
    user_prompt = json.dumps(
        {
            "actor_id": actor_id,
            "task": task,
            "context": redact_observability_value(context),
            "fallback_shape": merged_fallback,
        },
        sort_keys=True,
        default=str,
    )
    try:
        response = llm.generate_json(system_prompt=system_prompt, user_prompt=user_prompt, fallback=merged_fallback)
    except Exception:
        if bool(getattr(llm, "strict", False)):
            raise
        response = dict(merged_fallback)
        if hasattr(llm, "fallback_calls"):
            llm.fallback_calls = int(getattr(llm, "fallback_calls", 0) or 0) + 1

    if not isinstance(response, dict):
        response = dict(merged_fallback)
    response.setdefault("actor_id", actor_id)
    response.setdefault("role", role)
    response.setdefault("responsibilities", responsibilities)
    response.setdefault("provider", getattr(llm, "provider", "unknown"))
    response.setdefault("model", getattr(llm, "model", "unknown"))
    response.setdefault("generated_at", utc_now_iso())
    response["summary"] = compact_text(str(response.get("summary") or merged_fallback["summary"]), 700)
    return response


def emit_actor_activity(
    sink: Any,
    actor_id: str,
    *,
    message: str,
    step_id: str | None = None,
    status: str = "completed",
    result_summary: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    safe_message = str(redact_observability_value(message))
    safe_summary = str(redact_observability_value(result_summary)) if result_summary else None
    event = agent_activity_event(
        "actor_activity",
        message=safe_message,
        category="agent",
        agent_id=actor_id,
        step_id=step_id,
        status=status,
        result_summary=safe_summary,
        details=details,
    )
    payload = event["payload"]
    if hasattr(sink, "event"):
        sink.event("actor_activity", payload)
    else:
        run_dir = Path(sink)
        run_dir.mkdir(parents=True, exist_ok=True)
        record = {"type": "actor_activity", "timestamp": utc_now_iso(), "payload": payload}
        with (run_dir / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")
    return event


def run_actor_review(
    *,
    config: dict[str, Any],
    llm: Any,
    actor_id: str,
    state: dict[str, Any],
    task: str,
    context: dict[str, Any],
    event_sink: Any | None = None,
    step_id: str | None = None,
    fallback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    finding = actor_generate_json(llm, config, actor_id, task=task, context=context, fallback=fallback)
    record_actor_finding(state, actor_id, finding)
    if event_sink is not None:
        emit_actor_activity(
            event_sink,
            actor_id,
            step_id=step_id or actor_id,
            message=f"{actor_id} reviewed workflow evidence",
            result_summary=str(finding.get("summary") or ""),
            details={"confidence": finding.get("confidence"), "role": finding.get("role")},
        )
    return finding


def run_actor_reviews(
    *,
    config: dict[str, Any],
    llm: Any,
    actor_ids: list[str] | tuple[str, ...] | set[str],
    state: dict[str, Any],
    task: str,
    context: dict[str, Any],
    event_sink: Any | None = None,
) -> dict[str, Any]:
    for actor_id in actor_ids:
        run_actor_review(
            config=config,
            llm=llm,
            actor_id=str(actor_id),
            state=state,
            task=task,
            context=context,
            event_sink=event_sink,
            step_id=str(actor_id),
        )
    return actor_findings(state)


def _humanize_actor_id(actor_id: str) -> str:
    return str(actor_id).replace(":", " ").replace("_", " ").title()
