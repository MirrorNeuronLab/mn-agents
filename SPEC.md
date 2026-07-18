# MirrorNeuron Agent Package Specification

## Purpose

This document defines repository-wide rules for `mn-agents` packages. A
package-specific `SPEC.md` is normative for that agent's version. Machine-
readable `agent.json`, input/output specs, catalog entry, fixtures, public
Python API, README, and SPEC must describe one consistent contract.

This specification applies only to packages published from `mn-agents`.

## Package kinds

### Runtime node

A `runtime_node` packages a manifest shape. Its `create_agent(instance)` uses
the SDK template renderer. It may define:

- required and optional actualization fields;
- defaults and stereotypes;
- lifecycle, messages, artifacts, routing, and delegation metadata; and
- minimal/rendered fixtures.

It must not execute the represented worker or service in the package factory.

### Handler factory

A `handler_factory` returns a reusable Python callable around injected
strategies. It owns domain-neutral control flow, such as state lifecycle,
ordering, finite limits, review policy, or declared writes.

It must not introduce domain vocabulary, prompts, formulas, state schemas, or
tool implementations.

## Required package files

Every entry in `index.json` must have:

```text
<package>/
  README.md
  SPEC.md
  pyproject.toml
  src/<module>/
    __init__.py
    resources/
      agent.json
      input.spec.json
      output.spec.json
```

Runtime nodes should also have `fixtures/minimal.instance.json` and
`fixtures/rendered.node.json`.

## Documentation contract

`README.md` must answer:

1. What does this agent own?
2. When should or should it not be selected?
3. What is the smallest valid example?
4. What safety or operational boundary matters?
5. Where is the normative specification?

`SPEC.md` must define:

1. exact identity, version, distribution, module, and package kind;
2. public API or manifest inputs;
3. defaults, resolution order, and algorithm;
4. output, event, message, and error behavior;
5. invariants and explicit non-goals;
6. compatibility/versioning rules; and
7. required tests.

Descriptions must state current behavior, not proposed behavior. Known sharp
edges must be documented plainly.

## Source-of-truth reconciliation

When files disagree, do not silently pick the convenient one. Inspect runtime
code and tests, decide the intended contract, then update all affected sources.
For current-behavior investigation, use this evidence order:

1. executable tests and implementation;
2. packaged `agent.json` and input/output resources;
3. rendered fixtures and `index.json`;
4. package `SPEC.md`; and
5. package `README.md`.

The finished change must make them agree.

## Versioning

An exact `agent_id@version` identifies a contract. A new major agent version is
required for changes to:

- required inputs or public call signatures;
- default execution or merge behavior;
- ordering, retry, failure, lifecycle, or stop semantics;
- result, trace, event, message, or artifact shapes;
- stereotype meaning;
- security or side-effect classification; or
- previously documented invariants.

Additive optional fields may remain in the same version only when omitted
behavior is unchanged and all existing calls still pass.

## Safe modification workflow for coding agents

1. Read `AGENTS.md`, this file, the package README and SPEC, implementation,
   resources, fixtures, and relevant tests.
2. Identify whether the change belongs in SDK controls, an agent pattern, a
   reusable skill, or blueprint domain code.
3. Preserve domain neutrality in this repository.
4. Update implementation and machine-readable contracts together.
5. Update README for usage changes and SPEC for contract changes.
6. Add tests for success, boundary, and failure paths.
7. Run catalog validation, focused tests, full tests, lint, and
   `git diff --check`.
8. Bump the agent version when compatibility rules require it.

## Composition rules

- Place lifecycle wrappers outside strategy dispatch.
- Preserve stable ordering where promised.
- Keep tool loops finite and validate untrusted actions before execution.
- Make retryable side effects idempotent or deduplicated.
- Keep actor review before final approval-sensitive artifact completion.
- Write only declared artifacts at finalization boundaries.
- Keep terminal completion at the last DAG edge.

## Security rules

- Never embed secrets in examples, manifests, prompts, paths, or environment
  literals.
- Treat model-generated commands, URLs, paths, tool names, and configuration as
  untrusted.
- Runtime stereotypes classify capability; they do not authorize data leakage.
- Host workers are for trusted code. Use isolation appropriate to risk.
- Side-effect and retry metadata must match actual behavior.

## Documentation enforcement

The catalog documentation test must discover packages from `index.json`, not a
hard-coded list. A new catalog entry without both documents, an exact identity
reference, core normative sections, or a README-to-SPEC link must fail tests.

## Repository acceptance

Root `index.json` is the package inventory. A repository change is accepted
when catalog documentation validation, composable-agent behavior, and the full
test suite pass:

```bash
python -m pytest tests/test_agent_documentation.py -q
python -m pytest tests/test_composable_agents.py -q
python -m pytest -q
```

Tests may consume the declared sibling blueprint-support skill through
`pytest.ini`; package code must not silently vendor or bootstrap that sibling.
