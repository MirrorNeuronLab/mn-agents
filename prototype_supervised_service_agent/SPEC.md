# Supervised Service Agent Specification

## Identity

| Field | Value |
| --- | --- |
| Agent ID | `mn-agents.prototype.supervised_service` |
| Version | `1` |
| Distribution | `mn-prototype-supervised-service-agent` |
| Import module | `mn_prototype_supervised_service_agent` |
| Package kind | `handler_factory` |

## Public data types

```python
ServiceContext(
    config: Mapping[str, Any] = {},
    run_dir: Path | None = None,
    output_folder: Path | None = None,
    stop_event: threading.Event = threading.Event(),
    cycles_completed: int = 0,
)

ServiceResult(status: str, cycles_completed: int = 0, error: str = "")

SupervisedServiceSpec(
    serve: Callable[..., Any] | None = None,
    cycle: Callable[..., Any] | None = None,
    health: Callable[..., Any] | None = None,
    on_start: Callable[..., Any] | None = None,
    on_stop: Callable[..., Any] | None = None,
    on_error: Callable[..., Any] | None = None,
    interval_seconds: float = 0.0,
    max_cycles: int | None = None,
    stop_file: str | Path | None = None,
)
```

## Construction validation

- Exactly one of `serve` and `cycle` must be configured.
- `interval_seconds` must not be negative.
- `max_cycles`, when set, must be positive.

Invalid specifications raise `ValueError`.

## Invocation

The returned callable is:

```python
run(
    *,
    context: ServiceContext | None = None,
    config: Mapping[str, Any] | None = None,
    **options: Any,
) -> dict[str, Any]
```

When `context` is supplied, it is used unchanged and `config` does not replace
its configuration. Otherwise a new `ServiceContext(config=config or {})` is
created.

## Lifecycle order

1. Install `SIGTERM` and `SIGINT` handlers when running in the main thread.
   Each handler sets `context.stop_event`.
2. Resolve the optional stop-file path.
3. Enter the lifecycle `try` block.
4. Call `on_start(context, **options)` when configured.
5. Call `health(context, **options)` once when configured.
6. In serve mode, call `serve(context, **options)` once.
7. In cycle mode, while the stop event is unset:
   - stop before the next cycle when the stop file exists;
   - call `cycle(context, **options)`;
   - increment `cycles_completed` only after a successful return;
   - stop when the configured cycle bound is reached;
   - otherwise wait via `stop_event.wait(interval_seconds)` when non-zero.
8. Construct `ServiceResult("completed", cycles_completed)`.
9. If an exception occurs, call `on_error(context, exception, **options)` when
   configured, then re-raise.
10. Always call `on_stop(context, **options)` when configured.
11. Return the result dictionary only after successful completion.

If `on_error` raises, its exception replaces the observed error. If `on_stop`
raises, normal `finally` exception behavior applies.

## Signal and shutdown limitations

- Signal handlers are not installed from non-main threads.
- Version 1 replaces process handlers for `SIGTERM`/`SIGINT` and does not
  restore prior handlers.
- Signals only set the event. A blocking `serve` callback must observe that
  event or provide its own shutdown mechanism.
- Stop-file existence is checked only in cycle mode and only before a cycle.

## Result contract

The returned mapping contains `status` and `cycles_completed`. `error` is
included only when non-empty, although the current successful path does not
produce an error-bearing result.

## Non-goals

No process creation, crash restart, exponential backoff, daemonization,
distributed lease, readiness event, or health polling is provided. Those
belong to the runtime/service infrastructure.

## Compatibility and required tests

Changing lifecycle order, cycle counter timing, signal semantics, or exception
propagation is breaking. Tests must cover construction validation, serve and
cycle modes, health/start/stop order, max cycles, external stop event,
stop-file shutdown, callback errors, non-main-thread use, and context/config
precedence.
