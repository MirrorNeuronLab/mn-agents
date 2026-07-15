# BEAM Module Agent

`mn-agents.module.beam_module@1` renders a generic BEAM module as a workflow
node. Use it when the runtime behavior is implemented in an Elixir/Erlang
module rather than a Python, Docker, or LLM worker.

The blueprint supplies the module name, bundled source path, and emitted
message type. The template standardizes the manifest shape.

## Manifest example

```json
{
  "node_id": "video_frame_tick_source",
  "uses": "mn-agents.module.beam_module@1",
  "with": {
    "module": "MirrorNeuron.Examples.TickSource",
    "module_source": "payloads/tick_source.ex",
    "emit_type": "tick_generated",
    "backpressure": {"max_in_flight": 1}
  }
}
```

## Required fields

- `module`: fully qualified BEAM module name;
- `module_source`: blueprint-relative source file packaged with the payload; and
- `emit_type`: workflow message type produced by the module.

Optional fields are `role`, `node_type`, `backpressure`, and `answer_node`.
Version 1 defines no stereotypes.

## Ownership boundary

This package does not compile, load, supervise, or call the BEAM module in
Python. The MirrorNeuron runtime owns execution. The module source owns payload
validation and message contents; the template owns only the common runtime
shape and declared lifecycle.

See [SPEC.md](SPEC.md) for exact defaults and behavior metadata.
