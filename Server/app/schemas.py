"""Pydantic request models.

Only request bodies are modelled; responses are assembled as plain dicts so
the JSON contract stays exactly what Docs/DataSchema.md and the Unity client
expect (no null-stripping, predictable key names, explicit empty lists).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

NPC_ID_PATTERN = r"^npc_[a-z][a-z0-9_]{0,40}$"
EVIDENCE_ID_PATTERN = r"^E[0-9]{2}$"
FIELD_ID_PATTERN = r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$"
TOPIC_ID_PATTERN = r"^[a-z][a-z0-9_.]{0,79}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class CreateSessionRequest(StrictModel):
    npc_id: str = Field(pattern=NPC_ID_PATTERN)
    evidence_ids: list[str] = Field(default_factory=list, max_length=64)
    observed_field_ids: list[str] = Field(default_factory=list, max_length=256)


class TurnRequest(StrictModel):
    """Exactly one of `topic_id` (fixed content) or `text` (free input)."""

    topic_id: str | None = Field(default=None, pattern=TOPIC_ID_PATTERN)
    text: str | None = Field(default=None, max_length=4000)
    evidence_ids: list[str] | None = Field(default=None, max_length=64)
    observed_field_ids: list[str] | None = Field(default=None, max_length=256)
    request_id: str | None = Field(default=None, max_length=64)
    timeout_ms: int | None = Field(default=None, ge=100, le=30000)

    @model_validator(mode="after")
    def _exactly_one_input(self) -> "TurnRequest":
        has_topic = self.topic_id is not None
        has_text = self.text is not None
        if has_topic == has_text:
            raise ValueError("topic_id and text are mutually exclusive and exactly one is required")
        if self.text is not None and not self.text.strip():
            raise ValueError("text must not be blank")
        return self


class PresentEvidenceRequest(StrictModel):
    evidence_ids: list[str] = Field(min_length=1, max_length=8)
    observed_field_ids: list[str] = Field(default_factory=list, max_length=256)


class CancelRequest(StrictModel):
    pass


class _FeedbackPlaceholder(StrictModel):
    """Keeps the module non-empty for older Pydantic versions."""
