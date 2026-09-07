import pytest
from mn_prototype_bounded_tool_loop_agent.checkpoint import CheckpointLoop


def action(name="plan_enquiry", **args):
    return {"name": name, "arguments": args, "reason": "test"}


def test_identical_invalid_plan_stops_after_one_corrective_decision(tmp_path):
    loop = CheckpointLoop(tmp_path / "state.json", {}, max_decisions=5000)
    events = []
    state = loop.run(
        lambda s: action(),
        lambda a, s: pytest.fail("invalid action dispatched"),
        allowed_actions=lambda s: ["read_skill"],
        event_sink=events.append,
    )
    assert len(state["records"]) == 4
    assert state["stop_reason"] == "investigation_stalled"
    assert [e["type"] for e in events] == ["agent_recovery_started", "agent_stalled"]


def test_valid_recovery_and_progress_continue(tmp_path):
    loop = CheckpointLoop(tmp_path / "state.json", {})
    choices = iter([action()] * 3 + [action("read_skill"), action("finish")])
    state = loop.run(
        lambda s: next(choices),
        lambda a, s: {"manual": "read"},
        allowed_actions=lambda s: ["read_skill", "finish"],
    )
    assert state["stop_reason"] == "completed"
    assert state["progress_guard"]["recovery"] is None


def test_no_progress_has_two_recovery_decisions(tmp_path):
    loop = CheckpointLoop(tmp_path / "state.json", {})
    state = loop.run(
        lambda s: action("noise", id=len(s["records"])),
        lambda a, s: {},
        progress=lambda s: [],
    )
    assert len(state["records"]) == 14
    assert state["stop_reason"] == "investigation_stalled"


def test_recovery_counter_survives_crash_resume(tmp_path):
    path = tmp_path / "state.json"
    loop = CheckpointLoop(path, {})

    def propose(state):
        if len(state["records"]) == 3:
            raise SystemExit("crash")
        return action()

    with pytest.raises(SystemExit):
        loop.run(propose, lambda a, s: {}, allowed_actions=lambda s: [])
    resumed = CheckpointLoop(path, {})
    state = resumed.run(
        lambda s: action(), lambda a, s: {}, allowed_actions=lambda s: []
    )
    assert len(state["records"]) == 4
    assert state["stop_reason"] == "investigation_stalled"
