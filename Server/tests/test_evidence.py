"""Evidence presentation, disclosure (D) rules and duplicate handling."""

from __future__ import annotations

from conftest import assert_error, create_session, present, take_turn


def test_presenting_e02_triggers_d01_once(client):
    conversation_id = create_session(client, "npc_laozhou")
    first = present(client, conversation_id, ["E02"])
    assert first["presented_evidence_ids"] == ["E02"]
    assert first["already_presented"] is False
    assert first["triggered_disclosure_ids"] == ["D01"]
    assert first["fixed_segments"] == [
        {
            "content_ref": "dialogue.CH01.D01.laozhou",
            "text": "进水，二十一点十七。我的灯到二十才摆好。是黑过，中间那点我记混了。",
        }
    ]
    assert first["event_ids"]
    assert "D01" not in first["available_disclosure_ids"]

    # The newly unlocked topic is now visible.
    turn = take_turn(client, conversation_id, topic_id="opt.laozhou.ask_b01")
    assert "opt.laozhou.repeat_b01" in turn["available_topic_ids"]

    second = present(client, conversation_id, ["E02"])
    assert second["already_presented"] is True
    assert second["newly_presented_field_ids"] == []
    assert second["triggered_disclosure_ids"] == []
    assert second["fixed_segments"] == []
    assert second["event_ids"] == []


def test_linyao_d02_needs_both_receipts(client):
    conversation_id = create_session(client, "npc_linyao")
    first = present(client, conversation_id, ["E03"])
    assert first["triggered_disclosure_ids"] == []
    assert first["fixed_segments"] == []

    second = present(client, conversation_id, ["E04"])
    assert second["triggered_disclosure_ids"] == ["D02"]
    assert second["fixed_segments"][0]["content_ref"] == "dialogue.CH01.D02.linyao"
    assert second["fixed_segments"][0]["text"] == (
        "沈禾，是我妈妈。这个号和她放在家里那张一样。她写着要我自己领。"
    )


def test_laozhou_d02_is_verification_without_new_story_line(client):
    conversation_id = create_session(client, "npc_laozhou")
    data = present(client, conversation_id, ["E03", "E04"])
    assert data["triggered_disclosure_ids"] == ["D02"]
    assert data["fixed_segments"] == []


def test_laozhou_d03_requires_watch_and_inspection(client):
    conversation_id = create_session(client, "npc_laozhou")
    data = present(client, conversation_id, ["E01", "E05"])
    assert "D03" in data["triggered_disclosure_ids"]
    assert data["fixed_segments"][0]["text"] == (
        "她抓住小姑娘的胳膊，表掉到台沿。我弯腰拣的时候指针已经不动了，冠头是歪的。"
    )


def test_engraving_recognition_needs_observed_back_engraving(client):
    conversation_id = create_session(client, "npc_linyao")
    assert_error(
        client.post(
            f"/api/v1/sessions/{conversation_id}/turns",
            json={"topic_id": "opt.linyao.ask_engraving"},
        ),
        409,
        "PRECONDITION_FAILED",
    )

    data = present(
        client, conversation_id, ["E01"], ["watch.back_engraving"]
    )
    assert data["triggered_disclosure_ids"] == ["REC.engraving"]
    assert data["fixed_segments"][0]["text"] == (
        "四月十二是我妈的生日，九月十六是我的。那个点，我小时候摸得到。"
        "柜里究竟是不是那一只，你得对上号。"
    )

    turn = take_turn(client, conversation_id, topic_id="opt.linyao.ask_engraving")
    assert turn["source"] == "fixed_line"
    assert turn["fixed_segments"][0]["content_ref"] == "dialogue.CH01.linyao.engraving"


def test_evidence_not_approved_for_npc_is_precondition_failed(client):
    conversation_id = create_session(client, "npc_linyao")
    response = client.post(
        f"/api/v1/sessions/{conversation_id}/evidence",
        json={"evidence_ids": ["E02"]},
    )
    assert_error(response, 409, "PRECONDITION_FAILED")


def test_invalid_evidence_ids(client):
    conversation_id = create_session(client, "npc_laozhou")
    assert_error(
        client.post(
            f"/api/v1/sessions/{conversation_id}/evidence",
            json={"evidence_ids": ["E99"]},
        ),
        404,
        "NOT_FOUND",
    )
    assert_error(
        client.post(
            f"/api/v1/sessions/{conversation_id}/evidence",
            json={"evidence_ids": ["e1"]},
        ),
        400,
        "INVALID_REQUEST",
    )
    assert_error(
        client.post(
            f"/api/v1/sessions/{conversation_id}/evidence",
            json={"evidence_ids": []},
        ),
        422,
        "VALIDATION_ERROR",
    )
    assert_error(
        client.post(
            f"/api/v1/sessions/{conversation_id}/evidence",
            json={"evidence_ids": ["E02"], "observed_field_ids": ["bad.field"]},
        ),
        404,
        "NOT_FOUND",
    )


def test_presentation_never_grants_anything(client):
    conversation_id = create_session(client, "npc_linyao")
    data = present(client, conversation_id, ["E03"])
    assert set(data["presented_evidence_ids"]) <= {"E03"}
    forbidden = {"granted_evidence_ids", "rule_commands", "new_evidence", "quest_state"}
    assert forbidden.isdisjoint(data)
    assert data["observed_field_ids"] == []


def test_presenting_does_not_require_client_to_have_acquired_first(client):
    # Presenting is the acknowledgement of client-authoritative possession.
    conversation_id = create_session(client, "npc_laozhou")  # no evidence yet
    data = present(client, conversation_id, ["E02"])
    assert data["triggered_disclosure_ids"] == ["D01"]
