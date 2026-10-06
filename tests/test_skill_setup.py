"""Only admitted, validated distributions may prepare local dependencies."""

from types import SimpleNamespace

import pytest
from mn_prototype_bounded_tool_loop_agent import skills
from mn_prototype_bounded_tool_loop_agent.skills import SkillRuntime


def descriptor():
    return {"id": "example.skill", "module": "example", "description": "Test",
            "operations": {"read": {"arguments": {"type": "object"}}}}


def distribution(hooks=()):
    return SimpleNamespace(entry_points=[SimpleNamespace(group="mn.skills", load=lambda: descriptor), *hooks],
                           metadata={"Name": "example-package"}, version="1")


def hook(callback):
    return SimpleNamespace(group="mn.skills.setup", load=lambda: callback)


def test_only_admitted_packages_run_setup_once(monkeypatch):
    calls = []
    def setup(request):
        calls.append(request)
        return {"version": 1, "status": "installed"}
    def lookup(name):
        assert name == "example-package"
        return distribution([hook(setup)])
    monkeypatch.setattr(skills.metadata, "distribution", lookup)
    runtime = SkillRuntime.discover(["example-package", "example-package"], {("example.skill", "read"): lambda: {}})
    assert calls == [{"version": 1, "allow_install": True}]
    assert runtime.preparation["example-package"]["status"] == "installed"
    runtime.read_hashes["example.skill"] = "test"
    runtime.invoke_skill("example.skill", "read", {})
    assert len(calls) == 1


def test_offline_registration_requests_check_only(monkeypatch):
    calls = []
    monkeypatch.setattr(skills.metadata, "distribution", lambda name: distribution([
        hook(lambda request: calls.append(request) or {"version": 1, "status": "ready"})]))
    SkillRuntime.discover(["example-package"], {}, install_dependencies=False)
    assert calls == [{"version": 1, "allow_install": False}]


@pytest.mark.parametrize("error", ["binding", "schema", "duplicate", "hooks"])
def test_all_contracts_validate_before_setup(monkeypatch, error):
    entry = hook(lambda request: pytest.fail("invalid admission ran setup"))
    dist = distribution([entry])
    bindings = {}
    if error == "binding":
        bindings = {("missing", "read"): lambda: {}}
    elif error == "schema":
        dist.entry_points[0].load = lambda: lambda: {**descriptor(), "operations": {"read": {"arguments": {"type": "invalid"}}}}
    elif error == "duplicate":
        dist.entry_points.append(dist.entry_points[0])
    else:
        dist.entry_points.append(entry)
    monkeypatch.setattr(skills.metadata, "distribution", lambda name: dist)
    with pytest.raises(Exception):
        SkillRuntime.discover(["example-package"], bindings)


@pytest.mark.parametrize("result", [None, {}, {"version": 2, "status": "ready"}, {"version": 1, "status": "failed"}])
def test_failed_setup_prevents_registration(monkeypatch, result):
    monkeypatch.setattr(skills.metadata, "distribution", lambda name: distribution([hook(lambda request: result)]))
    with pytest.raises(ValueError, match="did not complete"):
        SkillRuntime.discover(["example-package"], {})


def test_setup_exception_propagates_and_unhooked_packages_still_work(monkeypatch):
    def fail(request):
        raise RuntimeError("download failed")
    monkeypatch.setattr(skills.metadata, "distribution", lambda name: distribution([hook(fail)]))
    with pytest.raises(RuntimeError, match="download failed"):
        SkillRuntime.discover(["example-package"], {})
    monkeypatch.setattr(skills.metadata, "distribution", lambda name: distribution())
    assert SkillRuntime.discover(["example-package"], {}).preparation == {}
