"""Async model calls must not block the event loop (M4-C C1.2).

The pre-M4-C provider used ``httpx.Client`` inside an ``async def`` route, so a
single slow model call froze *every* conversation on the instance.  These tests
drive the real ASGI app through ``httpx.ASGITransport`` and prove that a slow
call only delays its own request.
"""

from __future__ import annotations

import asyncio
import time

import httpx

from conftest import make_settings

from app.budget import RequestBudget
from app.content import load_content
from app.main import create_app
from app.providers.base import OUTCOME_TIMEOUT, ProviderResult
from app.providers.llm_provider import LlmProvider

CONTENT = load_content(make_settings().content_dir)
DELAY_SECONDS = 0.40


class SlowProvider:
    """Model stand-in that takes a fixed, observable amount of time."""

    provider_id = "slow-model"
    kind = "external_model"
    is_synthetic = False
    available = True

    def __init__(self, delay: float = DELAY_SECONDS) -> None:
        self.delay = delay
        self.calls = 0

    async def generate(self, request) -> ProviderResult:
        self.calls += 1
        await asyncio.sleep(self.delay)
        return ProviderResult(
            outcome=OUTCOME_TIMEOUT,
            provider_kind="fallback",
            provider_id=self.provider_id,
            is_synthetic=True,
            failure_detail="simulated_timeout",
        )


class ExplodingProvider:
    provider_id = "exploding-model"
    kind = "external_model"
    is_synthetic = False
    available = True

    async def generate(self, request) -> ProviderResult:
        raise RuntimeError("upstream exploded")


async def _open_session(client: httpx.AsyncClient, npc_id: str = "npc_laozhou") -> str:
    response = await client.post("/api/v1/sessions", json={"npc_id": npc_id})
    assert response.status_code == 201, response.text
    return response.json()["data"]["conversation_id"]


async def _take_turn(client: httpx.AsyncClient, conversation_id: str, text: str):
    return await client.post(
        f"/api/v1/sessions/{conversation_id}/turns", json={"text": text}
    )


def _app(provider, **overrides):
    return create_app(
        make_settings(**{"rate_limit_per_minute": 600, "rate_limit_burst": 600, **overrides}),
        provider=provider,
        content=CONTENT,
    )


def test_slow_model_does_not_block_other_requests():
    provider = SlowProvider()
    app = _app(provider)

    async def scenario():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            conversation_id = await _open_session(client)
            slow = asyncio.create_task(_take_turn(client, conversation_id, "那晚站台发生了什么"))
            await asyncio.sleep(0.05)  # the slow turn is now in flight

            started = time.perf_counter()
            health = await client.get("/api/v1/health")
            elapsed = time.perf_counter() - started

            slow_response = await slow
        return health, elapsed, slow_response

    health, elapsed, slow_response = asyncio.run(scenario())
    assert health.status_code == 200
    assert elapsed < DELAY_SECONDS / 2, "health waited for the model"
    assert slow_response.status_code == 200
    assert slow_response.json()["data"]["fallback_reason"] == "timeout"
    assert provider.calls == 1


def test_two_sessions_wait_for_the_model_in_parallel():
    provider = SlowProvider()
    app = _app(provider)

    async def scenario():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first = await _open_session(client, "npc_laozhou")
            second = await _open_session(client, "npc_linyao")
            started = time.perf_counter()
            responses = await asyncio.gather(
                _take_turn(client, first, "那天站台发生了什么"),
                _take_turn(client, second, "我带来了一张凭号"),
            )
            return time.perf_counter() - started, responses

    elapsed, responses = asyncio.run(scenario())
    assert all(response.status_code == 200 for response in responses)
    assert provider.calls == 2
    # Serialised calls would need ~2x DELAY; concurrent calls need ~1x.
    assert elapsed < DELAY_SECONDS * 1.6


def test_fixed_turns_stay_fast_while_the_model_is_busy():
    provider = SlowProvider()
    app = _app(provider)

    async def scenario():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            slow_session = await _open_session(client)
            fixed_session = await _open_session(client)
            slow = asyncio.create_task(_take_turn(client, slow_session, "那天站台发生了什么"))
            await asyncio.sleep(0.05)
            started = time.perf_counter()
            fixed = await client.post(
                f"/api/v1/sessions/{fixed_session}/turns",
                json={"topic_id": "opt.laozhou.ask_b01"},
            )
            elapsed = time.perf_counter() - started
            await slow
        return elapsed, fixed

    elapsed, fixed = asyncio.run(scenario())
    assert fixed.json()["data"]["source"] == "fixed_line"
    assert elapsed < DELAY_SECONDS / 2


def test_provider_exception_becomes_a_fallback_turn():
    app = _app(ExplodingProvider())

    async def scenario():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            conversation_id = await _open_session(client)
            return await _take_turn(client, conversation_id, "随便聊聊")

    response = asyncio.run(scenario())
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "completed"
    assert payload["source"] == "fallback"
    assert payload["fallback_reason"] == "model_unavailable"
    assert payload["provider"]["kind"] == "fallback"


def test_llm_client_is_created_lazily_and_released_on_shutdown(tmp_path):
    settings = make_settings(
        entry_mode="live",
        model_provider="llm",
        llm_base_url="https://llm.invalid/v1",
        llm_model="fake-model",
        llm_api_key="test-key-not-a-real-secret",
        llm_usage_path=tmp_path / "ledger.sqlite3",
        llm_ledger_epoch_path=tmp_path / "epoch" / "ledger-epoch.json",
    )
    settings.validate()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"npc_id": "npc_laozhou", "text": "灯还在里头。"}'
                        }
                    }
                ]
            },
        )
    )
    budget = RequestBudget.initialize(
        settings.llm_usage_path,
        settings.llm_ledger_epoch_path,
        limit=settings.llm_request_limit,
        per_session_limit=settings.llm_request_limit_per_session,
    )
    provider = LlmProvider(settings, budget=budget, transport=transport)
    app = create_app(settings, provider=provider, content=CONTENT)
    assert provider.available is True

    async def scenario():
        async with app.router.lifespan_context(app):
            inner = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=inner, base_url="http://test") as client:
                conversation_id = await _open_session(client)
                response = await _take_turn(client, conversation_id, "那晚站台发生了什么")
                assert response.status_code == 200
                assert response.json()["data"]["source"] == "external_model"
                created = provider._client is not None
        return created

    assert asyncio.run(scenario()) is True
    assert provider._client is None, "httpx client leaked after shutdown"
    assert provider.available is False
