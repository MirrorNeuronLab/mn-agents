# mn-agents Specification

`mn-agents` is the shared agent-template library for MirrorNeuron blueprints.

The goal is to let blueprints use reusable, versioned agents instead of repeating node boilerplate in every `manifest.json`. Each reusable agent lives in its own folder and owns the runtime wiring for a common node pattern.

## Architecture Model

An agent is the working unit of a MirrorNeuron workflow. Each agent has a bounded responsibility, accepts typed inputs, produces typed outputs, and communicates with other agents through messages, events, artifacts, streams, or service endpoints. Agents should be understandable as small pieces of behavior, not as hidden monoliths inside one large script.

`mn-agents` stores generic agent templates. A template is a reusable contract for a class of agents, like a reusable block. A blueprint actualizes a template into a concrete runtime agent by pinning a template version with `uses`, supplying values with `with`, and optionally overriding rendered config. The same template can therefore become many customized agents across many workflows.

MirrorNeuron is the runtime and orchestration system for those actualized agents. It runs workflows by scheduling agents, routing messages, applying graph rules, managing pools and resource limits, preserving run state, recording events and artifacts, and enforcing execution boundaries. The runtime should make agent workflows reliable, inspectable, and efficient, especially for edge deployments where compute, memory, network, and provider access may be constrained.

Agents do not all have the same execution needs:

- Deterministic agents can run without LLMs and should be replayable from inputs and config.
- LLM agents must reference named LLM config instead of embedding model settings directly.
- Code-producing, code-reviewing, browser-driving, shell-driving, or untrusted-input LLM agents should run inside an explicit sandbox boundary.
- Service agents may expose or consume ports and should declare tunneling, readiness, and failure events.
- Edge-oriented agents should keep config small, avoid unnecessary provider calls, and declare resource expectations clearly.

The `mn-agents` contract describes what an agent template is and how it can be rendered, validated, and simulated. It does not replace MirrorNeuron runtime execution; it gives the runtime and tests a reliable declaration of what each actualized agent is expected to do.

## Template Actualization

Blueprints assemble workflows from shared templates in the same way systems are assembled from reusable parts:

1. The blueprint chooses a template with `uses`, for example `mn-agents.data_llm_decision@1`.
2. The blueprint customizes it with `with`, such as `role`, `llm_config`, `output_message_type`, `upload_path`, or `complete_on_message`.
3. The renderer expands the template into a concrete manifest node.
4. MirrorNeuron runs that concrete node as an actual workflow agent.
5. Runtime events and rendered provenance record which template produced the agent.

Template authors should keep templates generic. Domain-specific prompts, scenarios, policies, product logic, and customer data belong in blueprints. Template fields should describe reusable execution shape, communication contracts, lifecycle events, resources, and sandbox/service boundaries.

## Goals

- Reduce blueprint-owned code and manifest repetition.
- Keep MirrorNeuron core generic.
- Keep domain logic inside blueprints.
- Make shared agent behavior versioned, testable, and auditable.
- Preserve rendered manifests so runtime behavior is explicit.
- Support reliable and efficient workflow orchestration across local, cloud, and edge runtimes.

## Non-Goals

- `mn-agents` does not replace MirrorNeuron core agent templates such as `generic`, `stream`, `map`, `reduce`, `batch`, or `accumulator`.
- `mn-agents` does not schedule, execute, or supervise workflows by itself; MirrorNeuron owns runtime orchestration.
- `mn-agents` does not own domain-specific simulation, prompts, policies, scenarios, or final artifact meaning.
- `mn-agents` does not store credentials or connector secrets.

## Directory Contract

Each shared agent MUST live in its own folder directly under `mn-agents/`.

Recommended layout:

