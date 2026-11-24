"""Session lifecycle and turn-contract tests."""

from __future__ import annotations

import time

from conftest import assert_error, build_client, create_session, fixed_texts, take_turn


def test_opening_lines_for_both_npcs(client):
    laozhou = client.post("/api/v1/sessions", json={"npc_id": "npc_laozhou"}).json()["data"]
    assert fixed_texts(laozhou) == ["这封从旧库搬过两回。我来对号，你来签。先看表背，失物只认号。"]
    linyao = client.post("/api/v1/sessions", json={"npc_id": "npc_linyao"}).json()["data"]
    assert fixed_texts(linyao) == ["公告上有一张我妈留的领取凭号。我把原来的带来了。表还在吗？"]
    assert laozhou["conversation_id"] != linyao["conversation_id"]


def test_fixed_turn_uses_approved_line_and_contract_fields(client):
    conversation_id = create_session(client, "npc_laozhou")
    turn = take_turn(client, conversation_id, topic_id="opt.laozhou.ask_b01")
    assert turn["source"] == "fixed_line"
    assert fixed_texts(turn) == ["站台那晚在我印象里一直亮着。我还把那盏油灯拖到里头去了。"]
    assert turn["fixed_segments"][0]["content_ref"] == "dialogue.CH01.B01.initial"
    assert turn["fixed_delivery_token"] is None
    assert turn["generated_bridge"] is None
    assert turn["fallback_reason"] is None
    assert turn["provider"] == {"kind": "mock", "id": "fixed-line-content", "is_synthetic": False}
    assert "opt.laozhou.repeat_b01" not in turn["available_topic_ids"]


def test_locked_topic_requires_disclosure(client):
    conversation_id = create_session(client, "npc_laozhou")
    assert_error(
        client.post(
            f"/api/v1/sessions/{conversation_id}/turns",
            json={"topic_id": "opt.laozhou.repeat_b01"},
        ),
        409,
        "PRECONDITION_FAILED",
    )


def test_unknown_topic_is_not_found(client):
    conversation_id = create_session(client, "npc_laozhou")
    assert_error(
        client.post(
            f"/api/v1/sessions/{conversation_id}/turns",
            json={"topic_id": "opt.laozhou.no_such_topic"},
        ),
        404,
        "NOT_FOUND",
    )


def test_turn_requires_exactly_one_input(client):
    conversation_id = create_session(client, "npc_laozhou")
    assert_error(
        client.post(f"/api/v1/sessions/{conversation_id}/turns", json={}),
        422,
        "VALIDATION_ERROR",
    )
    assert_error(
        client.post(
            f"/api/v1/sessions/{conversation_id}/turns",
            json={"topic_id": "opt.laozhou.ask_b01", "text": "灯"},
        ),
        422,
        "VALIDATION_ERROR",
    )
    assert_error(
        client.post(f"/api/v1/sessions/{conversation_id}/turns", json={"text": "   "}),
        422,
        "VALIDATION_ERROR",
    )


def test_overlong_player_text_is_rejected(client):
    conversation_id = create_session(client, "npc_laozhou")
    assert_error(
        client.post(
            f"/api/v1/sessions/{conversation_id}/turns", json={"text": "灯" * 1001}
        ),
        400,
        "INVALID_REQUEST",
    )


def test_request_id_mismatch_is_rejected(client):
    conversation_id = create_session(client, "npc_laozhou")
    response = client.post(
        f"/api/v1/sessions/{conversation_id}/turns",
        json={"text": "灯", "request_id": "body-id"},
        headers={"X-Request-ID": "header-id"},
    )
    assert_error(response, 400, "INVALID_REQUEST")


def test_leave_topic_closes_session(client):
    conversation_id = create_session(client, "npc_laozhou")
    take_turn(client, conversation_id, topic_id="opt.laozhou.leave")
    assert_error(client.get(f"/api/v1/sessions/{conversation_id}"), 410, "TURN_EXPIRED")


def test_cancel_session(client):
    conversation_id = create_session(client, "npc_laozhou")
    response = client.post(f"/api/v1/sessions/{conversation_id}/cancel")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "cancelled"
    assert_error(client.get(f"/api/v1/sessions/{conversation_id}"), 410, "TURN_EXPIRED")


def test_new_conversation_does_not_close_previous_one(client):
    """M4-C regression: creating a session must not touch other players.

    The pre-M4-C store closed every open session on ``create``, which made two
    browser tabs (or two players on one instance) fight over one conversation.
    """

    first = create_session(client, "npc_laozhou")
    second = create_session(client, "npc_linyao")
    assert first != second
    for conversation_id in (first, second):
        response = client.get(f"/api/v1/sessions/{conversation_id}")
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "open"


def test_session_expires_after_ttl(content, scenarios):
    with build_client(content, scenarios, session_ttl_seconds=0.15) as short_client:
        conversation_id = create_session(short_client, "npc_laozhou")
        time.sleep(0.25)
        assert_error(
            short_client.get(f"/api/v1/sessions/{conversation_id}"), 410, "TURN_EXPIRED"
        )


def test_unknown_session_is_not_found(client):
    assert_error(client.get("/api/v1/sessions/not-a-session"), 404, "NOT_FOUND")


def test_method_not_allowed_uses_envelope(client):
    assert_error(client.delete("/api/v1/sessions"), 405, "INVALID_REQUEST")
