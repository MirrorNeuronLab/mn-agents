# Python Docker Worker Agent Specification

## Identity

| Field | Value |
| --- | --- |
| Template reference | `mn-agents.worker.python_docker@1` |
| Agent ID | `mn-agents.worker.python_docker` |
| Distribution | `mn-worker-python-docker-agent` |
| Import module | `mn_worker_python_docker_agent` |
| Package kind | `runtime_node` |
| Category / kind | `data` / `executor` |

## Required and optional inputs

Required `with` fields are `upload_path`, `docker_worker_image`, and `image`.
`script` is additionally required unless `command` exists.

Optional fields: `stereotype`, `node_type`, `role`,
`output_message_type`, `environment`, `upload_paths`, `network`, `pool`,
`pool_slots`, `workdir`, `command`, `side_effect`, `timeout_seconds`,
`max_attempts`, and `retry_backoff_ms`.

## Defaults

The executor defaults include:

- runner `MirrorNeuron.Runner.DockerWorker`;
- `pool="default"` and one slot;
- shared/reused container enabled;
- cleanup, no-keep, and no-auto-providers enabled;
- `safe_to_retry=true` and `idempotent=true`;
- `tty=false` and `from="base"`;
- required beacon with 15-second interval, 45-second timeout, and
  `fail_attempt` action; and
- workdir template `/mn/job/{upload_path}`.

Upload/workdir and script-to-command derivation follow the same SDK rules as
the host worker, using the Docker workdir template.

## Stereotype contract

`blueprint_docker_worker` supplies:

```json
{
  "command": ["python3", "-m", "mn_sdk.step_runtime"],
  "docker_worker_image": "docker_worker",
  "network": "mirror-neuron-runtime",
  "side_effect": "read",
  "upload_as": "runtime",
  "upload_path": "runtime",
  "workdir": "/mn/job/runtime"
}
```

`internal_write_worker` supplies `side_effect="internal_write"`.

`public_browser_worker` supplies `side_effect="network_read"` and:

```json
{
  "environment": {
    "W3M_BROWSER_MAX_CHARS": "6000",
    "W3M_BROWSER_TIMEOUT_SECONDS": "12",
    "WEB_BROWSER_MAX_CHARS": "12000",
    "WEB_BROWSER_RESPECT_ROBOTS": "true",
    "WEB_BROWSER_TIMEOUT_SECONDS": "20"
  }
}
```

Stereotypes deep-merge left to right, followed by explicit `with` values.
Explicit `node.config` has final render precedence.

## Behavior metadata

- Success/failure lifecycle: standard started/completed or started/failed.
- Message: `config.output_message_type` with `worker_completed` fallback.
- Artifact: `result` using
  `mn-agents.worker.python_docker.output.v1`.
- Delegation: disabled.
- Transition: terminate after completion.

## Security invariants

- `image`, `docker_worker_image`, commands, mounts/uploads, environment, and
  network settings must be trusted deployment configuration.
- `public_browser_worker` authorizes a classified capability; it must not imply
  permission to send private data to public destinations.
- Browser limits are defaults, not a replacement for action budgets or tool
  policy.
- Retry-safe defaults require the injected workload to remain idempotent.

## Compatibility and required tests

Required inputs, runner/beacon/container defaults, stereotypes, environment
values, derived paths, and output fallback are versioned. Tests must exercise
minimal and composed stereotypes, environment deep merge, missing fields,
script/command forms, explicit config precedence, and fixture equality.