```text
mn-agents/
  SPEC.md
  README.md
  index.json
  schemas/
    agent.template.schema.json
    agent.instance.schema.json
  data_python_executor/
    agent.json
    input.spec.json
    output.spec.json
    README.md
    payloads/
    fixtures/
      minimal.instance.json
      rendered.node.json
    tests/
  data_llm_decision/
    agent.json
    input.spec.json
    output.spec.json
    README.md
    payloads/
    a2a/
      agent-card.json
    fixtures/
    tests/
  control_join/
    agent.json
    README.md
    fixtures/
    tests/
  control_router/
    agent.json
    README.md
    fixtures/
    tests/
  data_openshell_service/
    agent.json
    README.md
    fixtures/
    tests/
  tools/
    render_agent_templates.py
    validate_agents.py
```

Each agent folder MUST contain:

- `agent.json`: template metadata, inputs, defaults, rendered node behavior, and version.
- `input.spec.json`: machine-readable input contract for the agent.
- `output.spec.json`: machine-readable output contract for the agent.
- `README.md`: human-facing description and examples.
- `payloads/`: reusable scripts, policies, fixtures, adapters, static assets, or runtime support files owned by the agent. This folder MAY be empty for pure manifest/render templates.
- `fixtures/`: at least one valid instance and one expected rendered node.

Each agent folder SHOULD contain:

- `tests/`: agent-specific render and validation tests.
- helper scripts only when the agent owns reusable runtime behavior that cannot live in config alone.

Each agent folder MAY contain:

- `a2a/agent-card.json`: A2A-compatible agent card metadata when the agent explicitly opts into A2A. This is mainly useful for Python LLM agents that need to be discovered or called through an A2A bridge.

## Agent Template Contract

Every `agent.json` MUST include:

- `template_id`: stable id, such as `mn-agents.data_python_executor`.
- `template_category`: `control` for orchestration templates or `data` for workhorse templates.
- `version`: semver version.
- `kind`: runtime kind, such as `executor`, `aggregator`, `router`, `module`, `service`, or `listener`.
- `description`
- `inputs.required`
- `inputs.optional`
- `input_spec`: path to `input.spec.json`.
- `output_spec`: path to `output.spec.json`.
- `payloads`: path to `payloads/`.
- `defaults`
- `provides`
- `renders_to`: usually `manifest.nodes[]`.
- `behavior`: deterministic behavior metadata used by validation and local simulation.

Example:

```json
{
  "template_id": "mn-agents.data_python_executor",
  "template_category": "data",
  "version": 1,
  "kind": "executor",
  "description": "Runs a Python script with standard blueprint lifecycle wiring.",
  "inputs": {
    "required": ["script", "upload_path"],
    "optional": ["output_message_type", "environment", "pool", "pool_slots"]
  },
  "input_spec": "input.spec.json",
  "output_spec": "output.spec.json",
  "payloads": "payloads",
  "defaults": {
    "agent_type": "executor",
    "type": "generic",
    "runner_module": "MirrorNeuron.Runner.HostLocal",
    "workdir_template": "/sandbox/job/{upload_path}",
    "pool": "default",
    "pool_slots": 1
  },
  "provides": [
    "run_store_events",
    "structured_logging",
    "error_handling",
    "artifact_writing"
  ],
  "renders_to": "manifest.nodes[]",
  "behavior": {
    "schema_version": "mn.agent.behavior.v1",
    "summary": "Run a Python script with standard lifecycle, run-store, and artifact conventions.",
    "lifecycle_events": {
      "success": ["agent_started", "agent_completed"],
      "failure": ["agent_started", "agent_failed"]
    },
    "required_config": ["command", "runner_module", "upload_path", "workdir"],
    "emits": {
      "events": ["agent_started", "agent_completed", "agent_failed"],
      "messages": [{"message_type": "with.output_message_type", "fallback_message_type": "blueprint_report"}],
      "artifacts": [{"artifact_id": "result", "mime_type": "application/json"}]
    },
    "routing": {
      "transitions": [
        {
          "when": {"type": "always"},
          "then": {"type": "terminate", "reason": "python_script_completed"}
        }
      ]
    },
    "delegation": {
      "enabled": false,
      "inherits_tools": false,
      "allow_recursive": false
    }
  }
}
```

