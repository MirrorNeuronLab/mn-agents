import pytest
from jsonschema import ValidationError
from mn_prototype_bounded_tool_loop_agent import skills as skills_module
from mn_prototype_bounded_tool_loop_agent.checkpoint import CheckpointLoop
from mn_prototype_bounded_tool_loop_agent.skills import SkillRuntime

SKILL = "example.reading"


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    manual = tmp_path / "resources"
    manual.mkdir()
    (manual / "SKILL.md").write_text("Read the scoped lexical evidence before answering.")
    monkeypatch.setattr(skills_module.resources, "files", lambda module: tmp_path)
    schema = {"type": "object", "required": ["query"], "additionalProperties": False,
              "properties": {"query": {"type": "string", "minLength": 1},
                             "top_k": {"type": "integer", "minimum": 1, "maximum": 20}}}
    descriptor = {"id": SKILL, "module": "example", "description": "Scoped evidence",
                  "operations": {"search": {"arguments": schema}}}
    direct = lambda query, top_k=3: {"passages": [{"evidence_id": "one", "query": query}], "limit": top_k}
    return direct, SkillRuntime([descriptor], {(SKILL, "search"): direct})


def test_manual_and_dual_use(runtime):
    direct, skills = runtime
    with pytest.raises(ValueError, match="read_skill"):
        skills.invoke_skill(SKILL, "search", {"query": "cybersecurity"})
    manual = skills.read_skill(SKILL)
    assert "lexical" in manual["manual"] and len(manual["sha256"]) == 64
    result = skills.invoke_skill(SKILL, "search", {"query": "cybersecurity", "top_k": 3})
    assert result == direct("cybersecurity", 3)
    assert skills.list_skills()[0]["id"] == SKILL


@pytest.mark.parametrize("args", [
    {"query": "a", "path": "/etc/passwd"}, {"query": "a", "top_k": True},
    {"query": "a", "top_k": 21}, {"query": ""},
])
def test_invalid_arguments(runtime, args):
    _, skills = runtime
    skills.read_skill(SKILL)
    with pytest.raises(ValidationError):
        skills.invoke_skill(SKILL, "search", args)


def test_registration_boundaries(runtime):
    _, skills = runtime
    skills.read_skill(SKILL)
    with pytest.raises(ValueError):
        skills.invoke_skill(SKILL, "create", {})
    with pytest.raises(KeyError):
        skills.read_skill("uninstalled")
    skills.max_output_bytes = 5
    with pytest.raises(ValueError, match="byte limit"):
        skills.invoke_skill(SKILL, "search", {"query": "approval"})


def action(name="invoke_skill"):
    return {"name": name, "arguments": {}, "reason": "test enquiry"}


def test_checkpoint_replays_completed_calls_and_rejects_changed_binding(tmp_path):
    path = tmp_path / "state.json"
    calls = []
    loop = CheckpointLoop(path, {"snapshot": "a"})

    def propose(state):
        if state["records"]:
            raise KeyboardInterrupt()
        return action()

    with pytest.raises(KeyboardInterrupt):
        loop.run(propose, lambda a, s: calls.append(a) or {"answer": 1})
    loop = CheckpointLoop(path, {"snapshot": "a"})
    loop.run(lambda s: action("finish"), lambda a, s: {})
    assert len(calls) == 1 and loop.state["stop_reason"] == "completed"
    loop.run(
        lambda s: pytest.fail("replayed model"), lambda *a: pytest.fail("replayed tool")
    )
    with pytest.raises(ValueError, match="binding mismatch"):
        CheckpointLoop(path, {"snapshot": "b"})


def test_pending_decision_is_not_requested_twice(tmp_path):
    path = tmp_path / "state.json"
    loop = CheckpointLoop(path, {})
    with pytest.raises(KeyboardInterrupt):
        loop.run(
            lambda s: action(), lambda *a: (_ for _ in ()).throw(KeyboardInterrupt())
        )
    assert len(loop.state["records"]) == 1 and "result" not in loop.state["records"][0]
    resumed = CheckpointLoop(path, {})
    resumed.run(lambda s: action("finish"), lambda *a: {"ok": True})
    assert resumed.state["records"][0]["result"] == {"ok": True}


def test_limits_failures_invalid_responses_and_cancellation(tmp_path):
    loop = CheckpointLoop(tmp_path / "calls.json", {}, max_invocations=2)
    state = loop.run(
        lambda s: action(), lambda *a: (_ for _ in ()).throw(ValueError("unavailable"))
    )
    assert state["stop_reason"] == "tool_call_budget_exhausted"
    assert len(state["records"]) == 2 and all(
        "error" in r["result"] for r in state["records"]
    )
    loop = CheckpointLoop(tmp_path / "invalid.json", {}, max_decisions=2)
    assert (
        loop.run(lambda s: {}, lambda *a: None)["stop_reason"]
        == "iteration_limit_exhausted"
    )
    loop = CheckpointLoop(tmp_path / "cancel.json", {})
    assert (
        loop.run(lambda s: pytest.fail(), lambda *a: None, cancelled=lambda: True)[
            "stop_reason"
        ]
        == "cancelled"
    )


def test_blocking_call_obeys_deadline(tmp_path):
    import time

    loop = CheckpointLoop(tmp_path / "time.json", {}, seconds=1)
    start = time.monotonic()
    state = loop.run(lambda s: action(), lambda *a: time.sleep(10))
    assert state["stop_reason"] == "time_budget_exhausted"
    assert time.monotonic() - start < 3
