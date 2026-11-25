"""Upstream transport matrix, budget accounting, and circuit breaking.

Everything here runs against ``httpx.MockTransport``; no network is used and
no real credential exists.
"""

from __future__ import annotations

import asyncio
import sqlite3

import httpx
import pytest

from app.budget import RequestBudget
from app.config import Settings
from app.providers.base import (
    OUTCOME_COMPLETED,
    OUTCOME_INVALID_OUTPUT,
    OUTCOME_MODEL_UNAVAILABLE,
    OUTCOME_TIMEOUT,
    ProviderRequest,
)
from app.providers.llm_provider import LlmProvider

API_KEY = "test-key-not-a-real-secret"


def _settings(tmp_path, **overrides) -> Settings:
    values = dict(
        entry_mode="live",
        model_provider="llm",
        llm_base_url="https://llm.invalid/v1",
        llm_model="fake-model",
        llm_api_key=API_KEY,
        allowed_origins=("http://localhost:8080",),
        llm_usage_path=tmp_path / "ledger.sqlite3",
        llm_ledger_epoch_path=tmp_path / "epoch" / "ledger-epoch.json",
    )
    values.update(overrides)
    settings = Settings(**values)
    settings.validate()
    return settings


def _provider(tmp_path, handler, *, clock=None, **overrides):
    settings = _settings(tmp_path, **overrides)
    budget = RequestBudget.initialize(
        settings.llm_usage_path,
        settings.llm_ledger_epoch_path,
        limit=settings.llm_request_limit,
        per_session_limit=settings.llm_request_limit_per_session,
    )
    kwargs = {}
    if clock is not None:
        kwargs["clock"] = clock
    provider = LlmProvider(
        settings,
        budget=budget,
        transport=httpx.MockTransport(handler),
        **kwargs,
    )
    return settings, budget, provider


def _request(session_id: str = "conv-a") -> ProviderRequest:
    return ProviderRequest(
        request_id="req-1",
        npc_id="npc_laozhou",
        display_name="老周",
        player_input="那晚站台发生了什么？",
        acquired_evidence_ids=("E01",),
        available_topic_ids=("opt.laozhou.ask_b01",),
        timeout_ms=12000,
        content_version="story-v1.0-phase2",
        session_id=session_id,
    )


def _chat(content: str, *, finish_reason: str | None = "stop", usage=None):
    body = {
        "choices": [
            {
                "message": {"content": content},
                "finish_reason": finish_reason,
            }
        ]
    }
    if usage is not None:
        body["usage"] = usage
    return httpx.Response(200, json=body)


def _valid_reply() -> str:
    return '{"npc_id": "npc_laozhou", "text": "那晚我值夜，只听见风。"}'


def _run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("status", [401, 429, 500, 503])
def test_status_failures_send_exactly_one_request_and_count(tmp_path, status):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(status, text="upstream said no")

    settings, budget, provider = _provider(tmp_path, handler)
    result = _run(provider.generate(_request()))

    assert calls["n"] == 1  # no paid retry
    assert result.outcome == OUTCOME_MODEL_UNAVAILABLE
    assert result.failure_detail == f"upstream_status_{status}"
    assert "upstream said no" not in (result.failure_detail or "")
    usage = budget.usage()
    assert usage["global_used"] == 1  # failed attempt still counted
    with sqlite3.connect(settings.llm_usage_path) as conn:
        row = conn.execute("SELECT status, error FROM attempts").fetchone()
    assert row == ("failed", f"upstream_status_{status}")


def test_timeout_and_connection_failures_degrade(tmp_path):
    def timeout_handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    _, budget, provider = _provider(tmp_path, timeout_handler)
    result = _run(provider.generate(_request()))
    assert result.outcome == OUTCOME_TIMEOUT
    assert result.failure_detail == "upstream_timeout"
    assert budget.usage()["global_used"] == 1

    def connect_handler(request):
        raise httpx.ConnectError("refused", request=request)

    _, _, provider2 = _provider(tmp_path / "second", connect_handler)
    result2 = _run(provider2.generate(_request()))
    assert result2.outcome == OUTCOME_MODEL_UNAVAILABLE
    assert result2.failure_detail == "upstream_transport_error"


@pytest.mark.parametrize(
    "response, detail",
    [
        (httpx.Response(200, text="not json at all"), "response_not_json"),
        (httpx.Response(200, json={"choices": []}), "response_missing_choices"),
        (
            httpx.Response(
                200,
                json={"choices": [{"message": {"content": '{"npc_id": "npc_laozhou", "text"'}}]},
            ),
            "invalid_json_line_1",
        ),
        (
            httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": _valid_reply()}, "finish_reason": "length"}
                    ]
                },
            ),
            "response_truncated",
        ),
    ],
)
def test_malformed_and_truncated_outputs_are_invalid(tmp_path, response, detail):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return response

    _, budget, provider = _provider(tmp_path, handler)
    result = _run(provider.generate(_request()))
    assert result.outcome == OUTCOME_INVALID_OUTPUT
    assert result.failure_detail == detail
    assert calls["n"] == 1
    assert budget.usage()["global_used"] == 1


