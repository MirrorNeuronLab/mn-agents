from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from importlib.resources import files
from typing import Any, Callable, Iterable, Mapping


AGENT_ID = "mn-agents.prototype.entity_queue"
AGENT_VERSION = 1
EntityKey = Callable[[Any], str]
EntityLoader = Callable[..., Iterable[Any]]
EntityProcessor = Callable[..., Any]
EntitySkip = Callable[..., bool]


@dataclass(frozen=True)
class EntityOutcome:
    entity_id: str
    status: str
    value: Any = None
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = {"entity_id": self.entity_id, "status": self.status}
        if self.value is not None:
            payload["value"] = self.value
        if self.error:
            payload["error"] = self.error
        return payload


@dataclass(frozen=True)
class EntityQueueSummary:
    outcomes: tuple[EntityOutcome, ...]
    processed_count: int
    skipped_count: int
    failed_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "completed" if not self.failed_count else "completed_with_errors",
            "outcomes": [outcome.to_dict() for outcome in self.outcomes],
            "processed_count": self.processed_count,
            "skipped_count": self.skipped_count,
            "failed_count": self.failed_count,
        }


@dataclass(frozen=True)
class EntityQueueSpec:
    load_entities: EntityLoader
    process_entity: EntityProcessor
    entity_id: EntityKey = lambda entity: str(entity)
    should_skip: EntitySkip = lambda _context, _entity, **_options: False
    max_workers: int = 1
    failure_policy: str = "fail_fast"


def load_agent_definition() -> dict[str, Any]:
    return json.loads(files(__package__).joinpath("resources/agent.json").read_text(encoding="utf-8"))


def create_agent(spec: EntityQueueSpec) -> Callable[..., dict[str, Any]]:
    if spec.failure_policy not in {"fail_fast", "collect"}:
        raise ValueError("entity queue failure_policy must be fail_fast or collect")
    if spec.max_workers < 1:
        raise ValueError("entity queue max_workers must be positive")

    def run(context: Any, **options: Any) -> dict[str, Any]:
        entities = list(options.pop("entities", spec.load_entities(context, **options)))
        outcomes: list[EntityOutcome | None] = [None] * len(entities)
        work: list[tuple[int, Any, str]] = []
        for index, entity in enumerate(entities):
            entity_id = str(spec.entity_id(entity))
            if spec.should_skip(context, entity, **options):
                outcomes[index] = EntityOutcome(entity_id, "skipped")
            else:
                work.append((index, entity, entity_id))

        def process(item: tuple[int, Any, str]) -> tuple[int, EntityOutcome]:
            index, entity, entity_id = item
            try:
                value = spec.process_entity(context, entity, **options)
                if isinstance(value, EntityOutcome):
                    return index, value
                return index, EntityOutcome(entity_id, "processed", value=value)
            except Exception as exc:
                if spec.failure_policy == "fail_fast":
                    raise
                return index, EntityOutcome(entity_id, "failed", error=str(exc))

        if spec.max_workers == 1 or len(work) <= 1:
            for item in work:
                index, outcome = process(item)
                outcomes[index] = outcome
        else:
            with ThreadPoolExecutor(max_workers=spec.max_workers) as executor:
                futures = [executor.submit(process, item) for item in work]
                for future in futures:
                    index, outcome = future.result()
                    outcomes[index] = outcome

        resolved = tuple(outcome for outcome in outcomes if outcome is not None)
        summary = EntityQueueSummary(
            outcomes=resolved,
            processed_count=sum(outcome.status == "processed" for outcome in resolved),
            skipped_count=sum(outcome.status == "skipped" for outcome in resolved),
            failed_count=sum(outcome.status == "failed" for outcome in resolved),
        )
        return summary.to_dict()

    run.__name__ = "run"
    return run


__all__ = [
    "AGENT_ID",
    "AGENT_VERSION",
    "EntityOutcome",
    "EntityQueueSpec",
    "EntityQueueSummary",
    "create_agent",
    "load_agent_definition",
]
