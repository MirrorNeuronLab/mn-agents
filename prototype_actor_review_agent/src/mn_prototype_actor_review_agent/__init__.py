from __future__ import annotations

import json
import inspect
from dataclasses import dataclass
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
    actor_ids: tuple[str, ...] | Callable[..., list[str] | tuple[str, ...]] = ()
    build_context: Callable[..., Any] | None = None
    normalize: Callable[[Any], Any] | None = None
    persist: Callable[..., Any] | None = None
    failure_policy: str | Callable[..., str] = "fail"
    on_error: Callable[..., ActorReviewResult | Mapping[str, Any] | Any] | None = None


def load_agent_definition() -> dict[str, Any]:
    return json.loads(files(__package__).joinpath("resources/agent.json").read_text(encoding="utf-8"))


def create_agent(spec: ActorReviewSpec) -> Callable[..., dict[str, Any]]:
    if isinstance(spec.failure_policy, str) and spec.failure_policy not in {"fail", "warn"}:
        raise ValueError("actor review failure_policy must be fail or warn")

    def run(context: Any, *, llm_client: Any | None = None, **options: Any) -> dict[str, Any]:
        run_options = dict(options)
        actor_ids_override = run_options.pop("actor_ids", None)
        actor_ids = actor_ids_override if actor_ids_override is not None else spec.actor_ids
        if callable(actor_ids):
            actor_ids = actor_ids(context, **run_options)
        resolved_actor_ids = [str(actor_id) for actor_id in actor_ids]
        failure_policy = spec.failure_policy(context, **run_options) if callable(spec.failure_policy) else spec.failure_policy
        if failure_policy not in {"fail", "warn"}:
            raise ValueError("actor review failure_policy must resolve to fail or warn")
        review_context = spec.build_context(context, **run_options) if spec.build_context else context
        try:
            findings = spec.runner(
                config=context.get("config", {}) if hasattr(context, "get") else {},
                llm=llm_client,
                actor_ids=resolved_actor_ids,
                context=review_context,
                **run_options,
            )
            if spec.normalize:
                findings = spec.normalize(findings)
            result = ActorReviewResult(findings=findings)
            if spec.persist:
                spec.persist(context, result, **run_options)
            return result.to_dict()
        except Exception as exc:
            if failure_policy == "fail":
                raise
            recovered = spec.on_error(context, exc, actor_ids=resolved_actor_ids, **run_options) if spec.on_error else None
            if isinstance(recovered, ActorReviewResult):
                result = recovered
            elif isinstance(recovered, Mapping) and {"findings", "status"} & set(recovered):
                result = ActorReviewResult(
                    findings=recovered.get("findings", {}),
                    warnings=tuple(recovered.get("warnings") or ()),
                    status=str(recovered.get("status") or "completed_with_warnings"),
                )
            else:
                result = ActorReviewResult(
                    findings=recovered or {},
                    warnings=({"kind": "actor_review", "message": str(exc)},),
                    status="completed_with_warnings",
                )
            if spec.persist:
                spec.persist(context, result, **run_options)
            return result.to_dict()

    run.__name__ = "run"
    return run


def wrap_agent(
    primary: Callable[..., Any],
    review: Callable[..., dict[str, Any]],
    *,
    when: Callable[..., bool] | None = None,
    result_key: str = "",
) -> Callable[..., Any]:
    """Run a review after a successful primary handler, optionally attaching its result."""

    def run(context: Any, *, llm_client: Any | None = None, **options: Any) -> Any:
        result = _call(primary, context, llm_client=llm_client, **options)
        if when is not None and not _call(when, context, result=result, **options):
            return result
        review_result = review(
            context,
            llm_client=llm_client,
            primary_result=result,
            **options,
        )
        if result_key and isinstance(result, Mapping):
            attached = dict(result)
            attached[result_key] = review_result
            return attached
        return result

    run.__name__ = "run"
    return run


def _call(handler: Callable[..., Any], context: Any, **options: Any) -> Any:
    parameters = inspect.signature(handler).parameters
    if any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()):
        return handler(context, **options)
    return handler(context, **{key: value for key, value in options.items() if key in parameters})


__all__ = ["AGENT_ID", "AGENT_VERSION", "ActorReviewResult", "ActorReviewSpec", "create_agent", "load_agent_definition", "wrap_agent"]
