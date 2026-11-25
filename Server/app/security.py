"""Request/response validation that does not depend on any model provider.

The same rules protect every provider:
  * generated text is never longer than 400 characters (M3-B contract);
  * markup is rejected, because Unity WebGL renders TMP and must not receive
    rich-text/HTML fragments from a model;
  * prompt-injection phrases are rejected;
  * a model reply can only contain `npc_id`, `text`, and an optional
    `suggested_topic_id`; it has no field that could grant evidence, change a
    quest state, or trigger a disclosure.

`validate_model_reply` raises `ModelOutputRejected`; callers translate that
into the DataSchema `fallback_reason` (invalid_output / unsafe_output) instead
of failing the conversation.
"""

from __future__ import annotations

import json
import re
from typing import Any

MAX_REPLY_TEXT_LENGTH = 400
FORBIDDEN_FRAGMENTS = (
    "系统提示",
    "忽略上面",
    "忽略以上",
    "上面的指令",
    "系统消息",
    "开发者",
    "提示词",
    "剧本",
    "api key",
    "apikey",
    "sk-",
)
_ALLOWED_REPLY_KEYS = frozenset({"npc_id", "text", "suggested_topic_id"})
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_NORMALIZE_STRIP = re.compile(r"[\s\u3000，。、！？；：,.!?;:\"'“”‘’（）()\[\]【】…—\-]+")
#: A forbidden fact only counts when enough of it survives normalization;
#: short fragments ("表", "灯") would otherwise reject innocent replies.
_MIN_FACT_CHARS = 8
#: Evidence tickets look like ``E01``.  A reply may only cite tickets this NPC
#: has actually been shown; anything else would invent a lead.
_EVIDENCE_MENTION = re.compile(r"(?<![A-Za-z0-9])E\d{2}(?![0-9])")


class ModelOutputRejected(Exception):
    """The provider returned something the client must not receive."""

    def __init__(self, fallback_reason: str, detail: str) -> None:
        super().__init__(f"{fallback_reason}: {detail}")
        self.fallback_reason = fallback_reason
        self.detail = detail


def validate_bridge_text(
    raw_text: str,
    *,
    forbidden_facts: tuple[str, ...] = (),
    known_evidence_ids: tuple[str, ...] | None = None,
) -> str:
    """Validate free-form in-character text from *any* provider.

    This is the provider-independent half of :func:`validate_model_reply`; the
    policy layer applies it again so a custom/buggy provider cannot bypass the
    model adapter's own validation.  ``forbidden_facts`` are approved lines the
    player has not unlocked yet: quoting (or near-quoting) one is a safety
    failure, not a style problem.  ``known_evidence_ids`` (when not ``None``)
    forbids the reply from citing a ticket the NPC has never been shown.
    """

    if not isinstance(raw_text, str):
        raise ModelOutputRejected("invalid_output", "text_not_string")
    text = raw_text.strip()
    if not text:
        raise ModelOutputRejected("invalid_output", "empty_text")
    if len(text) > MAX_REPLY_TEXT_LENGTH:
        raise ModelOutputRejected("invalid_output", "text_too_long")
    if _CONTROL_CHARS.search(text):
        raise ModelOutputRejected("unsafe_output", "control_chars")
    if "<" in text or ">" in text:
        raise ModelOutputRejected("unsafe_output", "markup_detected")

    lowered = text.casefold()
    if any(fragment in lowered for fragment in FORBIDDEN_FRAGMENTS):
        raise ModelOutputRejected("unsafe_output", "forbidden_fragment")
    if facts_mentioned(text, forbidden_facts):
        raise ModelOutputRejected("unsafe_output", "locked_fact_disclosed")
    if known_evidence_ids is not None:
        allowed = set(known_evidence_ids)
        cited = {match.group(0) for match in _EVIDENCE_MENTION.finditer(text)}
        if cited - allowed:
            raise ModelOutputRejected("unsafe_output", "unknown_evidence_cited")
    return text


def _normalize(text: str) -> str:
    return _NORMALIZE_STRIP.sub("", text.casefold())


def facts_mentioned(
    text: str, forbidden_facts: tuple[str, ...]
) -> tuple[str, ...]:
    """Return the locked approved lines that ``text`` reproduces.

    Deliberately conservative: a fact must survive normalization (whitespace
    and punctuation removed) and be at least ``_MIN_FACT_CHARS`` characters,
    so ordinary one-sentence replies are not rejected for sharing a phrase.
    """

    if not forbidden_facts:
        return ()
    normalized = _normalize(text)
    hits: list[str] = []
    for fact in forbidden_facts:
        needle = _normalize(fact)
        if len(needle) >= _MIN_FACT_CHARS and needle in normalized:
            hits.append(fact)
    return tuple(hits)


def validate_model_reply(
    raw_content: str,
    *,
    npc_id: str,
    available_topic_ids: set[str],
    forbidden_facts: tuple[str, ...] = (),
    known_evidence_ids: tuple[str, ...] | None = None,
) -> tuple[str, str | None]:
    """Parse and validate a model JSON reply.

    Returns ``(text, suggested_topic_id)``.  Raises ModelOutputRejected with
    fallback_reason ``invalid_output`` or ``unsafe_output``.
    """

    if raw_content is None or not raw_content.strip():
        raise ModelOutputRejected("invalid_output", "empty_payload")
    if len(raw_content) > 4096:
        raise ModelOutputRejected("invalid_output", "payload_too_large")

    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise ModelOutputRejected("invalid_output", f"invalid_json_line_{exc.lineno}") from exc

    if not isinstance(parsed, dict):
        raise ModelOutputRejected("invalid_output", "root_not_object")

    unknown = set(parsed) - _ALLOWED_REPLY_KEYS
    if unknown:
        raise ModelOutputRejected("invalid_output", "unknown_field")

    data: dict[str, Any] = parsed
    raw_npc = data.get("npc_id")
    if not isinstance(raw_npc, str):
        raise ModelOutputRejected("invalid_output", "missing_npc_id")
    if raw_npc != npc_id:
        raise ModelOutputRejected("invalid_output", "npc_id_mismatch")

    text = data.get("text")
    if not isinstance(text, str):
        raise ModelOutputRejected("invalid_output", "missing_text")
    text = validate_bridge_text(
        text,
        forbidden_facts=forbidden_facts,
        known_evidence_ids=known_evidence_ids,
    )

    suggestion = data.get("suggested_topic_id")
    if suggestion is not None and not isinstance(suggestion, str):
        raise ModelOutputRejected("invalid_output", "invalid_suggestion_type")
    if isinstance(suggestion, str) and suggestion not in available_topic_ids:
        # Unknown suggestions are dropped, never executed.
        suggestion = None

    return text, suggestion


def safe_request_id(candidate: str | None) -> str | None:
    if not candidate:
        return None
    candidate = candidate.strip()
    if not _REQUEST_ID_PATTERN.fullmatch(candidate):
        return None
    return candidate


def contains_forbidden_fragment(text: str) -> bool:
    lowered = text.casefold()
    return any(fragment in lowered for fragment in FORBIDDEN_FRAGMENTS)
