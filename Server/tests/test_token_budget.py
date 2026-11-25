"""M5-C-A-R1 section 3/5: token-budget accounting with a fake upstream.

All calls go through ``httpx.MockTransport``; no real model, no magic credits.
"""

from __future__ import annotations

import sqlite3

import httpx
import pytest

from conftest import create_session, take_turn
from llm_support import NPC, chat_body, llm_settings, make_llm_app, reply_handler

from app.knowledge import estimate_tokens


def _row(settings) -> tuple:
    with sqlite3.connect(settings.llm_usage_path) as conn:
        return conn.execute(
            "SELECT status, prompt_tokens, completion_tokens, usage_known,"
            " billing_uncertain, reserved_tokens FROM attempts ORDER BY id DESC LIMIT 1"
        ).fetchone()


def _reservation(settings) -> int:
    return settings.llm_context_max_tokens + settings.llm_max_output_tokens


def test_reported_usage_is_recorded_exactly(tmp_path):
    settings = llm_settings(tmp_path)
    client, calls = make_llm_app(
        tmp_path,
        reply_handler("那晚我在站台值班。", usage={"prompt_tokens": 12, "completion_tokens": 5}),
        settings=settings,
    )
    conversation = create_session(client, NPC)
    take_turn(client, conversation, text="那晚到底发生了什么")

    usage = client.budget.usage()
    assert usage["tokens_used"] == 17
    assert usage["tokens_reserved"] == 0
    assert usage["unknown_usage_attempts"] == 0
    assert _row(settings)[:5] == ("completed", 12, 5, 1, 0)


def test_missing_usage_is_unknown_not_free(tmp_path):
    """A reply without ``usage`` must charge the reservation, not zero."""

    settings = llm_settings(tmp_path)
    client, calls = make_llm_app(tmp_path, reply_handler("那晚我在站台值班。"), settings=settings)
    conversation = create_session(client, NPC)
    turn = take_turn(client, conversation, text="那晚到底发生了什么")

    usage = client.budget.usage()
    assert turn["status"] == "completed"
    assert usage["tokens_used"] == _reservation(settings)
    assert usage["unknown_usage_attempts"] == 1
    assert usage["uncertain_billing_attempts"] == 1
    status, prompt, completion, known, uncertain, reserved = _row(settings)
    assert status == "completed"
    assert (prompt, completion) == (0, 0)
    assert known == 0
    assert uncertain == 1
    assert reserved == _reservation(settings)