## Behavior Contract

The `behavior` block makes an agent testable without running MirrorNeuron, LLMs, network services, shell commands, or external tools. It is a deterministic simulation contract, not a replacement for runtime execution.

Every behavior block MUST include:

- `schema_version`: currently `mn.agent.behavior.v1`.
- `summary`: short human-readable behavior statement.
- `lifecycle_events.success` and `lifecycle_events.failure`: event names expected for simulated success and failure paths.
- `required_config`: rendered `config` keys that must exist after template expansion.
- `emits.events`, `emits.messages`, and `emits.artifacts`: deterministic output shapes for local simulation.

Behavior blocks MAY include:

- `routing.transitions`: declarative routing hints using `always`, `from_message_type`, `tool_called`, or `context_equals` conditions and a `terminate` target.
- `delegation`: future delegation metadata. `allow_recursive` MUST remain `false` unless a future major version introduces a recursion-safe runtime model.

The shared simulator in `tools/agent_behavior.py` MUST:

- render fixture instances through the same renderer used by blueprints;
- validate required rendered config keys;
- emit deterministic lifecycle/message/artifact/routing records;
- avoid network, subprocess, LLM, or MirrorNeuron runtime execution.

## Payload Contract

Each agent owns a `payloads/` folder for reusable runtime files. Agent payloads are different from blueprint payloads:

- Agent payloads are shared implementation assets for the reusable agent template.
- Blueprint payloads are domain-specific scripts, policies, prompts, scenarios, media, or data.

Agent payloads MAY include:

- scripts
- helper packages
- static templates
- policy files
- test fixtures
- adapter code
- OpenShell support files

Agent payloads MUST NOT include:

- customer data
- blueprint-specific scenarios
- credentials
- literal API tokens, OAuth tokens, cookies, passwords, or private keys
- domain prompts or policies that belong to a blueprint

When rendering a blueprint that uses a shared agent, the renderer MUST keep agent payload provenance visible. If agent payloads are copied or mounted into a job bundle, rendered metadata MUST record:

- source agent template id and version
- payload source path
- payload target path
- checksum or content version when available

## Input And Output Spec Contract

Each agent MUST define `input.spec.json` and `output.spec.json`.

`input.spec.json` describes the messages, config fields, files, streams, or skill events the agent accepts. It SHOULD include:

- `schema_version`
- `description`
- `accepted_message_types`
- `required_fields`
- `optional_fields`
- optional `protocol_adapters`, when the agent supports an external protocol such as A2A
- `parts`
- `examples`

`output.spec.json` describes the messages, artifacts, events, files, streams, or skill outputs the agent emits. It SHOULD include:

- `schema_version`
- `description`
- `emitted_message_types`
- `artifacts`
- `events`
- optional `protocol_adapters`, when the agent supports an external protocol such as A2A
- `parts`
- `examples`

Minimal input spec example:

```json
{
  "schema_version": "mn.agent.input.v1",
  "description": "Inputs accepted by the Python executor agent.",
  "accepted_message_types": ["run_python_script"],
  "required_fields": ["script", "upload_path"],
  "optional_fields": ["environment", "output_message_type"],
  "parts": [
    {
      "kind": "data",
      "schema": "mn-agents.data_python_executor.input.v1"
    }
  ]
}
```

Minimal output spec example:

```json
{
  "schema_version": "mn.agent.output.v1",
  "description": "Outputs emitted by the Python executor agent.",
  "emitted_message_types": ["blueprint_report"],
  "artifacts": [
    {
      "artifact_id": "result",
      "mime_type": "application/json",
      "schema": "mn-agents.data_python_executor.result.v1"
    }
  ],
  "events": ["agent_started", "agent_completed", "agent_failed"],
  "parts": [
    {
      "kind": "data",
      "schema": "mn-agents.data_python_executor.output.v1"
    }
  ]
}
```

