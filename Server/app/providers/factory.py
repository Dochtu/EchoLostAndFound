"""Provider selection based on explicit configuration, never on fallback magic."""

from __future__ import annotations

from pathlib import Path

from ..config import Settings
from .base import DisabledProvider, NpcAiProvider
from .llm_provider import LlmProvider
from .mock_provider import MockAiProvider, load_scenario_set


def build_provider(settings: Settings, content_dir: Path | None = None) -> NpcAiProvider:
    if settings.model_provider == "mock":
        directory = content_dir or settings.content_dir
        return MockAiProvider(load_scenario_set(directory / "mock_ai_fixtures.json"))
    if settings.model_provider == "llm":
        provider = LlmProvider(settings)
        return provider if provider.available else DisabledProvider()
    return DisabledProvider()
