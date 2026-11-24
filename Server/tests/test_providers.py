"""Mock provider behaviour through the HTTP surface (fallbacks are successful
turn results, never fake model successes)."""

from __future__ import annotations

import dataclasses

from conftest import build_client, create_session, take_turn

from app.providers.mock_provider import MockAiProvider


def _app_with_provider(content, scenarios, provider):
    return build_client(content, scenarios, provider=provider)


def test_mock_completed_reply_is_labelled_synthetic(client):
    conversation_id = create_session(
        client, "npc_laozhou", evidence=("E01", "E02")
    )
    turn = take_turn(client, conversation_id, text="那天站台到底出了什么事")
    assert turn["source"] == "mock"
    assert turn["generated_bridge"] == "（模拟回复·仅测试，非正式台词）两样东西都把时间对上了。"
    assert turn["provider"] == {
        "kind": "mock",
        "id": "mock-deterministic",
        "is_synthetic": True,
    }
    assert turn["fallback_reason"] is None
    assert turn["fixed_segments"] == []


def test_mock_reply_is_deterministic(client):
    conversation_id = create_session(client, "npc_laozhou", evidence=("E01", "E02"))
    first = take_turn(client, conversation_id, text="那天夜里的事")
    second = take_turn(client, conversation_id, text="那天夜里的事")
    assert first["generated_bridge"] == second["generated_bridge"]
    assert first["provider"] == second["provider"]


def test_timeout_fixture_returns_fallback_timeout(client):
    conversation_id = create_session(client, "npc_laozhou")
    turn = take_turn(client, conversation_id, text="超时测试")
    assert turn["source"] == "fallback"
    assert turn["fallback_reason"] == "timeout"
    assert turn["generated_bridge"] is None
    assert turn["provider"]["kind"] == "fallback"


def test_transport_error_fixture_returns_model_unavailable(client):
    conversation_id = create_session(client, "npc_laozhou")
    turn = take_turn(client, conversation_id, text="错误测试")
    assert turn["fallback_reason"] == "model_unavailable"


def test_invalid_fixture_returns_invalid_output(client):
    conversation_id = create_session(client, "npc_laozhou")
    turn = take_turn(client, conversation_id, text="坏输出测试")
    assert turn["fallback_reason"] == "invalid_output"


def test_unsafe_fixture_returns_unsafe_output(client):
    conversation_id = create_session(client, "npc_laozhou")
    turn = take_turn(client, conversation_id, text="不安全测试")
    assert turn["fallback_reason"] == "unsafe_output"


def test_unknown_input_falls_back_to_unknown_intent(client):
    conversation_id = create_session(client, "npc_laozhou")
    turn = take_turn(client, conversation_id, text="今天天气不错")
    assert turn["fallback_reason"] == "unknown_intent"


def test_approved_fixed_input_never_calls_the_model(content, scenarios):
    class ExplodingProvider:
        provider_id = "explode"
        kind = "fallback"
        is_synthetic = True
        available = False

        async def generate(self, request):  # pragma: no cover - must never run
            raise AssertionError("the model must not be called for approved fixed input")

    with _app_with_provider(content, scenarios, ExplodingProvider()) as guarded:
        conversation_id = create_session(guarded, "npc_laozhou")
        turn = take_turn(guarded, conversation_id, text="灯")
        assert turn["source"] == "fixed_line"
        assert turn["fixed_segments"][0]["text"].startswith("站台那晚")


def test_content_version_mismatch_falls_back(content, scenarios):
    stale = dataclasses.replace(scenarios, content_version="story-v0.9")
    with _app_with_provider(content, scenarios, MockAiProvider(stale)) as stale_client:
        conversation_id = create_session(stale_client, "npc_laozhou")
        turn = take_turn(stale_client, conversation_id, text="今天天气不错")
        assert turn["fallback_reason"] == "model_unavailable"


def test_reserved_npc_is_not_reachable_by_text(client):
    # npc_xucheng is chapter-reserved; the server refuses the session outright.
    response = client.post("/api/v1/sessions", json={"npc_id": "npc_xucheng"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
