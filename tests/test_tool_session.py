import pytest
from mn_prototype_bounded_tool_loop_agent.session import ToolSession, ToolRegistry, GeneratedCodePolicy, execute_generated_python

def test_registry_and_session_record_on_demand_tools_and_code(tmp_path):
    registry = ToolRegistry({"rank"})
    registry.register("rank", lambda arguments: sorted(arguments["values"]))
    session = ToolSession(
        {"goal_id": "rank", "objective": "Rank candidates"},
        registry,
        tmp_path,
        prompt_factory=lambda goal, **kw: {"prompt_id": "rank-prompt", **kw},
        max_tool_calls=1,
    )
    session.create_prompt(phase="rank", instructions=["Rank candidates"])
    assert session.use_tool("rank", {"values": [3, 1, 2]}) == [1, 2, 3]
    result = session.execute_python("import json\nprint(json.loads(input()))\n", input_payload={"value": 2})
    assert result["status"] == "completed"
    assert session.snapshot()["tool_calls_used"] == 1
    with pytest.raises(RuntimeError, match="budget"):
        session.use_tool("rank", {"values": []})


def test_generated_python_rejects_unsafe_imports(tmp_path):
    with pytest.raises(ValueError, match="not allowed"):
        execute_generated_python("import subprocess\n", workspace=tmp_path)

    result = execute_generated_python(
        "while True:\n    pass\n",
        workspace=tmp_path,
        policy=GeneratedCodePolicy(timeout_seconds=1),
    )
    assert result["status"] in {"failed", "timed_out"}


def test_generated_output_is_bounded_while_child_is_running(tmp_path):
    result = execute_generated_python(
        "for index in range(10000):\n    print('x' * 1000)\n",
        workspace=tmp_path, policy=GeneratedCodePolicy(max_output_chars=80),
    )
    assert result["status"] == "completed"
    assert len(result["stdout"]) == 80
    assert result["stdout_truncated"] is True
    assert result["stderr"] == ""


def test_timeout_output_remains_text_and_policy_is_validated(tmp_path):
    result = execute_generated_python("print('hello', flush=True)\nwhile True: pass", workspace=tmp_path,
                                      policy=GeneratedCodePolicy(timeout_seconds=1))
    assert result["status"] in {"failed", "timed_out"}
    assert isinstance(result["stdout"], str)
    assert "hello" in result["stdout"]
    with pytest.raises(ValueError):
        GeneratedCodePolicy(timeout_seconds=0)
    with pytest.raises(ValueError):
        GeneratedCodePolicy(max_output_chars=-1)


def test_session_uses_shared_loop_and_remaining_tool_budget(tmp_path):
    from mn_prototype_bounded_tool_loop_agent import ToolAction
    registry = ToolRegistry({"rank"})
    registry.register("rank", lambda arguments: sorted(arguments["values"]))
    session = ToolSession({}, registry, tmp_path, prompt_factory=lambda *args, **kw: {}, max_tool_calls=2)
    session.use_tool("rank", {"values": [2, 1]})
    result = session.run(lambda context, trace: ToolAction("rank", {"values": [3, 2]}))
    assert result["stop_reason"] == "tool_call_budget_exhausted"
    assert result["tool_calls"] == 1
    assert session.snapshot()["tool_calls_used"] == 2
