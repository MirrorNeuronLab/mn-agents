# OpenShell Service Agent Specification

## Identity

| Field | Value |
| --- | --- |
| Template reference | `mn-agents.service.openshell@1` |
| Agent ID | `mn-agents.service.openshell` |
| Distribution | `mn-service-openshell-agent` |
| Import module | `mn_service_openshell_agent` |
| Package kind | `runtime_node` |
| Category / kind | `data` / `service` |

## Python API

`create_agent()` returns an isolated definition copy. `create_agent(instance)`
renders the instance using the shared SDK. `load_agent_definition()` loads
packaged `agent.json`.

## Actualization contract

Required `with` fields:

- `custom_openshell_image`;
- `container_port`;
- `external_port`; and
- `tunnel`.

Optional fields: `stereotype`, `node_type`, `role`, `required`,
`healthcheck_path`, and `output_message_type`. Version 1 has no stereotypes.

Rendered defaults:

```json
{
  "type": "generic",
  "agent_type": "service",
  "config": {
    "required": true,
    "runner_module": "MirrorNeuron.Runner.OpenShell"
  }
}
```

The packaged behavior also lists `runner_module` among required effective
config. The default satisfies that requirement. Presence validation does not
validate port ranges, image availability, or tunnel values.

## Behavior metadata

- Success events: `agent_started`, `agent_completed`.
- Failure events: `agent_started`, `agent_failed`.
- Message: `config.output_message_type`, with `service_ready` fallback.
- Artifact: `result` using
  `mn-agents.service.openshell.output.v1`.
- Delegation: disabled.
- Transition: terminate after agent completion.

The runtime, not this package, starts the image, establishes the tunnel, probes
health, and publishes readiness.

## Configuration and security invariants

- Explicit node config has final render precedence.
- Image, port, tunnel, and healthcheck settings must be trusted deployment
  configuration.
- `required=false` may be supplied explicitly, but the workflow must define
  how downstream nodes degrade when the service is absent.
- Secrets must be supplied through the runtime's secret/environment mechanisms,
  not embedded in this template or its documentation examples.

## Non-goals

No image pull, container start, port allocation, authentication, health retry,
or service shutdown is implemented in Python here.

## Compatibility and required tests

Required fields, runner/default-required values, fallback readiness message,
and service/generic shape are versioned. Tests must cover minimal rendering,
each missing field, explicit overrides, definition isolation, and unknown
stereotype rejection.
