# Message Router Agent Specification

## Identity

| Field | Value |
| --- | --- |
| Template reference | `mn-agents.control.message_router@1` |
| Agent ID | `mn-agents.control.message_router` |
| Distribution | `mn-control-message-router-agent` |
| Import module | `mn_control_message_router_agent` |
| Package kind | `runtime_node` |
| Category / kind | `control` / `router` |

## Python API

`create_agent(None)` must return a deep copy of the packaged `agent.json`.
`create_agent(instance)` must call SDK
`render_agent_node_from_definition(instance, definition)`.
`load_agent_definition()` must load a new dictionary from the packaged JSON.

## Actualization contract

Instances are manifest node mappings containing:

```json
{
  "node_id": "string",
  "uses": "mn-agents.control.message_router@1",
  "with": {},
  "config": {}
}
```

Version 1 has no required `with` fields. Optional fields are `stereotype`,
`node_type`, `role`, `emit_type`, `conditions`, `routing_mode`, and
`output_message_type`.

Rendered defaults are:

```json
{"type": "map", "agent_type": "router", "config": {}}
```

Top-level `type` and `agent_type` override defaults. Role resolves from the
top-level node, then `with.role`, then template default. Instance values become
config, and explicit `node.config` has final config precedence according to the
SDK renderer.

No stereotypes are defined in version 1. Supplying one must fail as an unknown
stereotype.

## Behavior metadata

- Summary: route or normalize incoming workflow messages.
- Success lifecycle: `agent_started`, then `agent_completed`.
- Failure lifecycle: `agent_started`, then `agent_failed`.
- Declared artifact: `result`, JSON,
  `mn-agents.control.message_router.output.v1`.
- Declared message: `config.emit_type` with `route_message` fallback.
- Delegation: disabled; recursive delegation and inherited tools are disabled.
- Routing transition: terminate after completion.

These fields describe the runtime contract; the Python package only renders the
node and does not transport messages itself.

## Input and output resources

`input.spec.json` accepts `actualize_agent_template` and defines optional
actualization fields. `output.spec.json` declares `route_message` and the
`result` artifact schema. The resource files are the machine-readable source of
truth and must remain consistent with this document.

## Invariants and non-goals

- Exact version pinning with `@1` is required by SDK reference parsing.
- Rendering must not mutate the packaged definition or input instance.
- Domain conditions and message payload schemas are blueprint-owned.
- This template is not the Python `operation_router` factory.

## Compatibility and required tests

Changing defaults, kind, emitted fallback type, lifecycle, or rendered config
keys requires a new version. Tests must cover definition-copy isolation,
minimal fixture rendering, explicit overrides, absent emit type, and rejection
of unknown stereotypes.
