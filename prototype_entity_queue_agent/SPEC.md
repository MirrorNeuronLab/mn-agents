# Entity Queue Agent Specification

## Identity

| Field | Value |
| --- | --- |
| Agent ID | `mn-agents.prototype.entity_queue` |
| Version | `1` |
| Distribution | `mn-prototype-entity-queue-agent` |
| Import module | `mn_prototype_entity_queue_agent` |
| Package kind | `handler_factory` |

## Public symbols

```python
EntityOutcome(entity_id: str, status: str, value: Any = None, error: str = "")
EntityQueueSummary(outcomes, processed_count, skipped_count, failed_count)

EntityQueueSpec(
    load_entities: Callable[..., Iterable[Any]],
    process_entity: Callable[..., Any],
    entity_id: Callable[[Any], str] = str,
    should_skip: Callable[..., bool] = always_false,
    max_workers: int | Callable[..., int] = 1,
    failure_policy: str = "fail_fast",
)

create_agent(spec: EntityQueueSpec) -> Callable[..., dict[str, Any]]
```

## Construction validation

- `failure_policy` must be `"fail_fast"` or `"collect"`.
- An integer `max_workers` must be positive.
- Callable worker resolvers are validated at invocation.

## Invocation

The returned callable has the logical signature:

```python
run(
    context: Any,
    *,
    entities: Iterable[Any] | None = None,
    max_workers: int | Callable[..., int] | None = None,
    **options: Any,
) -> dict[str, Any]
```

`entities` and `max_workers` are control parameters and must not be forwarded to
callbacks. Other options are forwarded.

## Algorithm

1. Use explicit `entities` when provided; otherwise call
   `load_entities(context, **options)`.
2. Materialize the iterable as a list.
3. Resolve workers from the call override or spec. If callable, invoke it as
   `resolver(context, **options)`.
4. Convert the worker value with `int` and require a positive result.
5. In input order, derive `str(entity_id(entity))` and evaluate
   `should_skip(context, entity, **options)`.
6. Place skipped outcomes immediately; retain other items with their original
   indexes.
7. Process sequentially when workers equal one or work has at most one item.
   Otherwise submit all work to `ThreadPoolExecutor(max_workers=...)`.
8. Place every result at its original input index.
9. Return the summary.

Parallel completion order must never change outcome order.

## Processor contract

The processor is called as:

```python
process_entity(context, entity, **options)
```

If it returns `EntityOutcome`, that object is used verbatim, including its
`entity_id` and `status`. Any other result is wrapped as a `processed` outcome
with the precomputed entity ID.

## Failure policy

With `fail_fast`, processor exceptions propagate. Submitted parallel work is
managed by the executor context; callers must not assume pending work is
cancelled or that no other side effects occur.

With `collect`, each processor exception becomes:

```json
{"entity_id": "...", "status": "failed", "error": "exception text"}
```

Loader, ID, skip, worker-resolution, and executor-level errors always
propagate; `collect` applies only to `process_entity`.

## Summary contract

The result contains `status`, ordered `outcomes`, and processed/skipped/failed
counts. `status` is `completed` when `failed_count == 0` and
`completed_with_errors` otherwise. Outcome `value` is omitted when `None`;
`error` is omitted when empty.

## Invariants and non-goals

- The queue is finite and eagerly materialized.
- No retries, checkpoints, persistence, rate limits, or async event loop are
  provided.
- Shared context and callbacks must be thread-safe when workers exceed one.
- Stable ordering is a compatibility invariant.

## Compatibility and required tests

Breaking changes include reordered outcomes, different override precedence, or
broader `collect` behavior. Tests must cover skips, ordered parallel completion,
dynamic and per-call workers, invalid limits, both failure policies, explicit
entity override, and direct `EntityOutcome` returns.
