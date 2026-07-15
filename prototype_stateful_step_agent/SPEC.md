# Stateful Step Agent Specification

## Identity

| Field | Value |
| --- | --- |
| Agent ID | `mn-agents.prototype.stateful_step` |
| Version | `1` |
| Distribution | `mn-prototype-stateful-step-agent` |
| Import module | `mn_prototype_stateful_step_agent` |
| Package kind | `handler_factory` |

This is a Python handler factory. It is not a manifest runtime-node template.

## Public symbols

```python
StatefulStepContext

StatefulStepSpec(
    context_factory: Callable[..., Mapping | Any],
    input_keys: frozenset[str] = frozenset(),
    state_name: str | None = None,
    state_default: Any = {},
    hooks: StepLifecycleHooks = StepLifecycleHooks(),
    prepare: Callable[..., Mapping[str, Any] | None] | None = None,
    finalize: Callable[..., Any] | None = None,
)

create_agent(
    spec: StatefulStepSpec,
    handler: Callable[..., Any],
) -> Callable[..., dict[str, Any]]
```

## Returned handler

The returned callable must have the effective signature:

```python
run(
    step_context: mn_sdk.step_runtime.StepContext,
    *,
    inputs: dict[str, Any] | None = None,
    runs_root: Path | None = None,
    llm_client: Any | None = None,
    **parameters: Any,
) -> dict[str, Any]
```

If `handler` is absent, construction raises `TypeError`.

## Input resolution

1. Explicit `inputs` are used only when they are a `dict`.
2. Otherwise, `find_message_payload` resolves the payload from
   `step_context.message` using `spec.input_keys`.
3. `step_context.config` is forwarded as `None` when false-like.
4. `step_context.step_id` is the lifecycle step identifier.
5. Remaining parameters are captured and forwarded to `prepare`, `handler`,
   and `finalize`.

## Runtime-context contract

`context_factory` is called by `execute_step_handler` with:

```python
context_factory(
    inputs=resolved_inputs,
    config=config,
    runs_root=runs_root,
    run_id=run_id,
)
```

Its return value must either expose `to_mapping()` or be convertible with
`dict(...)`. The mapping must contain `run_dir`. Fields required by downstream
handlers, such as `output_folder`, remain the caller's responsibility.

## Managed context contract

The factory creates `WorkflowStateStore(Path(runtime_context["run_dir"]))`.
When `state_name` is set, it reads that state using `state_default`. The managed
context must provide:

- key and attribute access for state, store, inputs, and services;
- fallback key access to `runtime_context`;
- `get(key, default)` mapping behavior;
- `config` defaulting to an empty mapping;
- `run_id` falling back to `step_context.run_id`; and
- `to_mapping()` containing runtime fields plus managed fields.

## Execution order

The implementation must preserve this order:

1. SDK `execute_step_handler` starts lifecycle handling.
2. Runtime mapping and state store are created.
3. Optional `prepare(managed, llm_client=..., **options)` runs.
4. A non-`None` prepare result must be a mapping and is merged into
   `managed.services`.
5. `handler(managed, llm_client=..., **options)` runs.
6. On successful handler return, named state is written when `state` is not
   `None`.
7. `finalize` runs in a `finally` block with `result` and `error`.

`finalize` must run after prepare or handler exceptions. If `finalize` itself
raises, Python exception replacement rules apply; callers should make cleanup
idempotent and avoid masking the original error.

## State guarantees

- Named state is not automatically written after a failed handler.
- The state object is not copied before being given to the handler.
- The store uses existing SDK state paths; this agent must not introduce a
  blueprint-specific path convention.
- Explicit store writes performed by a handler keep their normal SDK semantics.

## Errors

- Missing handler: `TypeError`.
- Non-mapping prepare result: `TypeError`.
- Invalid runtime mapping or missing `run_dir`: underlying conversion/key error.
- Context, lifecycle hook, state-store, prepare, handler, and finalize errors
  propagate according to SDK and Python semantics.

## Non-goals

This agent must remain domain-neutral. It must not contain business vocabulary,
operation registries, tool policies, actor prompts, artifact schemas, or state
migration logic.

## Compatibility and required tests

Changing input resolution, lifecycle ordering, state-write timing, service
exposure, or finalization-on-error is breaking and requires a new version.
Tests must cover explicit and message inputs, state round trips, prepare
services, parameter forwarding, finalize after success, finalize after prepare
and handler errors, and integration with another handler factory.
