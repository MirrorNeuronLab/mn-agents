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

Simulate one template fixture:

```bash
.venv/bin/python tools/simulate_agent.py data_python_executor/fixtures/minimal.instance.json
```

## Details

- [MirrorNeuron Component Guide](../mn-docs/component-guide.md#agent-templates)
- [Blueprints and Skills](../mn-docs/blueprints-and-skills.md)
- [Agent specification](SPEC.md)

## Common Paths

| Path | Purpose |
| --- | --- |
| `index.json` | Catalog of shared templates. |
| `control_*` | Control-flow templates such as routing, retry, joins, and approvals. |
| `data_*` | Workhorse templates such as Python execution, LLM use, observation, and services. |
| `schemas/` | Template and instance schemas. |
| `tools/` | Validation, rendering, and simulation helpers. |
