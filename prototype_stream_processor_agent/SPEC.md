# Stream Processor Agent Specification

## Identity

| Field | Value |
| --- | --- |
| Agent ID | `mn-agents.prototype.stream_processor` |
| Version | `1` |
| Distribution | `mn-prototype-stream-processor-agent` |
| Import module | `mn_prototype_stream_processor_agent` |
| Package kind | `handler_factory` |

## Public data types

```python
StreamItemResult(item_id: str, status: str, value: Any = None, error: str = "")
StreamSummary(items, processed_count, failed_count, exhausted)

StreamProcessorSpec(
    source: Callable[..., Iterable[Any]],
    process: Callable[..., Any],
    emit: Callable[..., Any],
    checkpoint: Callable[..., Any] | None = None,
    item_id: Callable[[Any], str] = str,
    retries: int = 0,
    failure_policy: str = "fail_fast",
)

create_agent(spec) -> Callable[..., dict[str, Any]]
```

## Construction validation

- `retries` must be zero or greater.
- `failure_policy` must be `fail_fast` or `collect`.

## Invocation algorithm

`run(context, **options)` must:

1. Iterate `source(context, **options)` without eager materialization.
2. Derive `item_id = str(spec.item_id(item))` once before attempts.
3. Attempt the item pipeline at most `retries + 1` times.
4. On each attempt:
   - call `process(context, item, **options)`;
   - call `emit(context, item, value, **options)`;
   - if configured, call
     `checkpoint(context, item, value, **options)`;
   - append a processed result and stop retrying that item.
5. On exception, record its text as the last error.
6. When final attempt fails:
   - under `fail_fast`, re-raise immediately;
   - under `collect`, append a failed item after the retry loop.
7. After source exhaustion, return the summary with `exhausted=True`.

Processing is synchronous and source-ordered.

## Retry boundary

The retry unit includes process, emit, and checkpoint. The implementation does
not know which callback caused an exception and does not compensate successful
earlier callbacks. Callers must make the three callbacks idempotent or
deduplicated when retries are enabled.

Errors from `source` iteration and `item_id` are outside the collected item
pipeline and always propagate.

## Result contract

`StreamSummary.to_dict()` returns:

- `status`: `completed` with zero failed items, otherwise
  `completed_with_errors`;
- `items`: source-ordered dataclass dictionaries;
- `processed_count`;
- `failed_count`; and
- `exhausted`, which is `True` for a returned result.

Unlike `EntityOutcome.to_dict`, stream item dictionaries include `value=None`
and `error=""` when those are their dataclass values.

## Invariants and non-goals

- Checkpoint occurs strictly after emit.
- Later items cannot overtake an earlier item.
- No parallel workers, backpressure protocol, async source, skip callback, or
  persistent checkpoint implementation is supplied.
- The factory does not resume from checkpoints; the injected source must do so.

## Compatibility and required tests

Changing callback order, retry scope, collection scope, output keys, or item
ordering is breaking. Tests must cover success, checkpoint order, retry at each
callback stage, duplicate-emission risk, both policies, source/ID errors, empty
sources, and summary counts.
