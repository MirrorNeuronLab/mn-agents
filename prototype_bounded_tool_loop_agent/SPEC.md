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

## Optional tool session

`mn_prototype_bounded_tool_loop_agent.session.ToolSession` combines an explicit
allowlisted `ToolRegistry`, an injected prompt factory, a workspace and a finite
tool-call budget. `run()` uses this package's shared `ToolLoopSpec` loop.
Goal/prompt construction can be supplied by the autonomous-research skill;
execution does not depend on that skill.

`execution.execute_generated_python` validates code and runs it inside the
caller's existing outer sandbox. It bounds code/input/output sizes and runtime,
drains process output with bounded memory, and cleans up its process group.
AST/import checks are policy checks, not a security sandbox.

## Installed skills and durable execution

`skills.SkillRuntime.discover(distributions, bindings)` loads only the explicitly
supplied installed distributions' `mn.skills` entry points. Each descriptor names
its module, manual and operation argument schemas. Trusted bindings map
`(skill_id, operation)` to scoped public Python callables. No installation,
unrestricted path resolution, generated code or model authority is provided.
`list_skills`, `read_skill`, and `invoke_skill` expose one implementation to an
agent; direct callers use the same Python APIs. Invocation requires a prior
manual read, a registered binding, valid JSON-schema arguments, and a bounded
JSON result (65,536 bytes by default). Manuals are package resources, not checkout
paths. This is an additive API; the existing ToolLoopSpec contract is unchanged.

`checkpoint.CheckpointLoop(path, binding, max_decisions=40, max_invocations=24,
seconds=600)` persists a model decision before dispatch and a completed observation
before requesting another decision, composing the existing bounded loop. Bindings
and budgets are hashed and checked on resume. Completed decisions/observations
are reused. A crash during an in-flight operation can retry that operation;
handlers must therefore be read-only or idempotent. The caller supplies domain
state, proposal, execution and cancellation callbacks. Decision records include
concise justifications, never a requirement for private reasoning traces.

The deadline uses POSIX interval timers on the worker main thread, including
blocking calls. Background-thread execution fails explicitly. Cancellation is
checked between actions; an in-flight call is bounded by its timeout/deadline.
Invalid responses and tool errors are recorded and consume budget. Terminal
stop reasons distinguish completion, cancellation, time and call/decision limits.
One worker must own a checkpoint at a time; the enclosing worker lifecycle owns
invocation serialization. No checkpoint is a cross-process locking primitive.
