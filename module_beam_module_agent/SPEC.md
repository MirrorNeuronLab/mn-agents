# BEAM Module Agent Specification

## Identity

| Field | Value |
| --- | --- |
| Template reference | `mn-agents.module.beam_module@1` |
| Agent ID | `mn-agents.module.beam_module` |
| Distribution | `mn-module-beam-module-agent` |
| Import module | `mn_module_beam_module_agent` |
| Package kind | `runtime_node` |
| Category / kind | `data` / `module` |

## Python and actualization API

`create_agent()` returns a deep copy of the packaged definition.
`create_agent(instance)` delegates rendering to the SDK. The instance must pin
`uses` to the exact version when loaded from a manifest.

Required `with` fields:

| Field | Contract |
| --- | --- |
| `module` | Non-absent runtime module identifier. |
| `module_source` | Non-absent source path consumed by the runtime. |
| `emit_type` | Non-absent emitted message type. |

The renderer checks presence, not value type or source-file existence. Blueprint
validation and packaging must provide those stronger guarantees.

Optional fields: `stereotype`, `node_type`, `role`, `backpressure`, and
`answer_node`. No v1 stereotypes are defined.

Rendered defaults:

```json
{"type": "generic", "agent_type": "module", "config": {}}
```

Required and optional instance fields are rendered into `config` according to
the shared SDK merge rules. Top-level `config` has final precedence.

## Behavior metadata

- Summary: load a BEAM module node that emits typed workflow messages.
- Required effective config: `module`, `module_source`, `emit_type`.
- Success events: `agent_started`, `agent_completed`.
- Failure events: `agent_started`, `agent_failed`.
- Message: `config.emit_type`, with `module_completed` fallback.
- Artifact: `result` using
  `mn-agents.module.beam_module.output.v1`.
- Delegation: disabled.
- Default transition: terminate after completion.

## Invariants and security

- Rendering must not read or execute `module_source`.
- Source paths and module identifiers must be treated as trusted blueprint
  configuration, not model-generated runtime input.
- The BEAM module owns its internal state, payload semantics, and backpressure
  interpretation.
- This template must not gain Python-specific execution fields.

## Compatibility and required tests

Required field names, generic/module defaults, emitted fallback, and lifecycle
metadata are versioned. Tests must cover missing each required field, the
minimal render fixture, config overrides, deep-copy isolation, and unknown
stereotype rejection.
