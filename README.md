# MirrorNeuron Agents

`mn-agents` is the shared, versioned agent-template catalog for MirrorNeuron
blueprints. Blueprints actualize these templates with `uses`, `with`, and
`config` instead of copying runtime node boilerplate.

## Quick Start

Install test dependencies and validate the catalog:

```bash
python3 -m pip install -r requirements-test.txt
python3 tools/validate_agents.py --json
python3 -m pytest -q
```

Simulate one template fixture:

```bash
python3 tools/simulate_agent.py data_python_executor/fixtures/minimal.instance.json
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
