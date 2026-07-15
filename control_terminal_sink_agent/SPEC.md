# Terminal Sink Agent Specification

## Identity

| Field | Value |
| --- | --- |
| Template reference | `mn-agents.control.terminal_sink@1` |
| Agent ID | `mn-agents.control.terminal_sink` |
| Distribution | `mn-control-terminal-sink-agent` |
| Import module | `mn_control_terminal_sink_agent` |
| Package kind | `runtime_node` |
| Category / kind | `control` / `aggregator` |

## Python API

`create_agent()` returns an isolated deep copy of the packaged definition.
`create_agent(instance)` renders that instance through the SDK renderer.
`load_agent_definition()` reads packaged `agent.json`.

## Inputs and defaults

There are no intrinsically required instance fields, but behavior metadata
requires effective `complete_on_message` configuration.

Optional actualization fields are `stereotype`, `node_type`, `role`,
`complete_on_message`, `complete_run`, `terminal_sink`, and
`output_message_type`.

Rendered defaults:

```json
{
  "type": "reduce",
  "agent_type": "aggregator",
  "role": "result_sink",
  "config": {}
}
```

## Stereotype contract

`terminal_report_sink` must contribute:

```json
{
  "complete_on_message": true,
  "complete_run": true,
  "terminal_sink": true
}
```

Explicit `with` values deep-merge after the stereotype and therefore override
it. Multiple stereotype syntax is accepted by the SDK, but this template has
only one version-1 stereotype.

## Behavior contract

- Success events: `agent_started`, `agent_completed`.
- Failure events: `agent_started`, `agent_failed`.
- Accepted terminal message transition: `blueprint_report`.
- Transition result: terminate with reason `terminal_report_received`.
- Declared emitted message: `run_completed`.
- Declared artifact: `result`, JSON,
  `mn-agents.control.terminal_sink.output.v1`.
- Delegation and inherited tools: disabled.

The node must be modeled as the workflow's terminal completion boundary. The
packaged Python does not implement message receipt or run termination; the
MirrorNeuron runtime interprets the rendered config and behavior.

## Merge and rendering invariants

- `node_id` is preserved.
- Top-level role overrides `with.role` and the default.
- Top-level type and agent type override defaults.
- Explicit `node.config` has final config precedence.
- `uses` and `with` are not present in the rendered runtime node.
- Unknown stereotypes raise `AgentTemplateError`.

## Non-goals

This package does not compose reports, write final files, wait for human input,
or decide whether a report is valid. Those operations must complete upstream.

## Compatibility and required tests

The stereotype keys, reducer/aggregator defaults, terminal message, termination
reason, and completion event are versioned invariants. Tests must compare the
minimal and rendered fixtures, exercise explicit overrides, verify deep-copy
isolation, and ensure unknown stereotypes fail.
