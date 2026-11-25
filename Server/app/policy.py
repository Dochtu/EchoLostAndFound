"""Deterministic dialogue policy: fixed lines first, model extension second,
fallback last.

Every branch that can change *game state* is decided here from approved
content.  A model can only supply `generated_bridge` text; it cannot add
evidence, trigger a disclosure, unlock a topic, or close a session.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass

from .config import Settings
from .content import (
    ContentBundle,
    DisclosureDefinition,
    NpcProfile,
    Segment,
    TopicDefinition,
)
from .errors import invalid_request, not_found, precondition_failed
from .providers.base import OUTCOME_COMPLETED, ProviderRequest, ProviderResult, NpcAiProvider
from .knowledge import KnowledgeScope, build_knowledge_scope
from .security import ModelOutputRejected, validate_bridge_text
from .sessions import Session, STATUS_CLOSED

_EVIDENCE_ID = re.compile(r"^E[0-9]{2}$")
_FIELD_ID = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")

SOURCE_FIXED_LINE = "fixed_line"
SOURCE_FALLBACK = "fallback"


@dataclass(frozen=True)
class ProviderInfo:
    kind: str
    provider_id: str
    is_synthetic: bool

    def to_payload(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "id": self.provider_id,
            "is_synthetic": self.is_synthetic,
        }


@dataclass(frozen=True)
class TurnData:
    turn_id: str
    source: str
    fixed_segments: tuple[Segment, ...]
    generated_bridge: str | None
    fallback_reason: str | None
    suggested_topic_id: str | None
    provider: ProviderInfo
    available_topic_ids: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "turn_id": self.turn_id,
            "status": "completed",
            "source": self.source,
            "fixed_segments": [segment.to_payload() for segment in self.fixed_segments],
            "fixed_delivery_token": None,
            "generated_bridge": self.generated_bridge,
            "fallback_reason": self.fallback_reason,
            "suggested_actions": [
                {"topic_id": self.suggested_topic_id, "kind": "topic"}
            ]
            if self.suggested_topic_id
            else [],
            "provider": self.provider.to_payload(),
            "available_topic_ids": list(self.available_topic_ids),
        }


@dataclass(frozen=True)
class PresentationData:
    presented_evidence_ids: tuple[str, ...]
    newly_presented_field_ids: tuple[str, ...]
    already_presented: bool
    available_disclosure_ids: tuple[str, ...]
    triggered_disclosure_ids: tuple[str, ...]
    fixed_segments: tuple[Segment, ...]
    event_ids: tuple[str, ...]
    observed_field_ids: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "presented_evidence_ids": list(self.presented_evidence_ids),
            "newly_presented_field_ids": list(self.newly_presented_field_ids),
            "already_presented": self.already_presented,
            "available_disclosure_ids": list(self.available_disclosure_ids),
            "triggered_disclosure_ids": list(self.triggered_disclosure_ids),
            "fixed_segments": [segment.to_payload() for segment in self.fixed_segments],
            "event_ids": list(self.event_ids),
            "observed_field_ids": list(self.observed_field_ids),
        }


def _event_id() -> str:
    return f"evt_{uuid.uuid4()}"


class DialoguePolicy:
    def __init__(
        self,
        content: ContentBundle,
        settings: Settings,
        provider: NpcAiProvider,
    ) -> None:
        self._content = content
        self._settings = settings
        self._provider = provider

    # ------------------------------------------------------------------ NPC

    def npc(self, npc_id: str) -> NpcProfile:
        profile = self._content.dialogue.npcs.get(npc_id)
        if profile is None:
            raise not_found("未知的 NPC。")
        return profile

    def opening(self, profile: NpcProfile) -> tuple[Segment, ...]:
        return profile.opening_segments

    def available_topics(self, profile: NpcProfile, session: Session) -> list[TopicDefinition]:
        return [
            topic
            for topic in profile.topics
            if topic.is_available(session.triggered_disclosure_ids, session.observed_field_ids)
        ]

    # -------------------------------------------------------------- validate

    def validate_evidence_ids(self, evidence_ids: list[str]) -> None:
        known = self._content.evidence
        for evidence_id in evidence_ids:
            if not _EVIDENCE_ID.fullmatch(evidence_id):
                raise invalid_request("证据编号格式无效。", details={"evidence_id": evidence_id})
            if evidence_id not in known.fields_by_evidence:
                raise not_found("未知的证据。")

    def validate_field_ids(self, field_ids: list[str]) -> None:
        known = self._content.evidence
        for field_id in field_ids:
            if not _FIELD_ID.fullmatch(field_id):
                raise invalid_request("字段编号格式无效。", details={"field_id": field_id})
            if field_id not in known.evidence_for_field:
                raise not_found("未知的证据字段。")

    def _merge_client_state(
        self,
        session: Session,
        evidence_ids: list[str] | None,
        observed_field_ids: list[str] | None,
    ) -> None:
        """Record what the client reports it already holds.

        This is an acknowledgement of client-authoritative M3-B state, not a
        grant: the server never adds evidence the client did not send, and the
        response never contains an evidence-granting field.
        """

        if evidence_ids:
            self.validate_evidence_ids(evidence_ids)
            session.acquired_evidence_ids.update(evidence_ids)
        if observed_field_ids:
            self.validate_field_ids(observed_field_ids)
            session.observed_field_ids.update(observed_field_ids)

    # ----------------------------------------------------------------- turns

    async def respond(
        self,
        profile: NpcProfile,
        session: Session,
        *,
        topic_id: str | None,
        text: str | None,
        evidence_ids: list[str] | None,
        observed_field_ids: list[str] | None,
        request_id: str,
        timeout_ms: int | None,
    ) -> TurnData:
        self._merge_client_state(session, evidence_ids, observed_field_ids)

        if topic_id is not None:
            topic = profile.topic(topic_id)
            if topic is None:
                raise not_found("未知的对话话题。")
            if not topic.is_available(session.triggered_disclosure_ids, session.observed_field_ids):
                raise precondition_failed("该话题尚未开放。")
            if topic_id.endswith(".leave"):
                session.status = STATUS_CLOSED
                session.ended_at = time.monotonic()
            return self._fixed_turn(profile, session, topic.segments, suggested_topic_id=None)

        assert text is not None
        if len(text.strip()) > self._settings.player_input_max_chars:
            raise invalid_request("玩家输入过长。")

        # Fixed lines first: an approved keyword intent is served without a
        # model call, even when a provider is configured.
        fixed_topic = self._match_fixed_intent(profile, session, text)
        if fixed_topic is not None:
            return self._fixed_turn(profile, session, fixed_topic.segments, suggested_topic_id=None)

        scope = build_knowledge_scope(
            self._content,
            profile,
            acquired_evidence_ids=session.acquired_evidence_ids,
            observed_field_ids=session.observed_field_ids,
            triggered_disclosure_ids=session.triggered_disclosure_ids,
        )
        request = ProviderRequest(
            request_id=request_id,
            npc_id=profile.npc_id,
            display_name=profile.display_name,
            player_input=text.strip(),
            acquired_evidence_ids=scope.known_evidence_ids,
            available_topic_ids=scope.available_topic_ids,
            timeout_ms=min(timeout_ms or self._settings.ai_timeout_ms, self._settings.ai_timeout_ms),
            content_version=self._content.content_version,
            session_id=session.conversation_id,
            knowledge=scope,
        )
        try:
            result = await self._provider.generate(request)
        except Exception:  # noqa: BLE001 - provider faults become a fallback result
            result = ProviderResult(
                outcome="model_unavailable",
                provider_kind="fallback",
                provider_id="provider_exception",
                is_synthetic=True,
                failure_detail="provider_exception",
            )

        return self._provider_turn(profile, session, result, scope)

    def _fixed_turn(
        self,
        profile: NpcProfile,
        session: Session,
        segments: tuple[Segment, ...],
        *,
        suggested_topic_id: str | None,
    ) -> TurnData:
        turn_id = f"turn_{uuid.uuid4()}"
        session.last_turn_id = turn_id
        return TurnData(
            turn_id=turn_id,
            source=SOURCE_FIXED_LINE,
            fixed_segments=segments,
            generated_bridge=None,
            fallback_reason=None,
            suggested_topic_id=suggested_topic_id,
            provider=ProviderInfo(
                kind="mock",
                provider_id="fixed-line-content",
                # Approved fixed content is not a model answer: report it as
                # synthetic so no client can mistake it for generated text.
                is_synthetic=True,
            ),
            available_topic_ids=tuple(
                topic.topic_id for topic in self.available_topics(profile, session)
            ),
        )

    def _provider_turn(
        self,
        profile: NpcProfile,
        session: Session,
        result: ProviderResult,
        scope: KnowledgeScope,
    ) -> TurnData:
        turn_id = f"turn_{uuid.uuid4()}"
        session.last_turn_id = turn_id
        available = tuple(topic.topic_id for topic in self.available_topics(profile, session))

        if result.outcome == OUTCOME_COMPLETED and result.text:
            # Defence in depth: the policy layer re-validates the text so a
            # custom provider cannot smuggle markup or prompt text past the
            # adapter's own checks.  Rejection becomes a normal fallback turn.
            try:
                bridge = validate_bridge_text(
                    result.text,
                    forbidden_facts=scope.forbidden_facts,
                    known_evidence_ids=scope.known_evidence_ids,
                )
            except ModelOutputRejected as exc:
                return TurnData(
                    turn_id=turn_id,
                    source=SOURCE_FALLBACK,
                    fixed_segments=(),
                    generated_bridge=None,
                    fallback_reason=exc.fallback_reason,
                    suggested_topic_id=None,
                    provider=ProviderInfo(
                        kind="fallback",
                        provider_id=result.provider_id,
                        is_synthetic=True,
                    ),
                    available_topic_ids=available,
                )
            suggestion = (
                result.suggested_topic_id
                if result.suggested_topic_id in available
                else None
            )
            return TurnData(
                turn_id=turn_id,
                source=result.provider_kind,
                fixed_segments=(),
                generated_bridge=bridge,
                fallback_reason=None,
                suggested_topic_id=suggestion,
                provider=ProviderInfo(
                    kind=result.provider_kind,
                    provider_id=result.provider_id,
                    is_synthetic=result.is_synthetic,
                ),
                available_topic_ids=available,
            )

        return TurnData(
            turn_id=turn_id,
            source=SOURCE_FALLBACK,
            fixed_segments=(),
            generated_bridge=None,
            fallback_reason=result.fallback_reason or "model_unavailable",
            suggested_topic_id=None,
            provider=ProviderInfo(
                kind="fallback",
                provider_id=result.provider_id,
                is_synthetic=True,
            ),
            available_topic_ids=available,
        )

    def _match_fixed_intent(
        self,
        profile: NpcProfile,
        session: Session,
        text: str,
    ) -> TopicDefinition | None:
        stripped = text.strip()
        available = {
            topic.topic_id: topic for topic in self.available_topics(profile, session)
        }
        for intent in profile.free_text_intents:
            if intent.matches(stripped) and intent.topic_id in available:
                return available[intent.topic_id]
        # A player may also say the exact approved option label.
        for topic in available.values():
            if topic.label == stripped:
                return topic
        return None

    # ------------------------------------------------------------ evidence

    def present(
        self,
        profile: NpcProfile,
        session: Session,
        evidence_ids: list[str],
        observed_field_ids: list[str],
    ) -> PresentationData:
        self.validate_evidence_ids(evidence_ids)
        self.validate_field_ids(observed_field_ids)

        unique_ids = list(dict.fromkeys(evidence_ids))
        for evidence_id in unique_ids:
            if evidence_id not in profile.allowed_evidence_ids:
                raise precondition_failed(
                    "该证据没有为此 NPC 配置已批准回应。",
                    details={"evidence_id": evidence_id},
                )

        # Client-authoritative possession: presenting is the acknowledgement.
        session.acquired_evidence_ids.update(unique_ids)
        session.observed_field_ids.update(observed_field_ids)

        newly_presented: list[str] = []
        for evidence_id in unique_ids:
            for field_id in self._content.evidence.fields_of(evidence_id):
                if field_id not in session.presented_field_ids:
                    newly_presented.append(field_id)

        already_presented = not newly_presented and all(
            evidence_id in session.presented_evidence_ids for evidence_id in unique_ids
        )
        session.presented_evidence_ids.update(unique_ids)
        session.presented_field_ids.update(self._all_fields(unique_ids))

        available_disclosures = self._satisfied_disclosures(profile, session)
        triggered_now: list[DisclosureDefinition] = []
        for disclosure in available_disclosures:
            if disclosure.disclosure_id not in session.triggered_disclosure_ids:
                triggered_now.append(disclosure)
        for disclosure in triggered_now:
            session.triggered_disclosure_ids.add(disclosure.disclosure_id)

        segments: list[Segment] = []
        for disclosure in triggered_now:
            segments.extend(disclosure.segments)

        event_ids: list[str] = []
        if not already_presented:
            event_ids.append(_event_id())
        event_ids.extend(_event_id() for _ in triggered_now)

        return PresentationData(
            presented_evidence_ids=tuple(sorted(session.presented_evidence_ids)),
            newly_presented_field_ids=tuple(newly_presented),
            already_presented=already_presented,
            available_disclosure_ids=tuple(
                sorted(
                    {d.disclosure_id for d in available_disclosures}
                    - session.triggered_disclosure_ids
                )
            ),
            triggered_disclosure_ids=tuple(
                disclosure.disclosure_id for disclosure in triggered_now
            ),
            fixed_segments=tuple(segments),
            event_ids=tuple(event_ids),
            observed_field_ids=tuple(sorted(session.observed_field_ids)),
        )

    def _all_fields(self, evidence_ids: list[str]) -> set[str]:
        return {
            field_id
            for evidence_id in evidence_ids
            for field_id in self._content.evidence.fields_of(evidence_id)
        }

    def _satisfied_disclosures(
        self, profile: NpcProfile, session: Session
    ) -> list[DisclosureDefinition]:
        return [
            disclosure
            for disclosure in self._content.dialogue.disclosures_for(profile.npc_id)
            if disclosure.requirements_met(
                session.presented_evidence_ids, session.observed_field_ids
            )
        ]
