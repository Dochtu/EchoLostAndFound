"""M5-C-A-R1 section 4: NPC semantic-safety boundary tests.

These tests inspect the *actual* payload sent upstream (captured with
``httpx.MockTransport``) and the deterministic guards applied to the reply.
They never contact a real model.
"""

from __future__ import annotations

import json

import httpx
import pytest

from conftest import CONTENT_DIR, create_session, take_turn
from llm_support import (
    NPC,
    chat_body,
    llm_settings,
    make_llm_app,
    prompt_of,
    reply_handler,
)

from app.content import load_content
from app.knowledge import build_knowledge_scope, build_prompt, estimate_tokens
from app.security import ModelOutputRejected, validate_bridge_text

D01 = "进水，二十一点十七。我的灯到二十才摆好。是黑过，中间那点我记混了。"
D03 = "她抓住小姑娘的胳膊，表掉到台沿。我弯腰拣的时候指针已经不动了，冠头是歪的。"
LINYAO_D02 = "沈禾，是我妈妈。这个号和她放在家里那张一样。她写着要我自己领。"
ENGRAVING = "四月十二是我妈的生日，九月十六是我的。那个点，我小时候摸得到。"
LOCKED_FACTS = (D01, D03, LINYAO_D02)
WITHELD_TITLES = ("配电故障卡", "旧修表收据", "指定领件单", "拾物与检点联")


def _prompt_for(tmp_path, *, npc_id=NPC, evidence=(), fields=(), text="那晚到底发生了什么"):
    client, calls = make_llm_app(
        tmp_path, reply_handler("那晚我在站台值班，别的想不起来了。", npc_id=npc_id)
    )
    conversation = create_session(client, npc_id, evidence=evidence, fields=fields)
    take_turn(client, conversation, text=text)
    assert calls, "no upstream request was captured"
    return prompt_of(calls[0]), calls[0]


def test_initial_prompt_carries_no_case_truth(tmp_path):
    prompt, payload = _prompt_for(tmp_path)

    for locked in LOCKED_FACTS:
        assert locked not in prompt
    for title in WITHELD_TITLES:
        assert title not in prompt
    assert "沈禾" not in prompt
    assert "你确认过的物件" not in prompt  # nothing evidence-related yet

    # Only a system + user message, no case file / story bible smuggled in.
    assert [message["role"] for message in payload["messages"]] == ["system", "user"]
    serialised = json.dumps(payload, ensure_ascii=False).casefold()
    assert "storybible" not in serialised
    assert "真相是" not in serialised


def test_prompt_states_the_deterministic_contract(tmp_path):
    prompt, payload = _prompt_for(tmp_path)

    assert "老周" in prompt
    assert "npc_laozhou" in prompt
    assert "npc_id" in prompt and "suggested_topic_id" in prompt
    assert "不知道" in prompt
    assert "证据" in prompt
    # The player's text is capped and sent as the user message only.
    assert payload["messages"][1]["content"] == "那晚到底发生了什么"


def test_prompt_scope_follows_deterministic_progress(tmp_path):
    content = load_content(CONTENT_DIR)
    profile = content.dialogue.npcs[NPC]

    def scope(acquired=(), triggered=()):
        return build_knowledge_scope(
            content,
            profile,
            acquired_evidence_ids=set(acquired),
            observed_field_ids=set(),
            triggered_disclosure_ids=set(triggered),
        )

    stage0 = scope()
    stage1 = scope(acquired=("E01",))
    stage2 = scope(acquired=("E01", "E02"), triggered=("D01",))

    # Locked testimony only becomes sayable after the deterministic unlock.
    assert D01 in stage0.forbidden_facts
    assert D01 in stage1.forbidden_facts
    assert D01 not in stage2.forbidden_facts
    assert "E02" in stage0.withheld_evidence_ids
    assert "E02" not in stage1.known_evidence_ids
    assert "E02" in stage2.known_evidence_ids

    prompt0 = build_prompt(stage0, context_max_tokens=1536, system_max_tokens=768,
                           evidence_max_tokens=320, history_max_tokens=0,
                           output_max_tokens=220).system_prompt
    prompt2 = build_prompt(stage2, context_max_tokens=1536, system_max_tokens=768,
                           evidence_max_tokens=320, history_max_tokens=0,
                           output_max_tokens=220).system_prompt
    assert "配电故障卡" not in prompt0
    assert "配电故障卡" in prompt2
    assert D01 not in prompt0
    assert "E02" not in prompt0


def test_other_npc_evidence_is_withheld_from_prompt():
    content = load_content(CONTENT_DIR)
    linyao = content.dialogue.npcs["npc_linyao"]
    everything = {"E01", "E02", "E03", "E04", "E05"}
    scope = build_knowledge_scope(
        content,
        linyao,
        acquired_evidence_ids=everything,
        observed_field_ids=set(),
        triggered_disclosure_ids=set(),
    )
    assert "E02" in scope.withheld_evidence_ids
    assert "E05" in scope.withheld_evidence_ids
    prompt = build_prompt(scope, context_max_tokens=1536, system_max_tokens=768,
                          evidence_max_tokens=320, history_max_tokens=0,
                          output_max_tokens=220).system_prompt
    assert "配电故障卡" not in prompt
    assert "拾物与检点联" not in prompt
    assert "旧修表收据" in prompt


