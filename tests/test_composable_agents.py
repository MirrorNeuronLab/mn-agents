from __future__ import annotations

import json
import time
from pathlib import Path

from mn_prototype_actor_review_agent import ActorReviewSpec, create_agent as create_review, wrap_agent
from mn_prototype_artifact_finalizer_agent import (
    ArtifactBundle,
    ArtifactFinalizerSpec,
    ArtifactWrite,
    create_agent as create_finalizer,
)
from mn_prototype_bounded_tool_loop_agent import (
    ToolAction,
    ToolLoopSpec,
    ToolPlan,
    create_agent as create_tool_loop,
)
from mn_prototype_entity_queue_agent import EntityQueueSpec, create_agent as create_queue
from mn_prototype_operation_router_agent import OperationBinding, create_agent as create_router
from mn_prototype_stateful_step_agent import (
    AgentHandlerOutput,
    MessageAgentSpec,
    StatefulStepSpec,
    create_agent as create_stateful_step,
    create_message_agent,
)
from mn_sdk.step_runtime import StepContext


def test_entity_queue_resolves_workers_at_runtime_and_preserves_input_order():
    def process(_context, entity, **_options):
        time.sleep((4 - entity) * 0.002)
        return entity * 10

    queue = create_queue(
        EntityQueueSpec(
            load_entities=lambda _context, **_options: [1, 2, 3],
            process_entity=process,
            entity_id=str,
            max_workers=lambda _context, **_options: 3,
        )
    )

    result = queue({})

    assert [item["entity_id"] for item in result["outcomes"]] == ["1", "2", "3"]
    assert [item["value"] for item in result["outcomes"]] == [10, 20, 30]


def test_bounded_tool_loop_executes_multi_action_plan_and_honors_call_limit():
    executed = []
    loop = create_tool_loop(
        ToolLoopSpec(
            propose_action=lambda _context, _trace, **_options: ToolPlan(
                actions=(ToolAction("one"), ToolAction("two"), ToolAction("three")),
                metadata={"thought_summary": "batch"},
            ),
            execute_action=lambda _context, action, **_options: executed.append(action.name) or action.name,
            max_iterations=2,
            max_tool_calls=5,
        )
    )

    result = loop({}, max_tool_calls=2)

    assert executed == ["one", "two"]
    assert result["status"] == "partial"
    assert result["stop_reason"] == "tool_call_budget_exhausted"
    assert result["iterations"] == 1
    assert result["trace"][0]["plan_metadata"] == {"thought_summary": "batch"}


def test_bounded_tool_loop_allows_a_zero_call_budget():
    loop = create_tool_loop(
        ToolLoopSpec(
            propose_action=lambda _context, _trace: ToolAction("search"),
            execute_action=lambda _context, _action: None,
            max_iterations=2,
            max_tool_calls=0,
        )
    )

    result = loop({})

    assert result["status"] == "partial"
    assert result["stop_reason"] == "tool_call_budget_exhausted"
    assert result["tool_calls"] == 0


def test_actor_review_supports_dynamic_ids_warning_recovery_and_wrapping():
    persisted = []
    review = create_review(
        ActorReviewSpec(
            runner=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("offline")),
            actor_ids=lambda _context, **_options: ("reviewer",),
            failure_policy="warn",
            on_error=lambda _context, error, **_options: {
                "status": "completed_with_warnings",
                "findings": {"reviewer": {"error": str(error)}},
                "warnings": [{"message": str(error)}],
            },
            persist=lambda _context, result, **_options: persisted.append(result),
        )
    )
    wrapped = wrap_agent(lambda _context, **_options: {"value": 1}, review, result_key="review")

    result = wrapped({"config": {}})

    assert result["value"] == 1
    assert result["review"]["status"] == "completed_with_warnings"
    assert persisted[0].findings["reviewer"]["error"] == "offline"


