# mn-agents Runtime-Shape Block Specification

`mn-agents` is the shared, versioned block catalog used to turn compact
blueprint template references into concrete `mn.workflow/v1` agent nodes.

The catalog is organized around observed runtime node shapes rather than
domain-specific agent names. A blueprint actualizes a block with `uses`, `with`,
optional `with.stereotype`, and optional node-level `config` overrides.

## Catalog

The v1 catalog contains these block IDs:

- `mn-agents.worker.python_host@1`
- `mn-agents.worker.python_docker@1`
- `mn-agents.worker.llm_host@1`
- `mn-agents.control.terminal_sink@1`
- `mn-agents.control.message_router@1`
- `mn-agents.module.beam_module@1`
- `mn-agents.service.openshell@1`

Old taxonomy IDs are intentionally not cataloged.

## Rendering

Render merge order is:

1. block `defaults`
2. selected `stereotypes[with.stereotype].with`
3. instance `with`
4. explicit node `config`

Rendered executable manifests must contain concrete node `config` only. The
`stereotype` selector is a source-level rendering instruction and must not leak
into runtime config.

## Template Folder Contract

Each block folder must contain:

- `agent.json`
- `input.spec.json`
- `output.spec.json`
- `README.md`
- `payloads/`
- `fixtures/minimal.instance.json`
- `fixtures/rendered.node.json`

Every `agent.json` must include:

- `template_id`
- `template_category`
- `version`
- `kind`
- `description`
- `inputs`
- `input_spec`
- `output_spec`
- `payloads`
- `defaults`
- `stereotypes`
- `provides`
- `renders_to`
- `behavior`

## Behavior

The `behavior` block is a deterministic simulation contract. It is used by
tests and local tools without running MirrorNeuron, LLMs, shells, network
services, or external providers.

Behavior blocks must include:

- `schema_version: mn.agent.behavior.v1`
- `summary`
- `lifecycle_events.success`
- `lifecycle_events.failure`
- `required_config`
- `emits.events`
- `emits.messages`
- `emits.artifacts`

## Stereotypes

Stereotypes capture common runtime defaults that otherwise make manifests noisy.
The initial shared stereotypes are:

- `document_workflow_host_worker`
- `document_workflow_docker_worker`
- `public_browser_worker`
- `internal_write_worker`
- `terminal_report_sink`

Stereotypes must stay generic. Blueprint-specific domain prompts, policies,
customer data, and business logic belong in blueprints.
