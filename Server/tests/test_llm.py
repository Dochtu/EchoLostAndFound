"""LLM adapter tests with a fake local transport (no network, no real key)."""

from __future__ import annotations

import asyncio
import json

import httpx
from fastapi.testclient import TestClient

from conftest import CONTENT_DIR, create_session, take_turn

from app.config import Settings
from app.content import load_content
from app.main import create_app
from app.providers.base import ProviderRequest
from app.providers.llm_provider import LlmProvider

FAKE_KEY = "test-key-not-a-real-secret"


def _generate(provider: LlmProvider, request: ProviderRequest):
    """Run one async generation and always release the HTTP client."""

    async def runner():
        try:
            return await provider.generate(request)
        finally:
            await provider.aclose()

    return asyncio.run(runner())


def _request(text: str = "那晚站台发生了什么") -> ProviderRequest:
    return ProviderRequest(
        request_id="req-llm-1",
        npc_id="npc_laozhou",
        display_name="老周",
        player_input=text,
        acquired_evidence_ids=("E01",),
        available_topic_ids=("opt.laozhou.ask_b01",),
        timeout_ms=1000,
        content_version="story-v1.0-phase2",
    )


def _settings(**overrides) -> Settings:
    values = dict(
        model_provider="llm",
        llm_base_url="https://llm.invalid/v1",
        llm_model="fake-model",
        llm_api_key=FAKE_KEY,
        allowed_origins=("http://localhost:8080",),
    )
    values.update(overrides)
    return Settings(**values)


def _chat_response(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": content}}]},
    )


def test_valid_reply_is_external_and_not_synthetic():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == f"Bearer {FAKE_KEY}"
        return _chat_response('{"npc_id": "npc_laozhou", "text": "灯还在里头。"}')

    provider = LlmProvider(_settings(), transport=httpx.MockTransport(handler))
    result = _generate(provider, _request())
    assert result.outcome == "completed"
    assert result.provider_kind == "external_model"
    assert result.is_synthetic is False
    assert result.text == "灯还在里头。"


def test_api_key_is_sent_only_in_authorization_header():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _chat_response('{"npc_id": "npc_laozhou", "text": "好。"}')

    provider = LlmProvider(_settings(), transport=httpx.MockTransport(handler))
    _generate(provider, _request())
    serialized = json.dumps(captured["body"], ensure_ascii=False)
    assert FAKE_KEY not in serialized
    assert "api_key" not in serialized.lower()
    assert "权限" not in serialized  # prompt carries rules, not credentials


def test_malformed_model_content_is_invalid_output():
    def handler(request: httpx.Request) -> httpx.Response:
        return _chat_response("这不是 JSON")

    provider = LlmProvider(_settings(), transport=httpx.MockTransport(handler))
    result = _generate(provider, _request())
    assert result.outcome == "invalid_output"
    assert result.provider_kind == "fallback"


def test_markup_is_unsafe_output():
    def handler(request: httpx.Request) -> httpx.Response:
        return _chat_response('{"npc_id": "npc_laozhou", "text": "<b>注意</b>"}')

    provider = LlmProvider(_settings(), transport=httpx.MockTransport(handler))
    result = _generate(provider, _request())
    assert result.outcome == "unsafe_output"


def test_upstream_500_becomes_model_unavailable_without_body_leak():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal detail with secret " + FAKE_KEY)

    provider = LlmProvider(_settings(), transport=httpx.MockTransport(handler))
    result = _generate(provider, _request())
    assert result.outcome == "model_unavailable"
    assert result.failure_detail == "upstream_status_500"
    assert FAKE_KEY not in (result.failure_detail or "")


def test_upstream_timeout_becomes_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated timeout")

    provider = LlmProvider(_settings(), transport=httpx.MockTransport(handler))
    result = _generate(provider, _request())
    assert result.outcome == "timeout"


def test_unconfigured_provider_reports_unavailable():
    provider = LlmProvider(Settings())
    assert provider.available is False
    result = _generate(provider, _request())
    assert result.outcome == "model_unavailable"
    assert result.failure_detail == "llm_not_configured"


def test_app_uses_llm_provider_end_to_end_without_leaking_key():
    settings = _settings()
    transport = httpx.MockTransport(
        lambda request: _chat_response(
            '{"npc_id": "npc_laozhou", "text": "那晚的事，你自己也看见了。"}'
        )
    )
    provider = LlmProvider(settings, transport=transport)
    app = create_app(settings, provider=provider, content=load_content(CONTENT_DIR))
    with TestClient(app) as client:
        conversation_id = create_session(client, "npc_laozhou")
        turn = take_turn(client, conversation_id, text="那晚站台发生了什么")
    assert turn["source"] == "external_model"
    assert turn["provider"]["kind"] == "external_model"
    assert turn["provider"]["is_synthetic"] is False
    assert turn["generated_bridge"] == "那晚的事，你自己也看见了。"
    assert FAKE_KEY not in json.dumps(turn, ensure_ascii=False)
