# AGENTS.md

Instructions for coding agents working in this repository. These instructions
apply only to `mn-agents`.

## Start Here

1. Read repository `SPEC.md` and `README.md`.
2. Read the target package's complete `README.md`, `SPEC.md`, `pyproject.toml`,
   implementation, resources, fixtures, and tests.
3. Check `git status` and preserve unrelated work.

Every `index.json` entry is an independently versioned agent contract. Do not
assume two packages share semantics just because their layouts are similar.

## Repository Boundary

This repository owns reusable, domain-neutral agent packages:

- `runtime_node` packages render/actualize a manifest node; their package
  factory does not execute the represented worker or service.
- `handler_factory` packages wrap injected strategies with bounded reusable
  control flow such as ordering, review, lifecycle, tool loops, or finalization.

Domain prompts, formulas, terminology, schemas, and product decisions belong in
blueprints. Generic tool capabilities belong in `mn-skills`; cross-blueprint
contracts/compilation in `mn-python-sdk`; delivery and routing in Core.

## Package Sources of Truth

Keep these synchronized:

- package implementation and public Python API;
- `src/<module>/resources/agent.json` plus input/output specs;
- `fixtures/minimal.instance.json` and `fixtures/rendered.node.json` for runtime
  nodes;
- exact package identity/version in root `index.json`;
- package `SPEC.md` (normative contract) and README (selection/usage); and
- repository tests.

When they disagree, investigate implementation and tests first, then reconcile
all affected surfaces. Do not silently choose the most convenient description.

## Invariants

- Keep shared agents domain neutral and directly resolvable.
- Preserve declared ordering, stop, retry, failure, event, artifact, and merge
  behavior; these are versioned semantics.
- Tool loops are finite and validate untrusted actions before execution.
- Retryable side effects are idempotent or deduplicated.
- Actor review precedes approval-sensitive finalization.
- Finalizers write only declared artifacts; terminal completion remains at the
  last owning DAG boundary.
- Runtime stereotypes classify capability but do not grant authority or permit
  data leakage.
- Host workers run trusted code; select isolation appropriate to risk.
- Never embed secrets in manifests, resources, examples, fixtures, or paths.

## Change and Verification Workflow

- Update README when selection/usage changes and package SPEC when any public
  input, output, invariant, default, error, or compatibility rule changes.
- Bump the exact agent version when repository `SPEC.md` classifies a change as
  breaking.
- Add success, boundary, error, and fixture-render tests.
- New `index.json` packages must include both documents and be discovered by the
  documentation test.

Run:

```bash
python -m pytest tests/test_agent_documentation.py -q
python -m pytest tests/test_composable_agents.py -q
python -m pytest -q
git diff --check
```

The suite expects the declared sibling `mn-skills/blueprint_support_skill`
source path. Do not copy that dependency into this repository to bypass setup.

## Issue-Fixing Policy

- Fix the root cause in the owning agent contract.
- Avoid fallback paths, compatibility shims, or flags that mask a broken
  primary path.
- Keep specified compatibility behavior narrow, documented, and tested.