## Optional A2A Compatibility Contract

A2A is an optional protocol adapter, not a required contract for all shared agents. Most local MirrorNeuron agents SHOULD use the native `input.spec.json` and `output.spec.json` contracts without A2A fields.

A2A is mainly useful for Python LLM agents that need to be discovered or called by other agents through an A2A bridge. When an agent opts into A2A, its contract SHOULD map cleanly to A2A concepts:

Large simulations SHOULD prefer lightweight native Beam actors or native MirrorNeuron actors for internal graph execution. These actors SHOULD use native runtime messages, queues, streams, and checkpointing instead of A2A. A2A SHOULD NOT be used on high-volume simulation hot paths unless the actor must interoperate with an external A2A agent.

- Agent discovery maps to an A2A Agent Card.
- Agent input maps to an A2A `Message`.
- Agent output maps to an A2A `Artifact`.
- Message and artifact content maps to A2A `Part` objects such as text, file, or structured data parts.

Agents that do not need A2A interoperability SHOULD omit `a2a/agent-card.json` and A2A-specific fields.

An agent that opts into A2A MUST include `a2a/agent-card.json`.

The A2A agent card SHOULD describe:

- agent name and description
- template id and version
- supported input modes
- supported output modes
- skills exposed by the agent
- authentication or capability requirements, if any
- endpoint or local bridge reference, if available

A2A-enabled input and output specs SHOULD declare the adapter mapping without replacing the native MirrorNeuron contract:

```json
{
  "protocol_adapters": {
    "a2a": {
      "enabled": true,
      "agent_card": "a2a/agent-card.json",
      "input_envelope": "Message",
      "output_envelope": "Artifact",
      "part_types": ["text", "file", "data"]
    }
  }
}
```

Example `agent.json` fragment for a Python LLM agent that opts into A2A:

```json
{
  "template_id": "mn-agents.data_llm_decision",
  "version": 1,
  "input_spec": "input.spec.json",
  "output_spec": "output.spec.json",
  "payloads": "payloads",
  "protocol_adapters": {
    "a2a": {
      "enabled": true,
      "recommended_for": ["python_llm_agent"],
      "agent_card": "a2a/agent-card.json",
      "input_envelope": "Message",
      "output_envelope": "Artifact"
    }
  }
}
```

A2A compatibility MUST NOT hide MirrorNeuron runtime behavior. Rendered manifests still need concrete node configuration, run-store events, and template provenance.

## Blueprint Usage Contract

Blueprints MAY use a shared agent by declaring `uses` and `with` in a manifest node.

Example:

```json
{
  "node_id": "simulation_loop",
  "uses": "mn-agents.data_python_executor@1",
  "with": {
    "script": "scripts/run_blueprint.py",
    "upload_path": "simulation_loop",
    "output_message_type": "blueprint_report"
  },
  "role": "root_coordinator"
}
```

The renderer MUST expand this into a concrete MirrorNeuron node before execution.

The runtime SHOULD execute rendered manifests, not unresolved template references.

## Rendered Manifest Contract

Any blueprint using shared agents MUST expose rendered template output through one of:

- `manifest.rendered.json`
- run metadata
- an equivalent API response

Rendered output MUST include:

- original node declaration
- `template_id`
- resolved template version
- concrete rendered node
- defaults applied
- validation warnings or errors

This keeps shared agents auditable and prevents hidden runtime behavior.

## Versioning

Agent templates use semver.

- Patch version: documentation, examples, or validation wording changes with no rendered behavior change.
- Minor version: new optional fields, new defaults that do not change existing rendered output, or new optional capabilities.
- Major version: changed required fields, changed rendered node behavior, renamed fields, removed defaults, or changed lifecycle behavior.

Blueprints SHOULD pin exact agent versions, such as `mn-agents.data_python_executor@1`.

Blueprints SHOULD NOT depend on `latest` for production runs.

## Template Catalog

