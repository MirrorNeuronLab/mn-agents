# Artifact Finalizer Agent Specification

## Identity

| Field | Value |
| --- | --- |
| Agent ID | `mn-agents.prototype.artifact_finalizer` |
| Version | `1` |
| Distribution | `mn-prototype-artifact-finalizer-agent` |
| Import module | `mn_prototype_artifact_finalizer_agent` |
| Package kind | `handler_factory` |

## Public data types

```python
ArtifactWrite(
    path: str,
    value: Any,
    kind: str = "json",
    destination: str = "output",
)

ArtifactBundle(
    final_artifact: Mapping[str, Any],
    writes: tuple[ArtifactWrite, ...],
    result: Mapping[str, Any] = {},
)

ArtifactFinalizerSpec(
    compose: Callable[..., ArtifactBundle],
    step_id: str = "",
    event_writer: Callable[[Path, str, dict], None] = append_event,
    result_builder: Callable[..., Mapping] | None = None,
    human_notice: str = "",
)
```

## Context requirements

`run(context, **options)` requires mapping keys:

- `run_dir`: root for `destination="run"` and event recording;
- `output_folder`: root for `destination="output"`; and
- any additional keys required by compose/result callbacks.

## Execution order

1. Call `compose(context, **options)`.
2. Require an `ArtifactBundle`; otherwise raise `TypeError`.
3. Iterate writes in declaration order.
4. Require destination to be `run`, `output`, or `both`.
5. Resolve output before run when destination is `both`.
6. Write each target.
7. Append its string path to `artifact_writes`.
8. Emit `artifact_written` with `{"path": str(target)}`.
9. Copy `bundle.result`.
10. Default `status` to `completed`.
11. Default `final_artifact` to a plain dictionary copied from the bundle.
12. Set `artifact_writes` to the ordered list, overriding any same-named bundle
    result value.
13. Emit `human_input_requested` when `human_notice` is non-empty.
14. Call `complete_runtime_step` when `step_id` is non-empty.
15. Apply optional `result_builder(context, result, **options)` and convert its
    result to a dictionary.

## Write semantics

| Kind | Behavior |
| --- | --- |
| `json` | Delegate to SDK `write_json(path, value)`. |
| `text` | Write `str(value)` as UTF-8 to a temporary sibling, then replace. |
| `bytes` | Convert with `bytes(value)`, write a temporary sibling, then replace. |

Text/byte temporary names include process ID and UUID. Parent directories are
created before those writes. Unsupported kinds raise `ValueError`.

Paths are joined with `Path(root) / artifact.path`. Version 1 does not enforce
relative or contained paths. Callers must provide trusted, normalized relative
paths and must reject untrusted traversal or absolute paths before composition.

## Atomicity and errors

Each individual text/byte replacement is atomic when supported by the
filesystem. The whole bundle is not transactional. Any compose, validation,
write, event, completion, or result-builder exception propagates immediately;
previous writes/events are not rolled back.

An `artifact_written` event must occur only after its target write succeeds.
The completion event must occur after all artifact and human-notice events.

## Invariants and non-goals

- Only declared `ArtifactWrite` values are written by this factory.
- Artifact schema and content are domain-owned.
- No overwrite prevention, cleanup, rollback, signing, upload, or approval wait
  is provided.
- Event ordering and `artifact_writes` ordering are compatibility invariants.

## Compatibility and required tests

Tests must cover all kinds and destinations, atomic replacement, invalid
bundle/kind/destination, ordered events and targets, partial failure behavior,
human notice, step completion, result defaults, and result-builder override.
Changing roots, ordering, result keys, or event names requires a new version.
