# LLM Host Worker Agent Specification

## Identity

| Field | Value |
| --- | --- |
| Template reference | `mn-agents.worker.llm_host@1` |
| Agent ID | `mn-agents.worker.llm_host` |
| Distribution | `mn-worker-llm-host-agent` |
| Import module | `mn_worker_llm_host_agent` |
| Package kind | `runtime_node` |
| Category / kind | `data` / `executor` |

## Actualization contract

`llm_config` is required. Optional fields are `stereotype`, `node_type`,
`role`, `output_message_type`, `timeout_seconds`, `max_attempts`,
`retry_backoff_ms`, `tools`, and `system_prompt_ref`.

Version 1 defines no stereotypes. Unknown stereotypes must raise
`AgentTemplateError`.

The renderer validates presence, not whether `llm_config` exists in a blueprint,
whether prompt resources exist, or whether tools are authorized.

## Rendered defaults

```json
{
  "type": "map",
  "agent_type": "executor",
  "config": {
    "runner_module": "MirrorNeuron.Runner.HostLocal",
    "beacon_enabled": true,
    "beacon_interval_ms": 15000,
    "beacon_timeout_ms": 45000,
    "beacon_missed_action": "fail_attempt"
  }
}
```

Workflow step control may fill positive timeout and retry values when the node
does not already define them. Explicit `with`/`config` values retain SDK
precedence.

## Behavior metadata

- Effective required config: `runner_module` and `llm_config`.
- Success events: `agent_started`, `agent_completed`.
- Failure events: `agent_started`, `agent_failed`.
- Message: `config.output_message_type` with `llm_worker_completed` fallback.
- Artifact: `result` using
  `mn-agents.worker.llm_host.output.v1`.
- Delegation: disabled; tools are not inherited.
- Transition: terminate after completion.

## Security and policy invariants

- `llm_config` must reference runtime-controlled provider/model settings.
- Secrets must never be embedded in `with`, prompt references, or tool names.
- Listed tools still require independent runtime authorization and validation.
- Prompt construction, usage accounting, structured response validation,
  strict-live policy, fallback, and redaction are outside this template.
- Beacon configuration describes worker liveness, not LLM request timeout.

## Python API

`create_agent()` returns a deep copy of the definition.
`create_agent(instance)` renders via the SDK.
`load_agent_definition()` loads packaged metadata.

## Compatibility and required tests

The required reference, executor/map shape, host runner, beacon defaults,
fallback message, and no-delegation policy are versioned. Tests must cover the
minimal fixture, missing `llm_config`, config and workflow-control precedence,
unknown stereotype rejection, and deep-copy isolation.
