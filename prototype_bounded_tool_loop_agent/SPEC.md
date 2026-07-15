# Bounded Tool Loop Agent Specification

## Identity

| Field | Value |
| --- | --- |
| Agent ID | `mn-agents.prototype.bounded_tool_loop` |
| Version | `1` |
| Distribution | `mn-prototype-bounded-tool-loop-agent` |
| Import module | `mn_prototype_bounded_tool_loop_agent` |
| Package kind | `handler_factory` |

## Public data types

```python
ToolAction(name: str, arguments: Mapping[str, Any] = {}, kind: str = "tool")
ToolObservation(name: str, value: Any = None, error: str = "")
ToolPlan(actions: tuple[ToolAction, ...] = (), metadata: Mapping = {}, stop_reason: str = "")
ToolLoopResult(trace: tuple[dict, ...], stop_reason: str, iterations: int, tool_calls: int)

ToolLoopSpec(
    propose_action: Callable[..., ToolAction | ToolPlan | None],
    execute_action: Callable[..., Any],
    observe_result: Callable[..., ToolObservation | Any] | None = None,
    validate_action: Callable[..., bool] | None = None,
    max_iterations: int = 8,
    max_tool_calls: int = 16,
    partial_on_limit: bool = True,
)
```

## Validation

At construction and invocation, `max_iterations` must be at least one and
`max_tool_calls` must be non-negative. Invocation values are converted with
`int`. Invalid values raise `ValueError`.

## Invocation

`run(context, **options)` accepts call-time `max_iterations` and
`max_tool_calls` overrides. These controls are removed before callbacks receive
options.

For each one-based iteration:

1. Call `propose_action(context, trace, **options)`. The trace is the live list
   accumulated so far.
2. Normalize one `ToolAction` to a one-action `ToolPlan`.
3. Reject any other non-`None` proposal type with `TypeError`.
4. An empty plan stops before counting the current iteration.
5. Validate that every plan member is a `ToolAction`.
6. Process actions in plan order.

## Action semantics

For `kind == "final"`:

- append a trace record containing iteration, action, `kind="final"`, and plan
  metadata;
- do not validate or execute the action;
- do not increment tool calls; and
- return the plan stop reason or `completed`.

For a normal action:

1. If configured, `validate_action(context, action, **options)` must return
   truthy. Otherwise raise `ValueError`.
2. Check the tool-call limit before execution.
3. Create a trace record with iteration, action name, copied arguments, and
   copied plan metadata when non-empty.
4. Call `execute_action(context, action, **options)`.
5. If present, call `observe_result(context, action, value, **options)`;
   otherwise construct `ToolObservation(action.name, value=value)`.
6. Serialize `ToolObservation` to a name/value/error mapping; preserve any
   other observation value unchanged.
7. Append the record and increment tool calls.

An execution or observation exception adds `error` to the current trace record,
appends it, and then propagates the exception. Because no result is returned,
callers needing failed traces must observe or persist them in injected code.

## Stop reasons and status

| Condition | Stop reason | Status |
| --- | --- | --- |
| Proposal is `None` | `completed` | `completed` |
| Empty plan | plan reason or `completed` | `completed` |
| Final action | plan reason or `completed` | `completed` |
| Plan actions finish with a reason | plan reason | `completed` |
| Tool-call limit | `tool_call_budget_exhausted` | `partial` |
| Iteration limit | `iteration_limit_exhausted` | `partial` |

Only the two built-in limit reasons imply `partial`. Custom stop reasons remain
`completed`. When `partial_on_limit` is false, either limit raises
`RuntimeError` instead.

The result also includes the ordered trace, iterations count, and executed
tool-call count.

## Invariants and safety

- Limits bound control flow but not the duration or side effects of one tool.
- Planning is sequential; actions within a plan are sequential.
- Plan metadata is copied into each action record.
- Validation is caller-owned and should treat all proposed values as untrusted.
- Persistence, redaction, LLM budgets, retries, and cancellation are non-goals.

## Compatibility and required tests

Breaking changes include counter semantics, trace keys, validation order,
multi-action ordering, or stop-status mapping. Tests must cover single actions,
multi-action plans, metadata, final actions, zero tool budget, both limits,
`partial_on_limit=False`, invalid proposals/actions, policy rejection,
observation normalization, and execution errors.