def test_stateful_router_queue_composition_prepares_and_finalizes_resources(tmp_path):
    lifecycle = []
    queue = create_queue(
        EntityQueueSpec(
            load_entities=lambda _context, **_options: ["a", "b"],
            process_entity=lambda context, entity, *, prefix, **_options: (
                context.services["prepared"],
                f"{prefix}{entity}",
            ),
        )
    )
    router = create_router({"queue": OperationBinding(queue, {"prefix": "item-"})})
    stateful = create_stateful_step(
        StatefulStepSpec(
            context_factory=lambda **_kwargs: {
                "run_dir": tmp_path / "run",
                "output_folder": tmp_path / "output",
                "run_id": "run-1",
                "blueprint_id": "test-blueprint",
                "config": {},
            },
            prepare=lambda _context, **_options: {"prepared": True},
            finalize=lambda _context, result, error, **_options: lifecycle.append((result, error)),
        ),
        router,
    )

    result = stateful(StepContext(step_id="queue_step", run_id="run-1"), operation="queue")

    assert result["processed_count"] == 2
    assert result["outcomes"][0]["value"] == (True, "item-a")
    assert lifecycle[0][1] is None


def test_stateful_finalize_runs_after_handler_failure(tmp_path):
    lifecycle = []

    def fail(_context, **_options):
        raise RuntimeError("boom")

    stateful = create_stateful_step(
        StatefulStepSpec(
            context_factory=lambda **_kwargs: {
                "run_dir": tmp_path / "run",
                "output_folder": tmp_path / "output",
                "run_id": "run-1",
                "blueprint_id": "test-blueprint",
                "config": {},
            },
            finalize=lambda _context, result, error, **_options: lifecycle.append((result, error)),
        ),
        fail,
    )

    try:
        stateful(StepContext(step_id="failing_step", run_id="run-1"))
    except RuntimeError:
        pass

    assert str(lifecycle[0][1]) == "boom"


def test_stateful_finalize_runs_after_prepare_failure(tmp_path):
    lifecycle = []
    stateful = create_stateful_step(
        StatefulStepSpec(
            context_factory=lambda **_kwargs: {
                "run_dir": tmp_path / "run",
                "output_folder": tmp_path / "output",
                "run_id": "run-1",
                "blueprint_id": "test-blueprint",
                "config": {},
            },
            prepare=lambda _context, **_options: (_ for _ in ()).throw(RuntimeError("prepare failed")),
            finalize=lambda _context, result, error, **_options: lifecycle.append((result, error)),
        ),
        lambda _context, **_options: None,
    )

    try:
        stateful(StepContext(step_id="failing_prepare", run_id="run-1"))
    except RuntimeError:
        pass

    assert str(lifecycle[0][1]) == "prepare failed"


def test_stateful_step_forwards_runtime_root_and_llm_client(tmp_path):
    client = object()
    captured = {}

    def context_factory(*, inputs, config, runs_root, run_id):
        captured["runs_root"] = runs_root
        return {
            "run_dir": Path(runs_root) / str(run_id),
            "blueprint_id": "test-blueprint",
            "config": config or {},
            "run_id": run_id,
        }

    agent = create_stateful_step(
        StatefulStepSpec(context_factory=context_factory),
        lambda _context, *, llm_client=None: {
            "status": "completed",
            "same_client": llm_client is client,
        },
    )
    result = agent(
        StepContext(step_id="demo", run_id="run-1", message={}, config={}),
        inputs={},
        runs_root=tmp_path,
        llm_client=client,
    )
    assert captured["runs_root"] == tmp_path
    assert result["same_client"] is True


def test_message_agent_replays_durable_route_neutral_output(tmp_path):
    calls = []

    def handle(_context, *, agent_input, **_options):
        calls.append(agent_input.idempotency_key)
        return AgentHandlerOutput(
            payload={"value": len(calls)},
            artifacts=({"kind": "report", "path": "reports/result.json"},),
            metrics={"items": 1},
        )

    agent = create_message_agent(
        MessageAgentSpec(
            stateful=StatefulStepSpec(
                context_factory=lambda **_kwargs: {
                    "run_dir": tmp_path / "run-1",
                    "output_folder": tmp_path / "output",
                    "run_id": "run-1",
                    "blueprint_id": "test-blueprint",
                    "config": {},
                }
            ),
            input_resolver=lambda value: value.payload.get("step_input", {}),
        ),
        handle,
    )
    context = StepContext(
        step_id="collect",
        agent_id="collector",
        invocation_id="collect__collector",
        run_id="run-1",
        idempotency_key="run-1/collect__collector",
        message={"body": {"outputs": {"item": 1}}},
    )

    first = agent(context)
    replay = agent(context)

    assert first.outputs == {"value": 1}
    assert replay.outputs == {"value": 1}
    assert calls == ["run-1/collect__collector"]
    assert first.metrics == {"items": 1}
    assert {item["kind"] for item in first.artifacts} == {
        "report",
        "agent_result",
        "agent_idempotency_record",
    }
    assert (
        tmp_path
        / "run-1"
        / "workflow_state"
        / "collect__collector_result.json"
    ).exists()
    marker = json.loads(
        (
            tmp_path
            / "run-1"
            / "workflow_state"
            / "agent_invocations"
            / "collect__collector.json"
        ).read_text()
    )
    assert marker["result"]["payload"] == {"value": 1}


