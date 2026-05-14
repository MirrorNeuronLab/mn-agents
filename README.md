# MirrorNeuron Agents

Shared, versioned agent templates for MirrorNeuron blueprints.

Blueprints can keep domain code and scenarios in `mn-blueprints` while referencing reusable node wiring with `uses` and `with`. Renderers expand those references into concrete manifest nodes and preserve template provenance for auditability.

See [SPEC.md](SPEC.md) for the full contract.

## Testing

Install local test dependencies, then run the catalog and fixture tests:

```bash
python3 -m pip install -r requirements-test.txt
python3 -m pytest -q
```

You can also run the validator directly:

```bash
python3 tools/validate_agents.py --json
```
