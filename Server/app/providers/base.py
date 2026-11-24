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
from typing import Protocol

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

    @property
    def fallback_reason(self) -> str | None:
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
