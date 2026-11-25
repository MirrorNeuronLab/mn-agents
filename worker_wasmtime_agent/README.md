# Wasmtime worker

The `mn-agents.worker.wasmtime@1` runtime-node template creates a Core executor for a WASI 0.3 command component. Install the `mn-worker-wasmtime-agent` distribution on the authoring host. The executor needs Wasmtime with Preview 3 enabled. Point `wasm_component` at a bundle-relative binary and list imported skill names in `wit_skills`. Include each selected component with its SHA-256 in the blueprint dependencies.

The component reads `/job/mirror_neuron_input.json` and `/job/config.json`. It writes an SDK step-result JSON object to stdout. The fixture under `fixtures/minimal.instance.json` shows the source node.

A blueprint can use a WIT binding in its agent registry, such as `{"wit":"inspect"}`. The SDK puts the selected operation into the component configuration and links the declared skill interfaces during submission. For a supervised workflow the guest reports advancing progress with the standard agent beacon on stdout. Core owns cancellation and enforces the invocation deadline.

The executable reads ordinary WASI files. A local folder must first be staged into the bundle and explicitly selected with `wasm_inputs` before it becomes visible at `/job/inputs`. Changes to that private copy last for one invocation. See [SPEC.md](SPEC.md) for the result envelope and error behavior.
