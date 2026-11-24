"""End-to-end offline investigation flow across both NPCs."""

from __future__ import annotations

from conftest import (
    assert_error,
    build_client,
    create_session,
    fixed_texts,
    present,
    take_turn,
)

from app.content import load_content  # used by readers when extending the flow
from app.providers.base import OUTCOME_MODEL_UNAVAILABLE, ProviderResult


def test_offline_chapter01_flow(client):
    health = client.get("/api/v1/health").json()["data"]
    assert health["content_version"] == "story-v1.0-phase2"
    assert health["provider"]["kind"] == "mock"

    # --- 老周: fixed opening, fixed B01, D01 after the power-fault card.
    laozhou = create_session(client, "npc_laozhou")
    turn = take_turn(client, laozhou, topic_id="opt.laozhou.ask_b01")
    assert fixed_texts(turn) == ["站台那晚在我印象里一直亮着。我还把那盏油灯拖到里头去了。"]

    # Approved keyword input is served from fixed content, not the model.
    intent_turn = take_turn(client, laozhou, text="那盏灯呢")
    assert intent_turn["source"] == "fixed_line"
    assert intent_turn["generated_bridge"] is None

    d01 = present(client, laozhou, ["E02"])
    assert d01["triggered_disclosure_ids"] == ["D01"]
    assert d01["fixed_segments"][0]["text"] == "进水，二十一点十七。我的灯到二十才摆好。是黑过，中间那点我记混了。"

    repeat = take_turn(client, laozhou, topic_id="opt.laozhou.repeat_b01")
    assert repeat["fixed_segments"][0]["text"].startswith("站台那晚")

    # --- 林遥 starts a new session; 老周's conversation is untouched (M4-C).
    linyao = create_session(client, "npc_linyao")
    still_there = client.get(f"/api/v1/sessions/{laozhou}")
    assert still_there.status_code == 200
    assert still_there.json()["data"]["triggered_disclosure_ids"] == ["D01"]

    first_receipt = present(client, linyao, ["E03"])
    assert first_receipt["triggered_disclosure_ids"] == []
    d02 = present(client, linyao, ["E04"])
    assert d02["triggered_disclosure_ids"] == ["D02"]
    assert d02["fixed_segments"][0]["text"] == "沈禾，是我妈妈。这个号和她放在家里那张一样。她写着要我自己领。"

    # Back engraving must have been observed, not merely owned.
    recognition = present(client, linyao, ["E01"], ["watch.back_engraving"])
    assert "REC.engraving" in recognition["triggered_disclosure_ids"]
    engraving = take_turn(client, linyao, topic_id="opt.linyao.ask_engraving")
    assert engraving["fixed_segments"][0]["content_ref"] == "dialogue.CH01.linyao.engraving"

    # Every payload keeps the contract: no evidence grants, no rule commands.
    forbidden = {"granted_evidence_ids", "rule_commands", "quest_state", "add_evidence"}
    for payload in (d01, d02, recognition, engraving):
        assert forbidden.isdisjoint(payload)

    leave = take_turn(client, linyao, topic_id="opt.linyao.leave")
    assert leave["status"] == "completed"
    assert_error(client.get(f"/api/v1/sessions/{linyao}"), 410, "TURN_EXPIRED")


def test_sessions_are_not_persisted_across_processes(content, scenarios):
    with build_client(content, scenarios) as first_process:
        conversation_id = create_session(first_process, "npc_laozhou")
    with build_client(content, scenarios) as second_process:
        assert_error(
            second_process.get(f"/api/v1/sessions/{conversation_id}"), 404, "NOT_FOUND"
        )


def test_fixed_content_works_without_any_model(content, scenarios):
    class NoModel:
        provider_id = "none"
        kind = "fallback"
        is_synthetic = True
        available = False

        def __init__(self):
            self.calls = 0

        async def generate(self, request):
            self.calls += 1
            return ProviderResult(
                outcome=OUTCOME_MODEL_UNAVAILABLE,
                provider_kind="fallback",
                provider_id="none",
                is_synthetic=True,
                failure_detail="no_model_configured",
            )

    offline_model = NoModel()
    with build_client(content, scenarios, provider=offline_model) as offline:
        conversation_id = create_session(offline, "npc_laozhou")
        opening = offline.get(f"/api/v1/sessions/{conversation_id}")
        assert opening.status_code == 200
        turn = take_turn(offline, conversation_id, topic_id="opt.laozhou.ask_b01")
        assert turn["source"] == "fixed_line"
        # A fixed topic must never reach the provider at all.
        assert offline_model.calls == 0
        # Free input without a model degrades to a structured fallback, not an error.
        fallback = take_turn(offline, conversation_id, text="随便聊点别的")
        assert fallback["source"] == "fallback"
        assert fallback["fallback_reason"] in {
            "model_unavailable",
            "unknown_intent",
        }
        assert offline_model.calls == 1
