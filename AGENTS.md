# AGENTS.md

Guidance for future coding agents working in this repository.

## Agent Package Documentation

- Read the repository `SPEC.md` and the target package's `README.md` and
  `SPEC.md` before changing implementation, resources, fixtures, or tests.
- Keep human guidance, normative specifications, Python behavior,
  machine-readable resources, and catalog identity consistent.
- Update `README.md` when selection or usage changes. Update `SPEC.md` whenever
  a public contract, invariant, error, default, or compatibility rule changes.
- Every `index.json` package must include both documents and pass
  `tests/test_agent_documentation.py`.
- Keep shared agents domain-neutral. Domain prompts, formulas, schemas, and
  terminology belong in blueprints or reusable skills.

## Issue Fixing Policy

- Unless the user explicitly asks for a temporary workaround, fix the root cause in the intended layer or contract.
- Avoid adding fallback paths, compatibility shims, feature flags, or temp solutions that mask a broken primary path.
- If fallback behavior is already product-specified, keep it narrow, documented, and tested; do not use it to avoid fixing the primary path.
