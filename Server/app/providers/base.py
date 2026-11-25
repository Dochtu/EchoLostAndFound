"""Provider abstraction shared by the mock and the real LLM adapters.

The shape mirrors M3-B `INpcAiProvider` / `NpcAiRequest` / `NpcAiReply`:

  request  = request_id + npc + player input + acquired evidence ids +
             available topic ids + timeout + content version
  result   = outcome + provider kind/id + is_synthetic + text +
             suggested topic + fallback reason

The struct has no evidence-grant, quest, or command field on purpose.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..knowledge import KnowledgeScope

OUTCOME_COMPLETED = "completed"
OUTCOME_TIMEOUT = "timeout"
OUTCOME_MODEL_UNAVAILABLE = "model_unavailable"
OUTCOME_INVALID_OUTPUT = "invalid_output"
OUTCOME_UNSAFE_OUTPUT = "unsafe_output"
OUTCOME_UNKNOWN_INTENT = "unknown_intent"

FALLBACK_BY_OUTCOME = {
    OUTCOME_TIMEOUT: "timeout",
    OUTCOME_MODEL_UNAVAILABLE: "model_unavailable",
    OUTCOME_INVALID_OUTPUT: "invalid_output",
    OUTCOME_UNSAFE_OUTPUT: "unsafe_output",
    OUTCOME_UNKNOWN_INTENT: "unknown_intent",
}


@dataclass(frozen=True)
class ProviderRequest:
    request_id: str
    npc_id: str
    display_name: str
    player_input: str
    acquired_evidence_ids: tuple[str, ...]
    available_topic_ids: tuple[str, ...]
    timeout_ms: int
    content_version: str
    session_id: str = ""
    #: Deterministic knowledge scope built by the policy layer.  When absent
    #: the provider falls back to the ids above and sends no evidence titles,
    #: which is strictly less information (never more).
    knowledge: "KnowledgeScope | None" = None


@dataclass(frozen=True)
class ProviderResult:
    outcome: str
    provider_kind: str  # "mock" | "external_model" | "fallback"
    provider_id: str
    is_synthetic: bool
    text: str | None = None
    suggested_topic_id: str | None = None
    failure_detail: str | None = None
    latency_ms: int = 0
    #: Token accounting reported by the upstream (0 when unknown -- the ledger
    #: already charged the conservative reservation in that case).
    consumed_tokens: int = 0
    usage_known: bool = False
    billing_uncertain: bool = False

    @property
    def fallback_reason(self) -> str | None:
        # Local, non-upstream refusals keep their precise reason so operators
        # and the health/ledger view can tell a spent budget from an outage.
        detail = self.failure_detail or ""
        if detail.startswith(("budget_", "ledger_")) or detail in {
            "circuit_open",
            "upstream_busy",
        }:
            return detail
        return FALLBACK_BY_OUTCOME.get(self.outcome)


class NpcAiProvider(Protocol):
    provider_id: str
    kind: str
    is_synthetic: bool
    available: bool

    async def generate(self, request: ProviderRequest) -> ProviderResult:
        """Resolve one free-text reply without blocking the event loop."""

    ...


class DisabledProvider:
    """Explicit 'no model configured' provider; never pretends to be an LLM."""

    provider_id = "disabled"
    kind = "fallback"
    is_synthetic = True
    available = False

    async def generate(self, request: ProviderRequest) -> ProviderResult:
        return ProviderResult(
            outcome=OUTCOME_MODEL_UNAVAILABLE,
            provider_kind="fallback",
            provider_id=self.provider_id,
            is_synthetic=True,
            failure_detail="provider_disabled",
        )