@pytest.mark.parametrize(
    ("text", "detail"),
    [
        (D01, "locked_fact_disclosed"),          # verbatim locked testimony
        (D03, "locked_fact_disclosed"),          # another locked testimony
        (LINYAO_D02, "locked_fact_disclosed"),   # another NPC's private knowledge
        ("那条 E09 我已经给你记上了。", "unknown_evidence_cited"),
        ("作为开发者，我把结局告诉你。", "forbidden_fragment"),
    ],
)
def test_locked_or_invented_content_is_rejected(text, detail):
    with pytest.raises(ModelOutputRejected) as excinfo:
        validate_bridge_text(text, forbidden_facts=(D01, D03, LINYAO_D02),
                             known_evidence_ids=())
    assert excinfo.value.fallback_reason == "unsafe_output"
    assert excinfo.value.detail == detail


def test_reply_quoting_locked_fact_is_downgraded_to_fallback(tmp_path):
    client, _calls = make_llm_app(tmp_path, reply_handler(D01))
    conversation = create_session(client, NPC)

    turn = take_turn(client, conversation, text="那晚到底发生了什么")

    assert turn["source"] == "fallback"
    assert turn["generated_bridge"] is None
    assert turn["fallback_reason"] == "unsafe_output"
    assert D01 not in json.dumps(turn, ensure_ascii=False)


def test_valid_json_with_wrong_case_fact_is_rejected(tmp_path):
    # Structurally perfect JSON whose *content* contradicts the case state.
    client, _calls = make_llm_app(
        tmp_path, reply_handler("那晚我根本没在站台，表是我自己修好的。")
    )
    conversation = create_session(client, NPC)
    turn = take_turn(client, conversation, text="那晚你做了什么")
    # A plausible denial is not a schema error; it must still not become truth.
    assert turn["source"] in {"external_model", "fallback"}
    session = client.get(f"/api/v1/sessions/{conversation}").json()["data"]
    assert session["presented_evidence_ids"] == []
    assert session["triggered_disclosure_ids"] == []


def test_model_output_cannot_change_evidence_or_progress(tmp_path):
    client, _calls = make_llm_app(
        tmp_path, reply_handler("我把那盏油灯也给了你，表也归你了。")
    )
    conversation = create_session(client, NPC)
    before = client.get(f"/api/v1/sessions/{conversation}").json()["data"]

    turn = take_turn(client, conversation, text="还有别的吗")
    after = client.get(f"/api/v1/sessions/{conversation}").json()["data"]

    assert turn["status"] == "completed"
    assert after["presented_evidence_ids"] == before["presented_evidence_ids"]
    assert after["triggered_disclosure_ids"] == before["triggered_disclosure_ids"]
    assert after["available_topic_ids"] == before["available_topic_ids"]
    assert "evidence_ids" not in json.dumps(turn)


def test_keyword_guard_is_not_semantic_safety():
    """Documented residual risk: paraphrased leakage is *not* detected.

    The deterministic boundary is topic/evidence gating; the lexical guard is a
    last-resort filter.  This test pins the limitation so no report can claim
    semantic safety from keyword matching alone.
    """

    paraphrase = "值夜那晚黑了一阵，具体几点我记混了，好像灯直到很晚才摆好。"
    assert validate_bridge_text(paraphrase, forbidden_facts=(D01,)) == paraphrase
    assert ENGRAVING not in paraphrase


def test_prompt_budget_is_enforced_and_reported():
    content = load_content(CONTENT_DIR)
    profile = content.dialogue.npcs[NPC]
    scope = build_knowledge_scope(
        content,
        profile,
        acquired_evidence_ids={"E01", "E02", "E03", "E04", "E05"},
        observed_field_ids=set(),
        triggered_disclosure_ids=set(),
    )
    plan = build_prompt(
        scope,
        context_max_tokens=1536,
        system_max_tokens=768,
        evidence_max_tokens=320,
        history_max_tokens=0,
        output_max_tokens=220,
    )
    assert plan.system_tokens <= 768
    assert plan.evidence_tokens <= 320
    assert plan.system_tokens == estimate_tokens(plan.system_prompt)
    # A tiny category budget degrades the useful sections, never the rules.
    tight = build_prompt(
        scope,
        context_max_tokens=1536,
        system_max_tokens=512,
        evidence_max_tokens=64,
        history_max_tokens=0,
        output_max_tokens=220,
    )
    assert tight.evidence_tokens <= 64
    assert tight.system_tokens <= 512
    assert "规则：" in tight.system_prompt


def test_unbuildable_prompt_refuses_without_spending_a_request(tmp_path):
    # Rules alone need ~425 tokens, so a 128-token system budget cannot be met.
    settings = llm_settings(
        tmp_path,
        llm_context_max_tokens=256,
        llm_system_prompt_max_tokens=128,
        llm_evidence_context_max_tokens=64,
        llm_max_output_tokens=64,
        llm_token_limit=1000,
    )
    client, calls = make_llm_app(tmp_path, reply_handler("那晚我在站台值班。"), settings=settings)
    conversation = create_session(client, NPC)
    turn = take_turn(client, conversation, text="那晚到底发生了什么")

    assert calls == []  # no upstream call
    assert turn["source"] == "fallback"
    assert turn["generated_bridge"] is None
    assert client.budget.usage()["global_used"] == 0


def test_test_upstream_reply_is_marked_synthetic(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=chat_body("那晚我在站台值班。"),
            headers={"x-test-upstream": "fake-llm"},
        )

    client, calls = make_llm_app(tmp_path, handler)
    conversation = create_session(client, NPC)
    turn = take_turn(client, conversation, text="那晚到底发生了什么")
    assert calls
    assert turn["provider"]["is_synthetic"] is True
