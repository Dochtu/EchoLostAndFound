"""Provider selection based on explicit configuration, never on fallback magic.

In ``mock`` entry mode the external adapter is never even constructed, so a
fully populated ``LLM_*`` environment cannot cause a network request.  In
``live`` mode the caller must supply a usable :class:`RequestBudget`; without
one the provider is disabled rather than silently unmetered.
"""

from __future__ import annotations

from pathlib import Path

from ..budget import RequestBudget
from ..config import Settings
from .base import DisabledProvider, NpcAiProvider
from .llm_provider import LlmProvider
from .mock_provider import MockAiProvider, load_scenario_set


def build_provider(
    settings: Settings,
    content_dir: Path | None = None,
    *,
    budget: RequestBudget | None = None,
    transport=None,
) -> NpcAiProvider:
    if settings.entry_mode == "mock" or settings.model_provider == "mock":
        directory = content_dir or settings.content_dir
        return MockAiProvider(load_scenario_set(directory / "mock_ai_fixtures.json"))
    if settings.model_provider == "llm":
        if budget is None:
            return DisabledProvider()
        provider = LlmProvider(settings, budget=budget, transport=transport)
        return provider if provider.available else DisabledProvider()
    return DisabledProvider()
