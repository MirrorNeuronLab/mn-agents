from __future__ import annotations

import json
from pathlib import Path

import pytest

from mn_prototype_actor_review_agent.actors import (
    actor_findings,
    actor_generate_json,
    emit_actor_activity,
    get_actor_llm_client,
    llm_usage,
    record_actor_finding,
    resolve_actor_specs,
)
from mn_sdk.llm import FakeLLMClient


def _config() -> dict:
    return {
        "llm": {
            "enabled": True,
            "mode": "fake",
            "mock_mode": "fake",
            "model": "default",
            "default_config": "primary",
            "responsibilities": ["Keep deterministic outputs as source of truth."],
            "agents": {
                "review_actor": {
                    "llm_config": "primary",
                    "model": "default",
                    "role": "Review actor",
                    "responsibilities": [
                        "Review evidence.",
                        "Summarize risks.",
                        "Keep the packet review-only.",
                    ],
                }
            },
        }
    }


def test_resolve_actor_specs_and_fake_actor_call() -> None:
    llm = FakeLLMClient()
    finding = actor_generate_json(
        llm,
        _config(),
        "review_actor",
        task="Review packet.",
        context={"record_count": 2},
        fallback={"summary": "Reviewed packet.", "confidence": 0.8},
    )

    assert llm.calls == 1
    assert finding["actor_id"] == "review_actor"
    assert finding["role"] == "Review actor"
    assert finding["provider"] == "fake"
    assert "Review evidence." in llm.prompts[0]["system"]
    assert resolve_actor_specs(_config())["review_actor"]["role"] == "Review actor"


def test_actor_call_falls_back_and_tracks_usage() -> None:
    class FailingLLM:
        provider = "test"
        model = "broken"
        calls = 0
        fallback_calls = 0

        def generate_json(self, *, system_prompt, user_prompt, fallback):
            self.calls += 1
            raise RuntimeError("offline")

    llm = FailingLLM()
    finding = actor_generate_json(
        llm,
        _config(),
        "review_actor",
        task="Review packet.",
        context={"record_count": 1},
        fallback={"summary": "Fallback review.", "confidence": 0.4},
    )

    assert finding["summary"] == "Fallback review."
    assert llm_usage(llm)["calls"] == 1
    assert llm_usage(llm)["fallback_calls"] == 1


def test_actor_call_fails_closed_when_live_response_is_required() -> None:
    class FailingStrictLLM:
        provider = "test"
        model = "broken"
        calls = 0
        fallback_calls = 0
        strict = True

        def generate_json(self, *, system_prompt, user_prompt, fallback):
            self.calls += 1
            raise RuntimeError("offline")

    with pytest.raises(RuntimeError, match="offline"):
        actor_generate_json(
            FailingStrictLLM(),
            _config(),
            "review_actor",
            task="Review packet.",
            context={"record_count": 1},
            fallback={"summary": "Fallback review.", "confidence": 0.4},
        )


def test_actor_factory_keeps_live_requirement_separate_from_strict_json(monkeypatch) -> None:
    monkeypatch.setenv("MN_LLM_PROVIDER", "docker_model_runner")
    monkeypatch.setenv("MN_LLM_MODEL", "default")
    config = _config()
    config["llm"].update({"mode": "live", "require_live": True})

    client = get_actor_llm_client(config)

    assert client.strict is False

    config["llm"]["strict_json"] = True

    assert get_actor_llm_client(config).strict is True


def test_llm_usage_includes_token_totals() -> None:
    class UsageLLM:
        provider = "docker_model_runner"
        model = "ai/nemotron3:latest"
        calls = 2
        fallback_calls = 0
        input_tokens = 15
        output_tokens = 5
        total_tokens = 20
        estimated_tokens = 0
        last_usage = {"total_tokens": 10, "estimated": False}

    usage = llm_usage(UsageLLM())

    assert usage["total_tokens"] == 20
    assert usage["input_tokens"] == 15
    assert usage["last_usage"]["total_tokens"] == 10


def test_actor_findings_and_redacted_activity_events(tmp_path: Path) -> None:
    state: dict = {}
    record_actor_finding(state, "review_actor", {"summary": "ok"})
    emit_actor_activity(
        tmp_path,
        "review_actor",
        message="Reviewed sensitive packet",
        result_summary="Account 4111 1111 1111 1111 was present.",
        details={"api_key": "secret-token", "public": "safe"},
    )

    assert actor_findings(state) == {"review_actor": {"summary": "ok"}}
    record = json.loads((tmp_path / "events.jsonl").read_text().splitlines()[0])
    payload = record["payload"]
    assert payload["agent_id"] == "review_actor"
    assert payload["details"]["api_key"] == "[REDACTED]"
    assert "[REDACTED-NUMBER]" in payload["result_summary"]
