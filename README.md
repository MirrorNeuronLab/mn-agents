# MirrorNeuron Agents

Shared, versioned agent templates for MirrorNeuron blueprints.

An agent is the working unit in a MirrorNeuron workflow. Agents receive typed messages, do one bounded job, emit messages, events, or artifacts, and hand work to other agents through the graph. Some agents are deterministic workers, routers, reducers, stream listeners, services, or output adapters. Some agents call LLMs. Some LLM agents must run inside a sandbox, especially agents that create, inspect, or execute code.

The entries in this repository are generic agent templates, not final runtime agents. A blueprint actualizes a template into a customized agent by referencing it with `uses` and providing template-specific values with `with` and `config`. The workflow then assembles those actualized agents like reusable blocks.

MirrorNeuron is the runtime system that runs the workflow: it schedules actualized agents, moves messages between them, preserves run state, records events and artifacts, and enforces execution boundaries. The `mn-agents` library keeps template contracts reusable and testable while letting blueprints decide how the agents are orchestrated.

Blueprints can keep domain code and scenarios in `mn-blueprints` while referencing reusable agent-template wiring with `uses` and `with`. Renderers expand those references into concrete manifest nodes and preserve template provenance for auditability.

See [SPEC.md](SPEC.md) for the full contract.

## Control Agent Templates

Control templates shape the workflow: lifecycle, routing, retry, joins, gates, checkpoints, input/output fanout, and UI/service control.

| Template | Kind | Use |
| --- | --- | --- |
| `mn-agents.control_approval_gate` | `router` | Gates workflow progress on human or policy approval state. |
| `mn-agents.control_checkpoint` | `executor` | Records checkpoint and resume metadata for stateful workflows. |
| `mn-agents.control_input_listener` | `listener` | Listens to connector-backed input skills such as Drive, Slack, webhooks, sockets, or WebSockets. |
| `mn-agents.control_join` | `aggregator` | Completes a reduce/sink stage when configured messages arrive. |
| `mn-agents.control_lifecycle` | `router` | Emits workflow lifecycle messages such as start, stop, pause, and resume. |
| `mn-agents.control_message_filter` | `router` | Filters or gates messages using a declarative predicate name. |
| `mn-agents.control_output_fanout` | `executor` | Fans out output events or artifacts after mandatory local run-store writes. |
| `mn-agents.control_retry` | `router` | Routes retry decisions with bounded attempts and backoff metadata. |
| `mn-agents.control_router` | `router` | Emits or routes messages with optional state and backpressure config. |
| `mn-agents.control_tick_source` | `listener` | Produces stream or polling ticks for live and replayed workflows. |
| `mn-agents.control_web_output` | `service` | Exposes TCP/web UI output with primary and fallback ports. |

## Data Agent Templates

Data templates do the work: Python execution, native modules, LLM decisions/tools, observation, sandboxed code work, edge model inference, and services that process data.

| Template | Kind | Use |
| --- | --- | --- |
| `mn-agents.data_edge_model` | `executor` | Runs a local or edge model with declared device and resource profile. |
| `mn-agents.data_llm_decision` | `executor` | Runs an LLM-backed decision agent using named `LLM_CONFIG`. |
| `mn-agents.data_llm_tool` | `executor` | Runs an LLM-backed tool-using agent with declared tools. |
| `mn-agents.data_module` | `module` | Runs a native MirrorNeuron or BEAM module node. |
| `mn-agents.data_observer` | `executor` | Observes a stream, file, sensor, or service and emits normalized observations. |
| `mn-agents.data_openshell_service` | `service` | Runs a custom OpenShell service with explicit port and tunnel verification. |
| `mn-agents.data_python_executor` | `executor` | Runs a Python script with standard blueprint lifecycle wiring. |
| `mn-agents.data_python_workflow` | `executor` | Runs a generated Python workflow bundle worker with standard config/input/output handling. |
| `mn-agents.data_sandboxed_codegen` | `executor` | Runs code-generation or code-review work inside an explicit sandbox boundary. |

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

Simulate a single agent fixture without running MirrorNeuron:

```bash
python3 tools/simulate_agent.py data_python_executor/fixtures/minimal.instance.json
```
