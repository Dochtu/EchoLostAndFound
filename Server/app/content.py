"""Approved content loading and validation.

Two JSON files are vendored under `app/content/`:
  * `ch01_dialogue.json` - fixed lines, topics, disclosure (D) rules;
  * `ch01_evidence.json` - the M3-B approved evidence catalog, used only to
    validate that an evidence id / field id exists in the current content
    version.  The server never derives new evidence from it.

The service refuses to start on a malformed or version-mismatched bundle, so
a deployment cannot silently serve lines from another content version.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

CONTENT_VERSION = "story-v1.0-phase2"

_DIALOGUE_KEYS = frozenset({"content_version", "npcs", "disclosures", "provenance"})
_NPC_KEYS = frozenset(
    {
        "npc_id",
        "display_name",
        "allowed_evidence_ids",
        "opening_segments",
        "topics",
        "free_text_intents",
    }
)
_TOPIC_KEYS = frozenset(
    {"topic_id", "label", "segments", "requires_disclosure_ids", "requires_observed_field_ids"}
)
_SEGMENT_KEYS = frozenset({"content_ref", "text"})
_INTENT_KEYS = frozenset({"keywords", "topic_id"})
_DISCLOSURE_KEYS = frozenset(
    {
        "disclosure_id",
        "npc_id",
        "kind",
        "required_evidence_ids",
        "required_observed_field_ids",
        "segments",
    }
)
_EVIDENCE_KEYS = frozenset({"evidence_id", "fields"})
_EVIDENCE_FIELD_KEYS = frozenset({"field_id"})


class ContentError(ValueError):
    """The vendored content bundle is invalid or inconsistent."""


@dataclass(frozen=True)
class Segment:
    content_ref: str
    text: str

    def to_payload(self) -> dict[str, str]:
        return {"content_ref": self.content_ref, "text": self.text}


@dataclass(frozen=True)
class TopicDefinition:
    topic_id: str
    label: str
    segments: tuple[Segment, ...]
    requires_disclosure_ids: frozenset[str]
    requires_observed_field_ids: frozenset[str]

    def is_available(self, triggered_disclosures: set[str], observed_fields: set[str]) -> bool:
        if not self.requires_disclosure_ids.issubset(triggered_disclosures):
            return False
        return self.requires_observed_field_ids.issubset(observed_fields)


@dataclass(frozen=True)
class FreeTextIntent:
    keywords: tuple[str, ...]
    topic_id: str

    def matches(self, text: str) -> bool:
        folded = text.casefold()
        return any(keyword.casefold() in folded for keyword in self.keywords)


@dataclass(frozen=True)
class NpcProfile:
    npc_id: str
    display_name: str
    allowed_evidence_ids: frozenset[str]
    opening_segments: tuple[Segment, ...]
    topics: tuple[TopicDefinition, ...]
    free_text_intents: tuple[FreeTextIntent, ...]

    def topic(self, topic_id: str) -> TopicDefinition | None:
        for topic in self.topics:
            if topic.topic_id == topic_id:
                return topic
        return None


@dataclass(frozen=True)
class DisclosureDefinition:
    disclosure_id: str
    npc_id: str
    kind: str
    required_evidence_ids: frozenset[str]
    required_observed_field_ids: frozenset[str]
    segments: tuple[Segment, ...]

    def requirements_met(
        self, presented_evidence: set[str], observed_fields: set[str]
    ) -> bool:
        if not self.required_evidence_ids.issubset(presented_evidence):
            return False
        return self.required_observed_field_ids.issubset(observed_fields)


@dataclass(frozen=True)
class DialogueContent:
    content_version: str
    npcs: dict[str, NpcProfile]
    disclosures: tuple[DisclosureDefinition, ...]
    provisional_content_refs: tuple[str, ...]

    def disclosures_for(self, npc_id: str) -> tuple[DisclosureDefinition, ...]:
        return tuple(d for d in self.disclosures if d.npc_id == npc_id)


@dataclass(frozen=True)
class EvidenceFieldIndex:
    content_version: str
    fields_by_evidence: dict[str, tuple[str, ...]]
    evidence_for_field: dict[str, str]

    def evidence_ids(self) -> frozenset[str]:
        return frozenset(self.fields_by_evidence)

    def fields_of(self, evidence_id: str) -> tuple[str, ...]:
        return self.fields_by_evidence.get(evidence_id, ())


@dataclass(frozen=True)
class ContentBundle:
    dialogue: DialogueContent
    evidence: EvidenceFieldIndex

    @property
    def content_version(self) -> str:
        return self.dialogue.content_version


def _reject_unknown(obj: Any, allowed: frozenset[str], where: str) -> None:
    if not isinstance(obj, dict):
        raise ContentError(f"{where} must be a JSON object")
    unknown = set(obj) - allowed
    if unknown:
        raise ContentError(f"{where} has unknown fields: {sorted(unknown)}")


def _require_str(obj: dict[str, Any], key: str, where: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ContentError(f"{where}.{key} must be a non-empty string")
    return value


def _require_str_list(obj: dict[str, Any], key: str, where: str) -> tuple[str, ...]:
    value = obj.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ContentError(f"{where}.{key} must be an array of strings")
    return tuple(value)


def _parse_segments(raw: Any, where: str) -> tuple[Segment, ...]:
    if not isinstance(raw, list):
        raise ContentError(f"{where}.segments must be an array")
    segments: list[Segment] = []
    for index, item in enumerate(raw):
        _reject_unknown(item, _SEGMENT_KEYS, f"{where}.segments[{index}]")
        segments.append(
            Segment(
                content_ref=_require_str(item, "content_ref", f"{where}.segments[{index}]"),
                text=_require_str(item, "text", f"{where}.segments[{index}]"),
            )
        )
    return tuple(segments)


def parse_dialogue(raw: Any) -> DialogueContent:
    _reject_unknown(raw, _DIALOGUE_KEYS, "$")
    version = _require_str(raw, "content_version", "$")
    npcs_raw = raw.get("npcs")
    if not isinstance(npcs_raw, list) or not npcs_raw:
        raise ContentError("$.npcs must be a non-empty array")

    npcs: dict[str, NpcProfile] = {}
    for npc_index, npc_raw in enumerate(npcs_raw):
        where = f"$.npcs[{npc_index}]"
        _reject_unknown(npc_raw, _NPC_KEYS, where)
        npc_id = _require_str(npc_raw, "npc_id", where)
        if npc_id in npcs:
            raise ContentError(f"duplicate npc_id {npc_id!r}")

        topics_raw = npc_raw.get("topics", [])
        if not isinstance(topics_raw, list):
            raise ContentError(f"{where}.topics must be an array")
        topics: list[TopicDefinition] = []
        seen_topics: set[str] = set()
        for topic_index, topic_raw in enumerate(topics_raw):
            topic_where = f"{where}.topics[{topic_index}]"
            _reject_unknown(topic_raw, _TOPIC_KEYS, topic_where)
            topic_id = _require_str(topic_raw, "topic_id", topic_where)
            if topic_id in seen_topics:
                raise ContentError(f"duplicate topic_id {topic_id!r} for {npc_id}")
            seen_topics.add(topic_id)
            topics.append(
                TopicDefinition(
                    topic_id=topic_id,
                    label=_require_str(topic_raw, "label", topic_where),
                    segments=_parse_segments(topic_raw.get("segments", []), topic_where),
                    requires_disclosure_ids=frozenset(
                        _require_str_list(topic_raw, "requires_disclosure_ids", topic_where)
                    ),
                    requires_observed_field_ids=frozenset(
                        _require_str_list(topic_raw, "requires_observed_field_ids", topic_where)
                    ),
                )
            )

        intents_raw = npc_raw.get("free_text_intents", [])
        if not isinstance(intents_raw, list):
            raise ContentError(f"{where}.free_text_intents must be an array")
        intents: list[FreeTextIntent] = []
        for intent_index, intent_raw in enumerate(intents_raw):
            intent_where = f"{where}.free_text_intents[{intent_index}]"
            _reject_unknown(intent_raw, _INTENT_KEYS, intent_where)
            keywords = _require_str_list(intent_raw, "keywords", intent_where)
            if not keywords:
                raise ContentError(f"{intent_where}.keywords must not be empty")
            intents.append(
                FreeTextIntent(
                    keywords=keywords,
                    topic_id=_require_str(intent_raw, "topic_id", intent_where),
                )
            )

        npcs[npc_id] = NpcProfile(
            npc_id=npc_id,
            display_name=_require_str(npc_raw, "display_name", where),
            allowed_evidence_ids=frozenset(
                _require_str_list(npc_raw, "allowed_evidence_ids", where)
            ),
            opening_segments=_parse_segments(npc_raw.get("opening_segments", []), where),
            topics=tuple(topics),
            free_text_intents=tuple(intents),
        )

    disclosures_raw = raw.get("disclosures")
    if not isinstance(disclosures_raw, list):
        raise ContentError("$.disclosures must be an array")
    disclosures: list[DisclosureDefinition] = []
    seen_disclosures: set[tuple[str, str]] = set()
    for index, disclosure_raw in enumerate(disclosures_raw):
        where = f"$.disclosures[{index}]"
        _reject_unknown(disclosure_raw, _DISCLOSURE_KEYS, where)
        disclosure_id = _require_str(disclosure_raw, "disclosure_id", where)
        npc_id = _require_str(disclosure_raw, "npc_id", where)
        key = (disclosure_id, npc_id)
        if key in seen_disclosures:
            raise ContentError(f"duplicate disclosure {disclosure_id!r} for {npc_id}")
        seen_disclosures.add(key)
        disclosures.append(
            DisclosureDefinition(
                disclosure_id=disclosure_id,
                npc_id=npc_id,
                kind=_require_str(disclosure_raw, "kind", where),
                required_evidence_ids=frozenset(
                    _require_str_list(disclosure_raw, "required_evidence_ids", where)
                ),
                required_observed_field_ids=frozenset(
                    _require_str_list(disclosure_raw, "required_observed_field_ids", where)
                ),
                segments=_parse_segments(disclosure_raw.get("segments", []), where),
            )
        )

    provenance = raw.get("provenance", {})
    provisional = ()
    if isinstance(provenance, dict):
        provisional_value = provenance.get("provisional_content_refs", [])
        if isinstance(provisional_value, list):
            provisional = tuple(item for item in provisional_value if isinstance(item, str))

    return DialogueContent(
        content_version=version,
        npcs=npcs,
        disclosures=tuple(disclosures),
        provisional_content_refs=provisional,
    )


def parse_evidence(raw: Any) -> EvidenceFieldIndex:
    if not isinstance(raw, dict):
        raise ContentError("evidence catalog must be a JSON object")
    version = raw.get("content_version")
    if not isinstance(version, str) or not version.strip():
        raise ContentError("evidence catalog is missing content_version")
    entries = raw.get("evidence")
    if not isinstance(entries, list) or not entries:
        raise ContentError("evidence catalog must contain a non-empty evidence array")

    fields_by_evidence: dict[str, tuple[str, ...]] = {}
    evidence_for_field: dict[str, str] = {}
    for index, entry in enumerate(entries):
        where = f"$.evidence[{index}]"
        if not isinstance(entry, dict):
            raise ContentError(f"{where} must be a JSON object")
        evidence_id = _require_str(entry, "evidence_id", where)
        if evidence_id in fields_by_evidence:
            raise ContentError(f"duplicate evidence_id {evidence_id!r}")
        fields_raw = entry.get("fields", [])
        if not isinstance(fields_raw, list) or not fields_raw:
            raise ContentError(f"{where}.fields must be a non-empty array")
        field_ids: list[str] = []
        for field_index, field_raw in enumerate(fields_raw):
            field_where = f"{where}.fields[{field_index}]"
            if not isinstance(field_raw, dict):
                raise ContentError(f"{field_where} must be a JSON object")
            field_id = _require_str(field_raw, "field_id", field_where)
            if field_id in evidence_for_field:
                raise ContentError(f"duplicate field_id {field_id!r}")
            evidence_for_field[field_id] = evidence_id
            field_ids.append(field_id)
        fields_by_evidence[evidence_id] = tuple(field_ids)

    return EvidenceFieldIndex(
        content_version=version,
        fields_by_evidence=fields_by_evidence,
        evidence_for_field=evidence_for_field,
    )


def _check_references(dialogue: DialogueContent, evidence: EvidenceFieldIndex) -> None:
    known_evidence = evidence.evidence_ids()
    known_fields = set(evidence.evidence_for_field)

    for npc in dialogue.npcs.values():
        unknown_allowed = npc.allowed_evidence_ids - known_evidence
        if unknown_allowed:
            raise ContentError(
                f"{npc.npc_id}.allowed_evidence_ids references unknown ids {sorted(unknown_allowed)}"
            )
        if not npc.opening_segments:
            raise ContentError(f"{npc.npc_id} has no opening segments")
        topic_ids = {topic.topic_id for topic in npc.topics}
        for topic in npc.topics:
            unknown_fields = topic.requires_observed_field_ids - known_fields
            if unknown_fields:
                raise ContentError(
                    f"topic {topic.topic_id} requires unknown fields {sorted(unknown_fields)}"
                )
        for intent in npc.free_text_intents:
            if intent.topic_id not in topic_ids:
                raise ContentError(
                    f"free-text intent of {npc.npc_id} targets unknown topic {intent.topic_id!r}"
                )

    for disclosure in dialogue.disclosures:
        if disclosure.npc_id not in dialogue.npcs:
            raise ContentError(f"disclosure {disclosure.disclosure_id} targets unknown NPC")
        unknown_evidence = disclosure.required_evidence_ids - known_evidence
        if unknown_evidence:
            raise ContentError(
                f"disclosure {disclosure.disclosure_id} requires unknown evidence "
                f"{sorted(unknown_evidence)}"
            )
        unknown_fields = disclosure.required_observed_field_ids - known_fields
        if unknown_fields:
            raise ContentError(
                f"disclosure {disclosure.disclosure_id} requires unknown fields "
                f"{sorted(unknown_fields)}"
            )


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContentError(f"content file not found: {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise ContentError(f"content file {path.name} is not valid JSON: {exc}") from exc


def load_content(content_dir: Path) -> ContentBundle:
    dialogue = parse_dialogue(_load_json(content_dir / "ch01_dialogue.json"))
    evidence = parse_evidence(_load_json(content_dir / "ch01_evidence.json"))
    if dialogue.content_version != evidence.content_version:
        raise ContentError(
            "content_version mismatch: "
            f"dialogue={dialogue.content_version!r} evidence={evidence.content_version!r}"
        )
    _check_references(dialogue, evidence)
    return ContentBundle(dialogue=dialogue, evidence=evidence)


def all_disclosure_ids(dialogue: DialogueContent, npc_id: str) -> Iterable[str]:
    return (disclosure.disclosure_id for disclosure in dialogue.disclosures_for(npc_id))
