"""Multi-player isolation (M4-C C1.1).

Two players on one service instance must never see each other's conversation,
evidence acknowledgement or disclosure state.  The pre-M4-C store closed every
open session whenever a new one was created, so these tests are the regression
guard for that bug.
"""

from __future__ import annotations

import time

import pytest

from conftest import assert_error, build_client, create_session, present, take_turn

from app.errors import ApiError
from app.sessions import SessionStore


def _status(client, conversation_id: str) -> str:
    response = client.get(f"/api/v1/sessions/{conversation_id}")
    assert response.status_code == 200, response.text
    return response.json()["data"]["status"]


def test_two_players_keep_their_own_sessions(client):
    player_a = create_session(client, "npc_laozhou")
    player_b = create_session(client, "npc_linyao")

    assert _status(client, player_a) == "open"
    assert _status(client, player_b) == "open"

    a_turn = take_turn(client, player_a, topic_id="opt.laozhou.ask_b01")
    assert a_turn["conversation_id"] == player_a

    b_turn = take_turn(client, player_b, text="我带来了一张凭号")
    assert b_turn["conversation_id"] == player_b


def test_evidence_and_disclosure_state_is_per_session(client):
    player_a = create_session(client, "npc_laozhou")
    player_b = create_session(client, "npc_laozhou")

    d01 = present(client, player_a, ["E02"])
    assert d01["triggered_disclosure_ids"] == ["D01"]

    a_state = client.get(f"/api/v1/sessions/{player_a}").json()["data"]
    b_state = client.get(f"/api/v1/sessions/{player_b}").json()["data"]
    assert a_state["triggered_disclosure_ids"] == ["D01"]
    assert a_state["presented_evidence_ids"] == ["E02"]
    assert b_state["triggered_disclosure_ids"] == []
    assert b_state["presented_evidence_ids"] == []
    # The repeat topic unlocked for A must stay locked for B.
    assert "opt.laozhou.repeat_b01" in a_state["available_topic_ids"]
    assert "opt.laozhou.repeat_b01" not in b_state["available_topic_ids"]


def test_cancelling_one_session_leaves_the_other_open(client):
    player_a = create_session(client, "npc_laozhou")
    player_b = create_session(client, "npc_linyao")

    assert client.post(f"/api/v1/sessions/{player_a}/cancel").status_code == 200
    assert_error(client.get(f"/api/v1/sessions/{player_a}"), 410, "TURN_EXPIRED")
    assert _status(client, player_b) == "open"
    take_turn(client, player_b, text="表还在吗")


def test_leaving_one_conversation_leaves_the_other_open(client):
    player_a = create_session(client, "npc_laozhou")
    player_b = create_session(client, "npc_linyao")

    take_turn(client, player_a, topic_id="opt.laozhou.leave")
    assert_error(client.get(f"/api/v1/sessions/{player_a}"), 410, "TURN_EXPIRED")
    assert _status(client, player_b) == "open"


def test_session_cap_bounds_memory_and_evicts_oldest(content, scenarios):
    with build_client(
        content,
        scenarios,
        max_sessions=3,
        rate_limit_per_minute=1000,
        rate_limit_burst=1000,
    ) as client:
        conversation_ids = [
            create_session(client, "npc_laozhou") for _ in range(5)
        ]
        # The two oldest were evicted to keep the store inside its hard cap.
        assert_error(client.get(f"/api/v1/sessions/{conversation_ids[0]}"), 404, "NOT_FOUND")
        assert_error(client.get(f"/api/v1/sessions/{conversation_ids[1]}"), 404, "NOT_FOUND")
        assert client.get(f"/api/v1/sessions/{conversation_ids[4]}").status_code == 200


def test_terminal_sessions_are_purged_after_retention():
    store = SessionStore(
        ttl_seconds=60.0, max_sessions=10, terminal_retention_seconds=0.01
    )
    ended = store.create("npc_laozhou", set(), set())
    store.close(ended.conversation_id)
    assert len(store) == 1

    time.sleep(0.03)
    live = store.create("npc_laozhou", set(), set())
    assert len(store) == 1, "closed session should have been purged"
    assert store.get(live.conversation_id).is_open


def test_store_never_exceeds_its_cap_even_when_all_sessions_are_open():
    store = SessionStore(ttl_seconds=60.0, max_sessions=2)
    recent = [store.create("npc_laozhou", set(), set()) for _ in range(6)]
    assert len(store) == 2
    assert store.open_count() == 2
    assert any(session.is_open for session in recent)


def test_expired_sessions_do_not_keep_their_slot():
    store = SessionStore(
        ttl_seconds=0.01, max_sessions=1, terminal_retention_seconds=0.01
    )
    first = store.create("npc_laozhou", set(), set())
    time.sleep(0.03)
    with pytest.raises(ApiError) as expired:
        store.get(first.conversation_id)
    assert expired.value.status_code == 410
    assert expired.value.code == "TURN_EXPIRED"

    second = store.create("npc_linyao", set(), set())
    assert len(store) == 1
    assert store.get(second.conversation_id).is_open
    with pytest.raises(ApiError) as evicted:
        store.get(first.conversation_id)
    assert evicted.value.status_code == 404
