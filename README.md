# MirrorNeuron Agents

`mn-agents` is the shared, versioned agent-template catalog for MirrorNeuron
blueprints. Blueprints actualize these templates with `uses`, `with`, and
`config` instead of copying runtime node boilerplate.

## Quick Start

Install test dependencies and validate the catalog:

```bash
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python tools/validate_agents.py --json
.venv/bin/python -m pytest -q
```

Simulate one block fixture:

```bash
.venv/bin/python tools/simulate_agent.py worker_python_host/fixtures/minimal.instance.json
```

## Details

- [MirrorNeuron Component Guide](../mn-docs/component-guide.md#agent-templates)
- [Blueprints and Skills](../mn-docs/blueprints-and-skills.md)
- [Agent specification](SPEC.md)

## Common Paths

| Path | Purpose |
| --- | --- |
| `index.json` | Catalog of shared templates. |
| `worker_*` | Runtime worker blocks such as host, Docker, and LLM execution. |
| `control_*` | Runtime control blocks such as routing and terminal sinks. |
| `module_*` | Runtime module blocks. |
| `service_*` | Runtime service blocks. |
| `schemas/` | Template and instance schemas. |
| `tools/` | Validation, rendering, and simulation helpers. |