def test_timeout_charges_the_reservation(tmp_path):
    settings = llm_settings(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("boom", request=request)

    client, calls = make_llm_app(tmp_path, handler, settings=settings)
    conversation = create_session(client, NPC)
    turn = take_turn(client, conversation, text="那晚到底发生了什么")

    assert turn["fallback_reason"] == "timeout"
    usage = client.budget.usage()
    assert usage["global_used"] == 1
    assert usage["tokens_used"] == _reservation(settings)
    assert usage["uncertain_billing_attempts"] == 1


def test_token_budget_blocks_before_the_second_call(tmp_path):
    settings = llm_settings(tmp_path, llm_token_limit=3000)
    client, calls = make_llm_app(tmp_path, reply_handler("那晚我在站台值班。"), settings=settings)

    first = create_session(client, NPC)
    take_turn(client, first, text="那晚到底发生了什么")
    second = create_session(client, NPC)
    turn = take_turn(client, second, text="再说说别的")

    assert len(calls) == 1, "the second turn must not reach the upstream"
    assert turn["fallback_reason"] == "budget_token_exhausted"
    assert client.budget.usage()["tokens_used"] == _reservation(settings)


def test_unknown_usage_still_consumes_the_budget(tmp_path):
    # Two unknown-usage replies must not be free: 2 * 1756 > 3000.
    settings = llm_settings(tmp_path, llm_token_limit=3000)
    client, calls = make_llm_app(tmp_path, reply_handler("那晚我在站台值班。"), settings=settings)
    for _ in range(2):
        conversation = create_session(client, NPC)
        turn = take_turn(client, conversation, text="那晚到底发生了什么")
    assert len(calls) == 1
    assert turn["fallback_reason"] == "budget_token_exhausted"


def test_output_and_input_caps_are_sent_upstream(tmp_path):
    settings = llm_settings(tmp_path, llm_max_output_tokens=64, llm_input_max_chars=120)
    client, calls = make_llm_app(tmp_path, reply_handler("那晚我在站台值班。"), settings=settings)
    conversation = create_session(client, NPC)
    long_text = "那晚" * 100  # 200 chars: legal for the API, above the model cap
    take_turn(client, conversation, text=long_text)

    payload = calls[0]
    assert payload["max_tokens"] == 64
    assert payload["stream"] is False
    assert len(payload["messages"][1]["content"]) == 120


def test_context_budget_covers_system_and_user_text(tmp_path):
    settings = llm_settings(
        tmp_path,
        llm_context_max_tokens=1024,
        llm_token_limit=2000,
    )
    client, calls = make_llm_app(tmp_path, reply_handler("那晚我在站台值班。"), settings=settings)

    # 800 characters of player text plus the rules cannot fit 1024 tokens, so
    # the adapter refuses instead of sending an oversized prompt.
    conversation = create_session(client, NPC)
    turn = take_turn(client, conversation, text="那" * 800)
    assert calls == []
    assert turn["source"] == "fallback"
    assert client.budget.usage()["global_used"] == 0

    # The same player may still talk: the cap is on the *context*, not the turn.
    short = create_session(client, NPC)
    take_turn(client, short, text="那晚的事")
    assert len(calls) == 1
    prompt = calls[0]["messages"][0]["content"]
    user_tokens = estimate_tokens(calls[0]["messages"][1]["content"])
    assert estimate_tokens(prompt) + user_tokens + 64 + 16 <= 1024


def test_reservation_is_request_scoped_and_released(tmp_path):
    settings = llm_settings(tmp_path)
    client, calls = make_llm_app(
        tmp_path,
        reply_handler("那晚我在站台值班。", usage={"prompt_tokens": 7, "completion_tokens": 3}),
        settings=settings,
    )
    conversation = create_session(client, NPC)
    take_turn(client, conversation, text="那晚到底发生了什么")
    usage = client.budget.usage()
    assert usage["tokens_reserved"] == 0
    assert usage["tokens_used"] == 10
    assert usage["token_limit"] == settings.llm_token_limit
    assert usage["persistent"] is True


def test_disabled_ledger_blocks_the_upstream(tmp_path):
    settings = llm_settings(tmp_path)
    client, calls = make_llm_app(tmp_path, reply_handler("那晚我在站台值班。"), settings=settings)
    conversation = create_session(client, NPC)

    client.budget._disable("ledger_replaced")  # simulate an unprovable ledger
    turn = take_turn(client, conversation, text="那晚到底发生了什么")

    assert calls == []
    assert turn["fallback_reason"].startswith("ledger_")
    assert client.provider.available is False


@pytest.mark.parametrize("status_code", [401, 429, 500, 503])
def test_upstream_errors_charge_one_attempt_and_no_retry(tmp_path, status_code):
    settings = llm_settings(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": "denied"})

    client, calls = make_llm_app(tmp_path, handler, settings=settings)
    conversation = create_session(client, NPC)
    turn = take_turn(client, conversation, text="那晚到底发生了什么")

    assert len(calls) == 1
    assert turn["fallback_reason"] == "model_unavailable"
    usage = client.budget.usage()
    assert usage["global_used"] == 1
    assert usage["tokens_used"] == _reservation(settings)


def test_fake_key_never_appears_in_the_response(tmp_path):
    settings = llm_settings(tmp_path)
    client, calls = make_llm_app(tmp_path, reply_handler("那晚我在站台值班。"), settings=settings)
    conversation = create_session(client, NPC)
    turn = take_turn(client, conversation, text="那晚到底发生了什么")
    assert "test-key-not-a-real-secret" not in str(turn)
    assert "test-key-not-a-real-secret" not in client.get("/api/v1/health").text
