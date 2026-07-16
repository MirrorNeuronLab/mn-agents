# Stateful Step Agent

`mn-agents.prototype.stateful_step` is the standard boundary between a
MirrorNeuron `StepContext` and blueprint domain code. It delegates step
lifecycle execution to `mn-python-sdk`, opens the workflow state store, resolves
message inputs, and manages optional prepare/finalize resources.

For individually routed agents, `create_message_agent` layers the SDK
`receive_input`/`send_output` contract and durable idempotent replay over the
same stateful lifecycle. Domain handlers receive an `AgentInput` without route
fields and may return an `AgentHandlerOutput` with bounded payload, artifact
references, metrics, and status.

Use it once at the outside of a step. Keep business logic in the injected
handler and reusable tool behavior in skills.

## What it owns

- SDK step lifecycle and runtime-context creation;
- message-payload discovery when inputs are not supplied explicitly;
- `WorkflowStateStore` access under the existing run directory;
- optional named step state;
- shared resources exposed through `context.services`; and
- finalization after success or failure.

It does not choose operations, process entity queues, invoke tools, review
outputs, or define the blueprint's state schema.

## Message-driven composition

```python
from mn_prototype_stateful_step_agent import (
    AgentHandlerOutput,
    MessageAgentSpec,
    StatefulStepSpec,
    create_message_agent,
)

run = create_message_agent(
    MessageAgentSpec(
        stateful=StatefulStepSpec(context_factory=build_context),
        input_resolver=lambda value: value.payload.get("step_input", {}),
    ),
    lambda context, *, agent_input, **_: AgentHandlerOutput(
        payload={"count": len(agent_input.payload)},
        artifacts=({"kind": "report", "path": "reports/result.json"},),
    ),
)
```

The invocation record is persisted before the output is returned to the SDK.
A duplicate delivery with the same idempotency key returns that durable result
without calling the domain handler again.

## Quick start

```python
from mn_prototype_stateful_step_agent import StatefulStepSpec, create_agent
from mn_sdk.blueprint_support import step_result


def build_context(*, inputs, config, runs_root, run_id):
    run_dir = runs_root / run_id
    return {
        "run_id": run_id,
        "run_dir": run_dir,
        "config": config or {},
        "output_folder": run_dir / "output",
    }


def prepare(context, **_options):
    return {"catalog": {"version": 1}}


def handle(context, **_options):
    context.state["count"] = int(context.state.get("count", 0)) + 1
    return step_result(
        context.to_mapping(),
        "collect",
        count=context.state["count"],
        catalog_version=context.services["catalog"]["version"],
    )


run = create_agent(
    StatefulStepSpec(
        context_factory=build_context,
        input_keys=frozenset({"document_folder"}),
        state_name="collect_state.json",
        prepare=prepare,
    ),
    handle,
)
```

The returned `run` function accepts a MirrorNeuron `StepContext`. Tests and
composition roots may also provide `inputs`, `runs_root`, and `llm_client`
explicitly.

When the compiler assigns the same logical agent to multiple workflow phases,
`StepContext.invocation_id` is used for lifecycle and result persistence. The
logical `step_id` and `agent_id` remain available to domain code.

## Handler context

`StatefulStepContext` supports attributes and mapping-style access:

- `step_context`: original SDK context;
- `runtime_context`: mapping returned by `context_factory`;
- `state_store`: `WorkflowStateStore(run_dir)`;
- `state`: optional named state value;
- `inputs`: resolved message payload;
- `services`: resources returned by `prepare`;
- `llm_client`: optional injected client; and
- `config` and `run_id` convenience properties.

## Resource lifecycle

`prepare` runs before the domain handler. It may return a mapping whose values
are merged into `services`. `finalize` always runs after preparation begins,
including when preparation or the handler raises. It receives `result` and
`error` so resources can be closed and usage can be persisted.

Named state is written only after the handler succeeds. Use explicit
`state_store` operations when different transaction boundaries are required.

## Composition

Recommended order:

```text
stateful_step
  -> operation_router
  -> entity_queue or bounded_tool_loop
  -> optional actor_review
  -> artifact_finalizer
```

See [SPEC.md](SPEC.md) for exact call signatures and failure semantics.