def test_artifact_finalizer_writes_declared_atomic_artifacts(tmp_path):
    context = {"run_dir": tmp_path / "run", "output_folder": tmp_path / "output"}
    finalizer = create_finalizer(
        ArtifactFinalizerSpec(
            compose=lambda _context, **_options: ArtifactBundle(
                final_artifact={"type": "demo"},
                writes=(
                    ArtifactWrite("result.json", {"ok": True}, destination="both"),
                    ArtifactWrite("notes.txt", "done", kind="text", destination="output"),
                ),
            )
        )
    )

    result = finalizer(context)

    assert (tmp_path / "run" / "result.json").exists()
    assert (tmp_path / "output" / "result.json").exists()
    assert (tmp_path / "output" / "notes.txt").read_text(encoding="utf-8") == "done"
    assert len(result["artifact_writes"]) == 3


def test_full_factory_composition_routes_queues_reviews_and_finalizes(tmp_path):
    tool_loop = create_tool_loop(
        ToolLoopSpec(
            propose_action=lambda _context, _trace, **_options: ToolPlan(
                actions=(ToolAction("inspect"),),
                stop_reason="evidence_collected",
            ),
            execute_action=lambda _context, action, **_options: {"tool": action.name, "ok": True},
            max_iterations=1,
            max_tool_calls=1,
        )
    )
    queue = create_queue(
        EntityQueueSpec(
            load_entities=lambda _context, **_options: ["first", "second"],
            process_entity=lambda _context, entity, **_options: {
                "entity": entity,
                "tool_loop": tool_loop({"entity": entity}),
            },
            max_workers=2,
        )
    )
    router = create_router({"process": queue})
    review = create_review(
        ActorReviewSpec(
            runner=lambda **kwargs: {
                "reviewer": {
                    "status": "reviewed",
                    "processed_count": kwargs["context"]["processed_count"],
                }
            },
            actor_ids=("reviewer",),
            build_context=lambda _context, *, primary_result, **_options: primary_result,
        )
    )
    reviewed_router = wrap_agent(router, review, result_key="review")

    def compose(context, **options):
        routed = reviewed_router(context, **options)
        return ArtifactBundle(
            final_artifact={"processed_count": routed["processed_count"]},
            writes=(ArtifactWrite("composition.json", routed, destination="both"),),
        )

    finalizer = create_finalizer(ArtifactFinalizerSpec(compose=compose))
    stateful = create_stateful_step(
        StatefulStepSpec(
            context_factory=lambda **_kwargs: {
                "run_dir": tmp_path / "run",
                "output_folder": tmp_path / "output",
                "run_id": "run-1",
                "blueprint_id": "test-blueprint",
                "config": {},
            }
        ),
        finalizer,
    )

    result = stateful(
        StepContext(step_id="composed", run_id="run-1"),
        operation="process",
    )

    assert result["final_artifact"] == {"processed_count": 2}
    assert (tmp_path / "run" / "composition.json").exists()
    payload = json.loads(
        (tmp_path / "output" / "composition.json").read_text(encoding="utf-8")
    )
    assert payload["review"]["findings"]["reviewer"]["status"] == "reviewed"
    assert [
        outcome["value"]["tool_loop"]["stop_reason"]
        for outcome in payload["outcomes"]
    ] == ["evidence_collected", "evidence_collected"]
