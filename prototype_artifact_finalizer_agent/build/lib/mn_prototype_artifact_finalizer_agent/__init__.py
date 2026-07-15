from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from mn_sdk.blueprint_support import complete_runtime_step, write_json
from mn_sdk.blueprint_support.step_execution import append_event


AGENT_ID = "mn-agents.prototype.artifact_finalizer"
AGENT_VERSION = 1


@dataclass(frozen=True)
class ArtifactWrite:
    path: str
    value: Any
    kind: str = "json"
    destination: str = "output"


@dataclass(frozen=True)
class ArtifactBundle:
    final_artifact: Mapping[str, Any]
    writes: tuple[ArtifactWrite, ...]
    result: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ArtifactFinalizerSpec:
    compose: Callable[..., ArtifactBundle]
    step_id: str = ""
    event_writer: Callable[[Path, str, dict[str, Any]], None] = append_event
    result_builder: Callable[..., Mapping[str, Any]] | None = None
    human_notice: str = ""


def load_agent_definition() -> dict[str, Any]:
    return json.loads(files(__package__).joinpath("resources/agent.json").read_text(encoding="utf-8"))


def create_agent(spec: ArtifactFinalizerSpec) -> Callable[..., dict[str, Any]]:
    def run(context: Mapping[str, Any], **options: Any) -> dict[str, Any]:
        bundle = spec.compose(context, **options)
        if not isinstance(bundle, ArtifactBundle):
            raise TypeError("artifact finalizer compose must return ArtifactBundle")
        run_dir = Path(context["run_dir"])
        output_folder = Path(context["output_folder"])
        written: list[str] = []
        for artifact in bundle.writes:
            if artifact.destination not in {"run", "output", "both"}:
                raise ValueError(f"unsupported artifact destination: {artifact.destination}")
            targets = []
            if artifact.destination in {"output", "both"}:
                targets.append(output_folder / artifact.path)
            if artifact.destination in {"run", "both"}:
                targets.append(run_dir / artifact.path)
            for target in targets:
                _write(target, artifact.kind, artifact.value)
                written.append(str(target))
                spec.event_writer(run_dir, "artifact_written", {"path": str(target)})
        result = dict(bundle.result)
        result.setdefault("status", "completed")
        result.setdefault("final_artifact", dict(bundle.final_artifact))
        result["artifact_writes"] = written
        if spec.human_notice:
            spec.event_writer(run_dir, "human_input_requested", {"mode": "approval_required", "reason": spec.human_notice})
        if spec.step_id:
            complete_runtime_step(context, spec.step_id, {"artifact_count": len(written)})
        if spec.result_builder:
            result = dict(spec.result_builder(context, result, **options))
        return result

    run.__name__ = "run"
    return run


def _write(path: Path, kind: str, value: Any) -> None:
    if kind == "json":
        write_json(path, value)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    if kind == "bytes":
        temporary.write_bytes(bytes(value))
    elif kind == "text":
        temporary.write_text(str(value), encoding="utf-8")
    else:
        raise ValueError(f"unsupported artifact kind: {kind}")
    temporary.replace(path)


__all__ = ["AGENT_ID", "AGENT_VERSION", "ArtifactBundle", "ArtifactFinalizerSpec", "ArtifactWrite", "create_agent", "load_agent_definition"]
