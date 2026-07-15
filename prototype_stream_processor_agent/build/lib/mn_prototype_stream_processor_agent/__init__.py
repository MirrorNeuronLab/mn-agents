from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib.resources import files
from typing import Any, Callable, Iterable, Mapping


AGENT_ID = "mn-agents.prototype.stream_processor"
AGENT_VERSION = 1


@dataclass(frozen=True)
class StreamItemResult:
    item_id: str
    status: str
    value: Any = None
    error: str = ""


@dataclass(frozen=True)
class StreamSummary:
    items: tuple[StreamItemResult, ...]
    processed_count: int
    failed_count: int
    exhausted: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "completed" if not self.failed_count else "completed_with_errors",
            "items": [item.__dict__ for item in self.items],
            "processed_count": self.processed_count,
            "failed_count": self.failed_count,
            "exhausted": self.exhausted,
        }


@dataclass(frozen=True)
class StreamProcessorSpec:
    source: Callable[..., Iterable[Any]]
    process: Callable[..., Any]
    emit: Callable[..., Any]
    checkpoint: Callable[..., Any] | None = None
    item_id: Callable[[Any], str] = lambda item: str(item)
    retries: int = 0
    failure_policy: str = "fail_fast"


def load_agent_definition() -> dict[str, Any]:
    return json.loads(files(__package__).joinpath("resources/agent.json").read_text(encoding="utf-8"))


def create_agent(spec: StreamProcessorSpec) -> Callable[..., dict[str, Any]]:
    if spec.retries < 0:
        raise ValueError("stream retries must not be negative")
    if spec.failure_policy not in {"fail_fast", "collect"}:
        raise ValueError("stream failure_policy must be fail_fast or collect")

    def run(context: Any, **options: Any) -> dict[str, Any]:
        results: list[StreamItemResult] = []
        for item in spec.source(context, **options):
            item_id = str(spec.item_id(item))
            last_error = ""
            for attempt in range(spec.retries + 1):
                try:
                    value = spec.process(context, item, **options)
                    spec.emit(context, item, value, **options)
                    if spec.checkpoint:
                        spec.checkpoint(context, item, value, **options)
                    results.append(StreamItemResult(item_id, "processed", value=value))
                    break
                except Exception as exc:
                    last_error = str(exc)
                    if attempt >= spec.retries and spec.failure_policy == "fail_fast":
                        raise
            else:
                results.append(StreamItemResult(item_id, "failed", error=last_error))
        summary = StreamSummary(
            items=tuple(results),
            processed_count=sum(item.status == "processed" for item in results),
            failed_count=sum(item.status == "failed" for item in results),
            exhausted=True,
        )
        return summary.to_dict()

    run.__name__ = "run"
    return run


__all__ = ["AGENT_ID", "AGENT_VERSION", "StreamItemResult", "StreamProcessorSpec", "StreamSummary", "create_agent", "load_agent_definition"]
