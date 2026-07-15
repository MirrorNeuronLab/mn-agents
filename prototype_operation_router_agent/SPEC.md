# Operation Router Agent Specification

## Identity

| Field | Value |
| --- | --- |
| Agent ID | `mn-agents.prototype.operation_router` |
| Version | `1` |
| Distribution | `mn-prototype-operation-router-agent` |
| Import module | `mn_prototype_operation_router_agent` |
| Package kind | `handler_factory` |

This document is normative for version 1. “Must” describes compatibility
requirements; “should” describes recommended caller behavior.

## Public symbols

```python
OperationBinding(
    handler: Callable[..., Any],
    bound_kwargs: Mapping[str, Any] = {},
)

OperationRouterSpec(
    operations: Mapping[str, Callable | OperationBinding],
    selector: str = "operation",
    label: str = "operation",
)

create_agent(
    spec: OperationRouterSpec | Mapping[str, Callable | OperationBinding],
    **options,
) -> Callable[..., Any]
```

`AGENT_ID`, `AGENT_VERSION`, and `load_agent_definition` are also public.

## Construction contract

1. Every operation key is converted to `str` and stripped.
2. The normalized key must not be empty.
3. A plain callable is normalized to `OperationBinding(callable)`.
4. Every binding handler must be callable.
5. Duplicate normalized keys follow normal mapping construction semantics; the
   final mapping value is used.
6. In compact form, `selector` and `label` default to `"operation"`.

The returned callable is named `run`.

## Invocation contract

The returned handler has the logical signature:

```python
run(context: Any, **parameters: Any) -> Any
```

Selection occurs in this order:

1. Remove and use `parameters[selector]` when present.
2. Otherwise, if `context` is a `Mapping`, read `context.get(selector)`.
3. Otherwise, read `getattr(context, selector, None)`.
4. Convert the selected value to stripped text. A false-like or absent value
   becomes the empty string.

The selected handler is called as:

```python
handler(context, **{**bound_kwargs, **remaining_parameters})
```

Therefore, per-call parameters must override bound keyword arguments. The
selector itself must not be forwarded. The handler result must be returned
without wrapping, copying, normalization, or serialization.

## Errors

- Empty operation name at construction: `ValueError`.
- Non-callable handler at construction: `TypeError`.
- Missing or unknown selector at invocation: `ValueError` containing the
  configured label and sorted available operation names.
- Handler exceptions: propagate unchanged.

The router must not silently select a default operation.

## Invariants and non-goals

- Dispatch is synchronous and performs exactly one handler call.
- The configured operation table is captured when the factory is created.
- Domain state, authorization, retries, tracing, and persistence are outside
  this contract.
- The router does not inspect handler signatures.
- `bound_kwargs` values should be immutable or treated as read-only by callers.

## Composition requirements

The router may be wrapped by `stateful_step`, `actor_review`, or another
domain-neutral lifecycle wrapper because it preserves the handler return type.
When nested, the outer wrapper owns lifecycle events and error policy.

## Compatibility and safe evolution

The following are breaking changes and require a new agent version:

- changing selection precedence;
- forwarding the selector to the handler;
- changing per-call override precedence;
- returning a wrapper object instead of the handler value; or
- adding implicit fallback selection.

New optional dataclass fields may be additive only when existing calls retain
the same behavior.

## Required tests

Changes must cover:

- compact and `OperationRouterSpec` construction;
- selector lookup from call, mapping, and object attribute;
- bound arguments and per-call overrides;
- unknown operation diagnostics;
- invalid names and handlers; and
- unchanged propagation of return values and exceptions.
