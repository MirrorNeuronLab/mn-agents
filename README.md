# MirrorNeuron Agents

`mn-agents` is the shared, versioned catalog of MirrorNeuron runtime-node
templates and Python handler factories. Blueprints reuse these packages instead
of copying execution shape or orchestration mechanics.

Every package has:

- a `README.md` for selection, examples, and operational guidance;
- a `SPEC.md` for normative API, invariants, errors, and compatibility;
- packaged machine-readable metadata in `resources/agent.json`; and
- an exact version entry in `index.json`.

Read [SPEC.md](SPEC.md) before adding or changing an agent.

## Choose an agent

### Handler factories

Handler factories compose Python domain code. They do not render manifest
nodes.

| Agent | Use it for |
| --- | --- |
| [Stateful step](prototype_stateful_step_agent/README.md) | SDK lifecycle, workflow state, and prepared resources. |
| [Operation router](prototype_operation_router_agent/README.md) | Dispatching a named operation to an injected handler. |
| [Entity queue](prototype_entity_queue_agent/README.md) | Ordered finite processing with bounded thread parallelism. |
| [Bounded tool loop](prototype_bounded_tool_loop_agent/README.md) | Finite plan/action/observation execution. |
| [Actor review](prototype_actor_review_agent/README.md) | Review lifecycle, failure policy, and primary-handler wrapping. |
| [Artifact finalizer](prototype_artifact_finalizer_agent/README.md) | Declared final writes and artifact events. |
| [Stream processor](prototype_stream_processor_agent/README.md) | Sequential process/emit/checkpoint pipelines with retries. |
| [Supervised service](prototype_supervised_service_agent/README.md) | Blocking-service or repeated-cycle lifecycle and shutdown. |

### Runtime-node templates

Runtime-node templates are actualized in a blueprint manifest with an exact
`uses` reference.

| Agent | Use it for |
| --- | --- |
| [Python host worker](worker_python_host_agent/README.md) | Trusted host-local Python execution. |
| [Python Docker worker](worker_python_docker_agent/README.md) | Containerized Python and classified public browsing. |
| [LLM host worker](worker_llm_host_agent/README.md) | Host-local execution through a named LLM configuration. |
| [Message router](control_message_router_agent/README.md) | Workflow ingress and message routing shape. |
| [Terminal sink](control_terminal_sink_agent/README.md) | The final run-completion boundary. |
| [BEAM module](module_beam_module_agent/README.md) | A runtime node implemented by a BEAM module. |
| [OpenShell service](service_openshell_agent/README.md) | An image/port/tunnel-defined service dependency. |

## Typical composition

```text
manifest runtime node
  -> stateful_step
     -> operation_router
        -> entity_queue and/or bounded_tool_loop
     -> actor_review
     -> artifact_finalizer
  -> terminal_sink
```

Use only the layers a step needs. The blueprint retains domain queries,
formulas, prompts, schemas, and artifact composition.

## Validate changes

From the workspace root:

```bash
.venv/bin/python -m pytest -q mn-agents/tests
.venv/bin/ruff check mn-agents
```

Validate machine-readable package definitions through the SDK:

```bash
PYTHONPATH=mn-python-sdk .venv/bin/python -c \
  'from mn_sdk.blueprint_support import validate_agent_library; assert not validate_agent_library("mn-agents")'
```

## Repository paths

| Path | Purpose |
| --- | --- |
| `index.json` | Versioned catalog and package locations. |
| `*_agent/README.md` | Human-oriented usage guide. |
| `*_agent/SPEC.md` | Normative contract for coding agents and maintainers. |
| `*_agent/src/*/resources/agent.json` | Machine-readable identity and behavior. |
| `tests/` | Cross-agent composition and documentation checks. |
