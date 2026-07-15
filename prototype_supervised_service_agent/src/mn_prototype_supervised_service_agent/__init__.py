from __future__ import annotations

import json
import signal
import threading
import time
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Any, Callable, Mapping


AGENT_ID = "mn-agents.prototype.supervised_service"
AGENT_VERSION = 1


@dataclass
class ServiceContext:
    config: Mapping[str, Any] = field(default_factory=dict)
    run_dir: Path | None = None
    output_folder: Path | None = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    cycles_completed: int = 0


@dataclass(frozen=True)
class ServiceResult:
    status: str
    cycles_completed: int = 0
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = {"status": self.status, "cycles_completed": self.cycles_completed}
        if self.error:
            payload["error"] = self.error
        return payload


@dataclass(frozen=True)
class SupervisedServiceSpec:
    serve: Callable[..., Any] | None = None
    cycle: Callable[..., Any] | None = None
    health: Callable[..., Any] | None = None
    on_start: Callable[..., Any] | None = None
    on_stop: Callable[..., Any] | None = None
    on_error: Callable[..., Any] | None = None
    interval_seconds: float = 0.0
    max_cycles: int | None = None
    stop_file: str | Path | None = None


def load_agent_definition() -> dict[str, Any]:
    return json.loads(files(__package__).joinpath("resources/agent.json").read_text(encoding="utf-8"))


def create_agent(spec: SupervisedServiceSpec) -> Callable[..., dict[str, Any]]:
    if (spec.serve is None) == (spec.cycle is None):
        raise ValueError("supervised service requires exactly one of serve or cycle")
    if spec.interval_seconds < 0:
        raise ValueError("service interval_seconds must not be negative")
    if spec.max_cycles is not None and spec.max_cycles < 1:
        raise ValueError("service max_cycles must be positive")

    def run(*, context: ServiceContext | None = None, config: Mapping[str, Any] | None = None, **options: Any) -> dict[str, Any]:
        service_context = context or ServiceContext(config=config or {})
        _install_signal_handlers(service_context.stop_event)
        if spec.stop_file:
            stop_file = Path(spec.stop_file)
        else:
            stop_file = None
        try:
            if spec.on_start:
                spec.on_start(service_context, **options)
            if spec.health:
                spec.health(service_context, **options)
            if spec.serve:
                spec.serve(service_context, **options)
            else:
                while not service_context.stop_event.is_set():
                    if stop_file and stop_file.exists():
                        break
                    spec.cycle(service_context, **options)
                    service_context.cycles_completed += 1
                    if spec.max_cycles and service_context.cycles_completed >= spec.max_cycles:
                        break
                    if spec.interval_seconds:
                        service_context.stop_event.wait(spec.interval_seconds)
            result = ServiceResult("completed", service_context.cycles_completed)
        except Exception as exc:
            if spec.on_error:
                spec.on_error(service_context, exc, **options)
            raise
        finally:
            if spec.on_stop:
                spec.on_stop(service_context, **options)
        return result.to_dict()

    run.__name__ = "run"
    return run


def _install_signal_handlers(stop_event: threading.Event) -> None:
    if threading.current_thread() is not threading.main_thread():
        return
    for name in ("SIGTERM", "SIGINT"):
        value = getattr(signal, name, None)
        if value is not None:
            signal.signal(value, lambda _signum, _frame: stop_event.set())


__all__ = ["AGENT_ID", "AGENT_VERSION", "ServiceContext", "ServiceResult", "SupervisedServiceSpec", "create_agent", "load_agent_definition"]
