# Python Host Worker Agent Specification

## Identity

| Field | Value |
| --- | --- |
| Template reference | `mn-agents.worker.python_host@1` |
| Agent ID | `mn-agents.worker.python_host` |
| Distribution | `mn-worker-python-host-agent` |
| Import module | `mn_worker_python_host_agent` |
| Package kind | `runtime_node` |
| Category / kind | `data` / `executor` |

## Actualization contract

`upload_path` is required. `script` is required unless `command` is present.
Optional fields are `stereotype`, `node_type`, `role`,
`output_message_type`, `environment`, `pass_env`, `pool`, `pool_slots`,
`workdir`, `command`, `side_effect`, `timeout_seconds`, `max_attempts`,
`retry_backoff_ms`, `safe_to_retry`, and `idempotent`.

The packaged renderer validates field presence, not command safety, path
containment, types, or executable availability.

## Defaults

Version 1 renders:

```json
{
  "type": "generic",
  "agent_type": "executor",
  "config": {
    "runner_module": "MirrorNeuron.Runner.HostLocal",
    "pool": "default",
    "pool_slots": 1,
    "tty": false,
    "from": "base",
    "no_keep": true,
    "no_auto_providers": true,
    "agent_beacon_required": true,
    "beacon_enabled": true,
    "beacon_interval_ms": 15000,
    "beacon_timeout_ms": 45000,
    "beacon_missed_action": "fail_attempt"
  }
}
```

Given `upload_path=X`, default rendering sets `upload_as=X` and
`workdir=/sandbox/job/X` unless overridden. Given `script=S` without a command,
it sets `command=["python3.11", S]`. `script` itself is not retained in rendered
config.

Manifest workflow control may provide timeout and retry defaults through the
SDK renderer. Explicit node config remains authoritative.

## Stereotypes

`blueprint_host_worker` contributes:

- command `python3 -m mn_sdk.step_runtime`;
- `upload_path`/`upload_as` `runtime`;
- work directory `/sandbox/job/runtime`;
- `side_effect="read"`;
- `safe_to_retry=true`; and
- `idempotent=true`.

`internal_write_worker` contributes only `side_effect="internal_write"`.
Stereotypes deep-merge in listed order, then explicit `with` overrides them.

## Behavior metadata

- Success: `agent_started`, `agent_completed`.
- Failure: `agent_started`, `agent_failed`.
- Message: `config.output_message_type` with `worker_completed` fallback.
- Artifact: `result` using
  `mn-agents.worker.python_host.output.v1`.
- Delegation: disabled.
- Transition: terminate after completion.

## Safety invariants

- Host-local execution must be reserved for trusted commands and payloads.
- Secrets should use `pass_env` or approved runtime mechanisms, never manifest
  literals.
- Side-effect, idempotency, and retry declarations must describe reality.
- A required beacon means blocking handlers must continue satisfying runtime
  liveness expectations.

## Compatibility and required tests

Required fields, derived paths/command, stereotypes, beacon defaults, runner,
and fallback output type are versioned. Tests must cover script and explicit
command forms, stereotypes and their composition, config precedence, missing
fields, workflow retry-policy merge, and deep-copy isolation.