def test_success_records_real_token_usage_and_never_leaks_key(tmp_path):
    seen = {}

    def handler(request):
        seen["body"] = request.read().decode("utf-8")
        seen["auth"] = request.headers.get("authorization")
        return _chat(
            _valid_reply(),
            usage={"prompt_tokens": 12, "completion_tokens": 5, "total_tokens": 17},
        )

    settings, budget, provider = _provider(tmp_path, handler)
    result = _run(provider.generate(_request()))

    assert result.outcome == OUTCOME_COMPLETED
    assert result.text == "那晚我值夜，只听见风。"
    assert result.is_synthetic is False
    assert seen["auth"] == f"Bearer {API_KEY}"
    assert API_KEY not in seen["body"]
    with sqlite3.connect(settings.llm_usage_path) as conn:
        row = conn.execute(
            "SELECT status, prompt_tokens, completion_tokens FROM attempts"
        ).fetchone()
    assert row == ("completed", 12, 5)
    assert budget.usage()["global_used"] == 1


def test_payload_respects_token_and_input_caps(tmp_path):
    seen = {}

    def handler(request):
        import json

        seen["payload"] = json.loads(request.read().decode("utf-8"))
        return _chat(_valid_reply())

    _, _, provider = _provider(
        tmp_path, handler, llm_input_max_chars=120, llm_max_output_tokens=64
    )
    request = ProviderRequest(
        request_id="req-1",
        npc_id="npc_laozhou",
        display_name="老周",
        player_input="询" * 5000,
        acquired_evidence_ids=(),
        available_topic_ids=(),
        timeout_ms=12000,
        content_version="story-v1.0-phase2",
        session_id="s",
    )
    result = _run(provider.generate(request))
    assert result.outcome == OUTCOME_COMPLETED
    payload = seen["payload"]
    assert payload["max_tokens"] == 64
    assert len(payload["messages"][1]["content"]) == 120
    assert payload["stream"] is False


def test_global_budget_exhaustion_blocks_before_any_request(tmp_path):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return _chat(_valid_reply())

    _, budget, provider = _provider(
        tmp_path, handler, llm_request_limit=2, llm_request_limit_per_session=1
    )
    first = _run(provider.generate(_request("conv-a")))
    second = _run(provider.generate(_request("conv-b")))
    third = _run(provider.generate(_request("conv-c")))

    assert first.outcome == OUTCOME_COMPLETED
    assert second.outcome == OUTCOME_COMPLETED
    assert third.outcome == OUTCOME_MODEL_UNAVAILABLE
    assert third.failure_detail == "budget_global_exhausted"
    assert calls["n"] == 2  # the refused attempt made no upstream request
    assert budget.usage()["global_used"] == 2


def test_one_session_cannot_exhaust_the_service_budget(tmp_path):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return _chat(_valid_reply())

    _, budget, provider = _provider(
        tmp_path, handler, llm_request_limit=6, llm_request_limit_per_session=2
    )
    for _ in range(2):
        assert _run(provider.generate(_request("conv-a"))).outcome == OUTCOME_COMPLETED
    blocked = _run(provider.generate(_request("conv-a")))
    assert blocked.failure_detail == "budget_session_exhausted"
    # A different conversation still has its own allowance.
    other = _run(provider.generate(_request("conv-b")))
    assert other.outcome == OUTCOME_COMPLETED
    assert calls["n"] == 3
    assert budget.usage()["global_used"] == 3


def test_deleted_ledger_blocks_live_calls_without_upstream(tmp_path):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return _chat(_valid_reply())

    settings, budget, provider = _provider(tmp_path, handler)
    assert _run(provider.generate(_request())).outcome == OUTCOME_COMPLETED
    # Simulate the persisted ledger disappearing (restart/new container).
    budget.close()
    settings.llm_usage_path.unlink()

    blocked = _run(provider.generate(_request()))
    assert blocked.outcome == OUTCOME_MODEL_UNAVAILABLE
    assert blocked.failure_detail == "ledger_unavailable"
    assert calls["n"] == 1
    assert budget.unavailable_reason == "ledger_closed"
    assert budget.usage()["persistent"] is False
    assert provider.available is False


def test_circuit_breaker_opens_then_recovers_half_open(tmp_path):
    state = {"t": 0.0, "status": 500, "calls": 0}

    def clock():
        return state["t"]

    def handler(request):
        state["calls"] += 1
        if state["status"] == 200:
            return _chat(_valid_reply())
        return httpx.Response(500)

    _, _, provider = _provider(tmp_path, handler, clock=clock)
    for _ in range(5):
        assert _run(provider.generate(_request())).outcome == OUTCOME_MODEL_UNAVAILABLE
        state["t"] += 1
    assert provider.breaker.snapshot()["state"] == "open"

    blocked = _run(provider.generate(_request()))
    assert blocked.failure_detail == "circuit_open"
    assert state["calls"] == 5  # open circuit sends nothing upstream

    state["t"] += 61  # cooldown elapsed -> one half-open trial
    state["status"] = 200
    recovered = _run(provider.generate(_request()))
    assert recovered.outcome == OUTCOME_COMPLETED
    assert provider.breaker.snapshot()["state"] == "closed"
    assert state["calls"] == 6


def test_budget_finish_failure_does_not_crash_the_turn(tmp_path):
    """A ledger that dies between reserve and finish must not leak the error."""

    def handler(request):
        return _chat(_valid_reply())

    settings, budget, provider = _provider(tmp_path, handler)
    original_finish = budget.finish

    def exploding_finish(*args, **kwargs):
        raise sqlite3.Error("injected finish failure")

    budget.finish = exploding_finish  # type: ignore[method-assign]
    result = _run(provider.generate(_request()))
    # The model already answered, so the player still gets the line; the
    # ledger error is contained by _budget_finish.
    assert result.outcome == OUTCOME_COMPLETED
    assert result.text == "那晚我值夜，只听见风。"
    budget.finish = original_finish  # type: ignore[method-assign]
