"""M5-C-A-R1 section 7: the service must not claim a real model is connected.

State machine under test (``app.model_state``)::

    mock                 entry_mode=mock
    not_configured       live but no base_url/model/key
    configured_unverified  configured, nothing proven yet
    connected            at least one *real* upstream success
    test_upstream_verified  success only from the Fake test upstream
    upstream_error       failures, no success yet
    circuit_open         breaker tripped
    budget_exhausted     request or token budget used up
    budget_unavailable   the ledger cannot prove the budget
"""

from __future__ import annotations

import httpx
import pytest

from conftest import create_session, take_turn
from llm_support import NPC, chat_body, make_llm_app, reply_handler

from app.model_state import ModelState


def _health(client) -> dict:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    return response.json()["data"]


def _upstream_error(request: httpx.Request) -> httpx.Response:
    return httpx.Response(500, json={"error": "boom"})


# ------------------------------------------------------------------ mock mode


def test_mock_mode_never_claims_a_model(client):
    data = _health(client)
    assert data["entry_mode"] == "mock"
    assert data["model_status"] == "mock"
    assert data["model_ready"] is False
    assert data["model_available"] is False
    assert data["provider"]["is_synthetic"] is True


# --------------------------------------------------------------- live states


def test_configuration_alone_is_not_a_connection(tmp_path):
    client, calls = make_llm_app(tmp_path, reply_handler("那晚我在站台值班。"))
    data = _health(client)

    assert calls == []
    assert data["model_status"] == "configured_unverified"
    assert data["model_ready"] is False, "no call has been made yet"
    assert data["model"]["verified"] is False
    assert data["model"]["successes"] == 0
    assert data["provider"]["is_synthetic"] is False


def test_a_real_success_marks_connected(tmp_path):
    client, calls = make_llm_app(tmp_path, reply_handler("那晚我在站台值班。"))
    conversation = create_session(client, NPC)
    take_turn(client, conversation, text="那晚到底发生了什么")

    data = _health(client)
    assert len(calls) == 1
    assert data["model_status"] == "connected"
    assert data["model_ready"] is True
    assert data["model"]["successes"] == 1
    assert data["model"]["last_success_synthetic"] is False


def test_test_upstream_success_is_never_connected(tmp_path):
    def fake_upstream(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=chat_body("那晚我在站台值班。"),
            headers={"x-test-upstream": "fake"},
        )

    client, calls = make_llm_app(tmp_path, fake_upstream)
    conversation = create_session(client, NPC)
    take_turn(client, conversation, text="那晚到底发生了什么")

    data = _health(client)
    assert data["model_status"] == "test_upstream_verified"
    assert data["model_ready"] is False, "a Fake upstream must not count as real"
    assert data["provider"]["is_synthetic"] is True
    assert data["model"]["last_success_synthetic"] is True


def test_upstream_errors_are_reported_as_error(tmp_path):
    client, calls = make_llm_app(tmp_path, _upstream_error)
    conversation = create_session(client, NPC)
    take_turn(client, conversation, text="那晚到底发生了什么")

    data = _health(client)
    assert data["model_status"] == "upstream_error"
    assert data["model_ready"] is False
    assert data["model"]["failures"] == 1
    assert data["model"]["last_failure_detail"] == "upstream_status_500"


def test_open_breaker_is_reported_as_circuit_open(tmp_path):
    client, calls = make_llm_app(tmp_path, _upstream_error)
    for _ in range(5):
        conversation = create_session(client, NPC)
        take_turn(client, conversation, text="那晚到底发生了什么")

    data = _health(client)
    assert data["breaker"]["state"] == "open"
    assert data["model_status"] == "circuit_open"
    assert data["model_available"] is False


def test_exhausted_budget_is_reported_as_budget_exhausted(tmp_path):
    from llm_support import llm_settings

    settings = llm_settings(tmp_path, llm_token_limit=1756)  # exactly one reservation
    client, calls = make_llm_app(
        tmp_path,
        reply_handler("那晚我在站台值班。"),  # no usage => charged the reservation
        settings=settings,
    )
    conversation = create_session(client, NPC)
    take_turn(client, conversation, text="那晚到底发生了什么")

    data = _health(client)
    assert data["ledger"]["tokens_used"] == data["ledger"]["token_limit"] == 1756
    assert data["model_status"] == "budget_exhausted"
    assert data["model_available"] is False


def test_unprovable_ledger_is_reported_as_budget_unavailable(tmp_path):
    client, calls = make_llm_app(tmp_path, reply_handler("那晚我在站台值班。"))
    client.budget._disable("ledger_replaced")

    data = _health(client)
    assert data["model_status"] == "budget_unavailable"
    assert data["model_available"] is False
    assert data["ledger"]["persistent"] is False


# ------------------------------------------------------------ unit-level truth


def test_model_state_requires_a_non_synthetic_last_success():
    state = ModelState(entry_mode="live", provider_kind="external_model", configured=True)
    state.record_success(synthetic=True)
    assert state.verified_real is False
    assert state.verified_test_upstream is True

    state.record_success(synthetic=False)
    assert state.verified_real is True
    assert state.status() == "connected"


def test_model_state_prefers_failure_when_nothing_succeeded():
    state = ModelState(entry_mode="live", provider_kind="external_model", configured=True)
    state.record_failure("upstream_timeout")
    snapshot = state.snapshot(budget_usage={"status": "ready"})
    assert snapshot["status"] == "upstream_error"
    assert snapshot["verified"] is False
    assert snapshot["last_failure_detail"] == "upstream_timeout"


@pytest.mark.parametrize(
    ("usage", "expected"),
    [
        ({"status": "ledger_replaced"}, "budget_unavailable"),
        (
            {"status": "ready", "global_used": 5, "global_limit": 5, "tokens_used": 0,
             "token_limit": 60000},
            "budget_exhausted",
        ),
        (
            {"status": "ready", "global_used": 1, "global_limit": 5, "tokens_used": 60000,
             "token_limit": 60000},
            "budget_exhausted",
        ),
    ],
)
def test_budget_states_win_over_configuration(usage, expected):
    state = ModelState(entry_mode="live", provider_kind="external_model", configured=True)
    assert state.status(budget_usage=usage) == expected


def test_breaker_state_wins_over_empty_history():
    state = ModelState(entry_mode="live", provider_kind="external_model", configured=True)
    snapshot = state.snapshot(
        budget_usage={"status": "ready", "global_used": 0, "global_limit": 5},
        breaker={"state": "open"},
    )
    assert snapshot["status"] == "circuit_open"
