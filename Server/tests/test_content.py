"""Content bundle contract: only approved lines, correct version, reserved NPCs."""

from __future__ import annotations

from conftest import CONTENT_DIR

from app.content import CONTENT_VERSION, load_content


def test_bundle_loads_and_pins_content_version():
    bundle = load_content(CONTENT_DIR)
    assert bundle.content_version == CONTENT_VERSION
    assert set(bundle.dialogue.npcs) == {"npc_laozhou", "npc_linyao"}
    assert "npc_xucheng" not in bundle.dialogue.npcs


def test_approved_lines_are_exact():
    dialogue = load_content(CONTENT_DIR).dialogue
    laozhou = dialogue.npcs["npc_laozhou"]
    assert laozhou.display_name == "老周"
    assert laozhou.opening_segments[0].text == (
        "这封从旧库搬过两回。我来对号，你来签。先看表背，失物只认号。"
    )
    b01 = laozhou.topic("opt.laozhou.ask_b01")
    assert b01 is not None
    assert b01.segments[0].text == "站台那晚在我印象里一直亮着。我还把那盏油灯拖到里头去了。"
    assert b01.segments[0].content_ref == "dialogue.CH01.B01.initial"

    linyao = dialogue.npcs["npc_linyao"]
    assert linyao.display_name == "林遥"
    assert linyao.opening_segments[0].text == (
        "公告上有一张我妈留的领取凭号。我把原来的带来了。表还在吗？"
    )


def test_disclosure_requirements_match_design():
    dialogue = load_content(CONTENT_DIR).dialogue
    by_npc = {
        (d.disclosure_id, d.npc_id): d for d in dialogue.disclosures
    }
    assert by_npc[("D01", "npc_laozhou")].required_evidence_ids == frozenset({"E02"})
    assert by_npc[("D02", "npc_linyao")].required_evidence_ids == frozenset({"E03", "E04"})
    assert by_npc[("D02", "npc_laozhou")].required_evidence_ids == frozenset({"E03", "E04"})
    assert by_npc[("D02", "npc_laozhou")].segments == ()
    assert by_npc[("D03", "npc_laozhou")].required_evidence_ids == frozenset({"E01", "E05"})
    engraving = by_npc[("REC.engraving", "npc_linyao")]
    assert engraving.required_evidence_ids == frozenset({"E01"})
    assert engraving.required_observed_field_ids == frozenset({"watch.back_engraving"})


def test_provisional_refs_are_declared_not_hidden():
    dialogue = load_content(CONTENT_DIR).dialogue
    assert "dialogue.CH01.opening.laozhou" in dialogue.provisional_content_refs
    assert "dialogue.CH01.linyao.refusal" in dialogue.provisional_content_refs
    # Documented refs must not be listed as provisional.
    assert "dialogue.CH01.B01.initial" not in dialogue.provisional_content_refs
    assert "dialogue.CH01.D02.linyao" not in dialogue.provisional_content_refs


def test_evidence_index_matches_m3b_catalog():
    evidence = load_content(CONTENT_DIR).evidence
    assert evidence.fields_of("E01") == (
        "watch.dial",
        "watch.back_engraving",
        "watch.serial_number",
        "watch.side_crown",
        "watch.crown_shaft_damage",
    )
    assert evidence.evidence_for_field["power_fault.timestamp"] == "E02"
    assert set(evidence.fields_by_evidence) == {"E01", "E02", "E03", "E04", "E05"}
