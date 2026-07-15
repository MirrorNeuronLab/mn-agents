from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib.resources import files
from typing import Any, Callable, Mapping


AGENT_ID = "mn-agents.prototype.actor_review"
AGENT_VERSION = 1


@dataclass(frozen=True)
class ActorReviewResult:
    findings: Any
    warnings: tuple[dict[str, Any], ...] = ()
    status: str = "completed"

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "findings": self.findings, "warnings": list(self.warnings)}


@dataclass(frozen=True)
class ActorReviewSpec:
    runner: Callable[..., Any]
    actor_ids: tuple[str, ...] = ()
    build_context: Callable[..., Any] | None = None
    normalize: Callable[[Any], Any] | None = None
    persist: Callable[..., Any] | None = None
    failure_policy: str = "fail"


def load_agent_definition() -> dict[str, Any]:
    return json.loads(files(__package__).joinpath("resources/agent.json").read_text(encoding="utf-8"))


def create_agent(spec: ActorReviewSpec) -> Callable[..., dict[str, Any]]:
    if spec.failure_policy not in {"fail", "warn"}:
        raise ValueError("actor review failure_policy must be fail or warn")

    def run(context: Any, *, llm_client: Any | None = None, **options: Any) -> dict[str, Any]:
        review_context = spec.build_context(context, **options) if spec.build_context else context
        try:
            findings = spec.runner(
                config=context.get("config", {}) if hasattr(context, "get") else {},
                llm=llm_client,
                actor_ids=list(spec.actor_ids),
                context=review_context,
                **options,
            )
            if spec.normalize:
                findings = spec.normalize(findings)
            result = ActorReviewResult(findings=findings)
            if spec.persist:
                spec.persist(context, result, **options)
            return result.to_dict()
        except Exception as exc:
            if spec.failure_policy == "fail":
                raise
            result = ActorReviewResult(findings={}, warnings=({"kind": "actor_review", "message": str(exc)},), status="completed_with_warnings")
            if spec.persist:
                spec.persist(context, result, **options)
            return result.to_dict()

    run.__name__ = "run"
    return run


__all__ = ["AGENT_ID", "AGENT_VERSION", "ActorReviewResult", "ActorReviewSpec", "create_agent", "load_agent_definition"]
