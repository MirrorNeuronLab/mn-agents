# Wasmtime worker contract

`mn-agents.worker.wasmtime@1` renders one executor with `MirrorNeuron.Runner.Wasmtime`. The data template accepts `wasm_component`, optional `wasm_inputs`, `wasm_config` and `wit_skills`. Core stages the component and exposes a private `/job` directory. For supervised workflow steps, the command emits live agent beacons as work advances.

The Python package exports `create_agent` and `load_agent_definition`. Their output is determined solely by the packaged definition and supplied instance. `fixtures/rendered.node.json` records the minimal instance after expansion.

## Identity

The registry ID is `mn-agents.worker.wasmtime@1`. Its Python distribution publishes the agent template through the `mn.agents` entry point. Core executes the WebAssembly component on the selected node. A Rust command built for `wasm32-wasip3` can consume the invocation through the WASI 0.3 CLI world.

## Inputs and results

The template requires a relative `.wasm` component path in the blueprint payloads. A skill record supplies its exact version, contained payload path, and SHA-256. Submission validates those bytes before linking them into the command and staging the content-addressed output. A standalone component may select an empty list of skills. Workflow bindings specify the operation name and input mappings. `wasm_config` carries JSON values for that invocation. Local source input requires a separate `wasm_inputs` binding.

The command may emit an SDK result with `outputs`, `artifacts`, `metrics`, and `status`. A nonzero exit code fails the invocation. Core enforces the component memory ceiling and command time and output budgets. An application that needs durable storage commits results through an authorized workflow boundary. Restarting the component creates a fresh private invocation directory.

## Compatibility

Version 1 requires a component-model binary and an executor with a WASI 0.3-capable Wasmtime CLI. Application interfaces have their own WIT package identities. Changing the name or incompatible signature of an imported interface requires a corresponding change to the consuming command and an updated dependency pin. The Python template version describes the shape of the rendered Core node independently of Rust build tooling.

## Required tests

Render the minimal fixture and compare it to the checked-in node. Check that a missing component path is rejected by the template. Exercise a linked Rust command through the Core runner, verify success and failing exit statuses, and validate that host environment and unstaged files are inaccessible from the guest.
