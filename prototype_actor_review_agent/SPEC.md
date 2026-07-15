# Actor Review Agent Specification

## Identity

| Field | Value |
| --- | --- |
| Agent ID | `mn-agents.prototype.actor_review` |
| Version | `1` |
| Distribution | `mn-prototype-actor-review-agent` |
| Import module | `mn_prototype_actor_review_agent` |
| Package kind | `handler_factory` |

## Public data types

```python
ActorReviewResult(
    findings: Any,
    warnings: tuple[dict[str, Any], ...] = (),
    status: str = "completed",
)

ActorReviewSpec(
    runner: Callable[..., Any],
    actor_ids: tuple[str, ...] | Callable[..., list[str] | tuple[str, ...]] = (),
    build_context: Callable[..., Any] | None = None,
    normalize: Callable[[Any], Any] | None = None,
    persist: Callable[..., Any] | None = None,
    failure_policy: str | Callable[..., str] = "fail",
    on_error: Callable[..., ActorReviewResult | Mapping | Any] | None = None,
)

create_agent(spec) -> Callable[..., dict[str, Any]]
wrap_agent(primary, review, *, when=None, result_key="") -> Callable[..., Any]
```

`ActorReviewResult.to_dict()` must return `status`, `findings`, and a list of
`warnings`.

## Review invocation

The created review callable is:

```python
run(context, *, llm_client=None, actor_ids=None, **options) -> dict
```

It must:

1. Remove the call-time `actor_ids` override from options.
2. Otherwise use `spec.actor_ids`. When callable, resolve it with
   `actor_ids(context, **options)`.
3. Convert every actor ID to text while preserving order.
4. Resolve callable `failure_policy(context, **options)` and require `fail` or
   `warn`.
5. Build review context with `build_context(context, **options)` when present;
   otherwise use `context`.
6. Invoke the runner with named arguments:

```python
runner(
    config=context.get("config", {}) if context supports get else {},
    llm=llm_client,
    actor_ids=resolved_actor_ids,
    context=review_context,
    **options,
)
```

7. Apply `normalize(findings)` when configured.
8. Construct a completed `ActorReviewResult`.
9. Persist with `persist(context, result, **options)` when configured.
10. Return `result.to_dict()`.

## Failure and recovery

A literal construction-time failure policy outside `fail`/`warn` raises
`ValueError`. A callable policy is validated on every call.

Any exception in runner, normalization, or initial persistence follows the
resolved policy:

- `fail`: re-raise unchanged.
- `warn`: call
  `on_error(context, exception, actor_ids=resolved_actor_ids, **options)` when
  configured.

Recovery values normalize as follows:

- `ActorReviewResult`: use directly.
- Mapping containing `findings` or `status`: construct a result using mapping
  values, defaulting status to `completed_with_warnings`.
- Any other value: use it as findings, or `{}` when false-like, and add a
  generic `actor_review` warning containing the exception text.

Recovered results are persisted. An exception during recovery or recovered
persistence propagates.

## Wrapper contract

`wrap_agent` returns a handler that:

1. calls the primary handler through signature-aware option filtering;
2. returns immediately if the primary raises;
3. evaluates optional `when(context, result=primary_result, **options)` through
   the same filtering;
4. skips review when `when` is false;
5. calls review with `primary_result` and the same `llm_client`/options;
6. if `result_key` is non-empty and primary result is a mapping, returns a
   shallow copy with review output attached; and
7. otherwise returns the original primary result.

The helper forwards all options to callables accepting `**kwargs` and only
declared options to stricter primary/`when` callables. The review callable is
invoked directly and must accept the documented options.

## Invariants and non-goals

- Reviews are sequential with respect to the primary handler.
- The factory does not define actors, prompts, approval semantics, or schemas.
- `warn` is explicit degradation, never silent success.
- `wrap_agent` never reviews a failed primary result.

## Compatibility and required tests

Changes to callback names, resolution order, recovery normalization, or wrapper
attachment are breaking. Tests must cover dynamic actors and policy, success
normalization/persistence, fail and warn paths, each recovery form, primary
failure, conditional skip, signature filtering, `primary_result` forwarding,
and `result_key` behavior.
