import hashlib

import pytest
from jsonschema import ValidationError
from mn_prototype_bounded_tool_loop_agent.skills import SkillRuntime
from mn_prototype_bounded_tool_loop_agent.checkpoint import CheckpointLoop
from mn_document_reading_skill.search import PassageIndex
from mn_document_reading_skill import extract_outline

DOC = "mirrorneuron.document.reading"
DIST = "mirrorneuron-document-reading-skill"


def runtime(tmp_path):
    text = "Cybersecurity approval. Routine cybersecurity responsibilities."
    index = PassageIndex.build(
        tmp_path / "index.db",
        [
            dict(
                source_id="one",
                text=text,
                access_scope="case",
                content_sha256=hashlib.sha256(text.encode()).hexdigest(),
            )
        ],
        "case",
    )
    return index, SkillRuntime.discover(
        [DIST],
        {
            (DOC, "search"): index.search,
            (DOC, "passage"): index.passage,
            (DOC, "outline"): extract_outline,
        },
    )


def test_manual_and_dual_use(tmp_path):
    index, skills = runtime(tmp_path)
    with pytest.raises(ValueError, match="read_skill"):
        skills.invoke_skill(DOC, "search", {"query": "cybersecurity"})
    manual = skills.read_skill(DOC)
    assert "lexical" in manual["manual"] and len(manual["sha256"]) == 64
    result = skills.invoke_skill(DOC, "search", {"query": "cybersecurity", "top_k": 3})
    assert result == index.search("cybersecurity", 3)
    eid = result["passages"][0]["evidence_id"]
    assert skills.invoke_skill(DOC, "passage", {"evidence_id": eid}) == index.passage(
        eid
    )
    assert skills.invoke_skill(
        DOC, "outline", {"text": "# Example"}
    ) == extract_outline("# Example")
    assert skills.list_skills()[0]["id"] == DOC


@pytest.mark.parametrize(
    "args",
    [
        {"query": "a", "path": "/etc/passwd"},
        {"query": "a", "top_k": True},
        {"query": "a", "top_k": 21},
        {"query": ""},
    ],
)
def test_invalid_arguments(tmp_path, args):
    _, skills = runtime(tmp_path)
    skills.read_skill(DOC)
    with pytest.raises(ValidationError):
        skills.invoke_skill(DOC, "search", args)


def test_discovery_and_registration_boundaries(tmp_path):
    _, skills = runtime(tmp_path)
    skills.read_skill(DOC)
    with pytest.raises(ValueError):
        skills.invoke_skill(DOC, "create", {})
    with pytest.raises(KeyError):
        skills.read_skill("uninstalled")
    with pytest.raises(ValueError, match="descriptor"):
        SkillRuntime.discover(["mn-prototype-bounded-tool-loop-agent"], {})
    skills.max_output_bytes = 5
    with pytest.raises(ValueError, match="byte limit"):
        skills.invoke_skill(DOC, "search", {"query": "approval"})


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
