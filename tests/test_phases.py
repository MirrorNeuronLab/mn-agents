import pytest
from mn_prototype_bounded_tool_loop_agent.phases import PhaseCycle
from mn_prototype_bounded_tool_loop_agent.checkpoint import CheckpointLoop


def test_phase_resume_and_tool_review_boundary():
    data = {}
    cycle = PhaseCycle(data, max_actions=1)
    with pytest.raises(ValueError):
        cycle.require_execution()
    cycle.start({"question": "test"})
    cycle.require_execution()
    cycle.attempted()
    resumed = PhaseCycle(data, max_actions=1)
    with pytest.raises(ValueError):
        resumed.require_execution()
    resumed.review({"finding": "test"})
    assert resumed.phase == "planning"
    assert resumed.state["plans"] == [{"question": "test"}]


def test_no_deadline_and_early_finish_without_repeat(tmp_path):
    loop = CheckpointLoop(
        tmp_path / "state.json",
        {},
        max_decisions=5000,
        max_invocations=5000,
        seconds=None,
    )
    action = {"name": "finish", "arguments": {}, "reason": "Enough evidence"}
    assert loop.run(lambda s: action, lambda a, s: {})["stop_reason"] == "completed"
    resumed = CheckpointLoop(
        tmp_path / "state.json",
        {},
        max_decisions=5000,
        max_invocations=5000,
        seconds=None,
    )
    resumed.run(
        lambda s: pytest.fail("repeated model"),
        lambda a, s: pytest.fail("repeated tool"),
    )
    assert len(resumed.state["records"]) == 1


def test_tool_budget_leaves_finalization_decisions(tmp_path):
    loop = CheckpointLoop(
        tmp_path / "state.json",
        {},
        max_decisions=8,
        max_invocations=1,
        seconds=None,
        finalization_decisions=2,
    )
    actions = iter(["invoke_skill", "invoke_skill", "finish"])
    calls = []
    state = loop.run(
        lambda s: {"name": next(actions), "arguments": {}, "reason": "test"},
        lambda a, s: calls.append(a["name"]) or {},
    )
    assert calls == ["invoke_skill", "finish"]
    assert "error" in state["records"][1]["result"]
    assert state["stop_reason"] == "completed"