Control templates SHOULD cover orchestration behavior:

- `control_lifecycle`: workflow start, stop, pause, and resume signals.
- `control_router`: message routing and state-driven graph movement.
- `control_retry`: bounded retry and backoff decisions.
- `control_join`: reduce/join completion detection.
- `control_message_filter`: predicate-based message filtering.
- `control_checkpoint`: checkpoint and resume metadata.
- `control_approval_gate`: human or policy approval gates.
- `control_tick_source`: stream or polling tick source.
- `control_input_listener`: connector-backed input listener.
- `control_output_fanout`: output fan-out after local run-store writes.
- `control_web_output`: TCP/web UI output service.

Data templates SHOULD cover the workhorse agents that blueprints customize most:

- `data_python_executor`: HostLocal Python script executor.
- `data_python_workflow`: one-shot Python workflow runner with blueprint-standard config/input/output handling.
- `data_module`: native MirrorNeuron or BEAM module node.
- `data_llm_decision`: named `LLM_CONFIG` based LLM decision agent.
- `data_llm_tool`: LLM tool-use agent.
- `data_sandboxed_codegen`: sandboxed code generation, code review, or code execution agent.
- `data_observer`: stream, file, sensor, or service observation agent.
- `data_edge_model`: local or edge model inference agent.
- `data_openshell_service`: custom OpenShell image service with port and SSH tunnel verification.

## Ownership Boundary

Shared agents own:

- runner module defaults
- workdir and upload conventions
- lifecycle event wiring
- structured logging defaults
- error handling defaults
- local run-store integration
- port/tunnel conventions
- input/output skill plumbing
- artifact write conventions

Blueprints own:

- product problem
- domain inputs and scenarios
- domain scripts
- prompts and policies
- LLM roles and responsibilities
- final artifact schema and meaning
- external destination choices

## Required Renderer Behavior

The renderer MUST:

- load `mn-agents/index.json`
- resolve `uses` by `template_id` and exact version
- validate `with` against the template input contract
- merge defaults without overwriting explicit blueprint values
- produce a concrete manifest node
- record provenance in rendered output
- fail before runtime if a required template or required field is missing

The renderer SHOULD:

- produce clear validation errors with node id, template id, and missing field
- warn on deprecated template versions
- warn when a blueprint uses unpinned versions

## Required Validation

Validation MUST confirm:

- every agent folder directly under `mn-agents/` has an `agent.json`
- every agent folder has `input.spec.json`, `output.spec.json`, and `payloads/`
- every `agent.json` has `template_id`, `version`, `kind`, `inputs`, `input_spec`, `output_spec`, `payloads`, `defaults`, `provides`, and `renders_to`
- every template id appears in `index.json`
- every `input.spec.json` declares accepted message types and required fields
- every `output.spec.json` declares emitted message types or artifacts and events
- every agent that opts into A2A declares `protocol_adapters.a2a` and has `a2a/agent-card.json`
- every fixture instance renders successfully
- rendered fixture output matches the expected rendered node
- no template stores literal credentials
- no agent payload stores literal credentials
- LLM templates reference named `LLM_CONFIG` entries instead of concrete model settings
- OpenShell templates declare `container_port`, `external_port`, `tunnel`, and `required` for network services
- TCP output templates use external `8080` and `8081` unless an explicit override is declared

## Acceptance Criteria

- Existing full node declarations remain valid.
- A blueprint can replace repeated executor boilerplate with `uses`.
- Rendering produces the same effective node behavior as an equivalent hand-written node.
- Each shared agent has its own folder.
- `mn-agents/index.json` catalogs all shared agents.
- Each shared agent has `input.spec.json`, `output.spec.json`, and `payloads/`.
- Agents that opt into A2A have `a2a/agent-card.json`; agents that do not opt in have no A2A requirement.
- Each shared agent has at least one fixture render test.
- Rendered manifests preserve template provenance.
- Runtime behavior is debuggable without reading template source.
