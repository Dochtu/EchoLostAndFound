"""Deterministic mock provider used for local development and tests.

Every reply is explicitly labelled synthetic (``is_synthetic: true`` and the
approved "（模拟回复·仅测试，非正式台词）" prefix in fixture text).  It is not a
language model and must never be presented as one.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from ..security import ModelOutputRejected, validate_model_reply
from .base import (
    OUTCOME_COMPLETED,
    OUTCOME_INVALID_OUTPUT,
    OUTCOME_MODEL_UNAVAILABLE,
    OUTCOME_TIMEOUT,
    OUTCOME_UNKNOWN_INTENT,
    OUTCOME_UNSAFE_OUTPUT,
    ProviderRequest,
    ProviderResult,
)

DEFAULT_PROVIDER_ID = "mock-deterministic"


@dataclass(frozen=True)
class MockScenario:
    scenario_id: str
    npc_id: str
    behavior: str  # reply | timeout | transport_error
    input_keywords: tuple[str, ...]
    requires_evidence_ids: tuple[str, ...]
    excludes_evidence_ids: tuple[str, ...]
    raw_reply_json: str | None

    def matches(self, request: ProviderRequest) -> bool:
        if request.npc_id != self.npc_id:
            return False
        acquired = set(request.acquired_evidence_ids)
        if not set(self.requires_evidence_ids).issubset(acquired):
            return False
        if set(self.excludes_evidence_ids) & acquired:
            return False
        if not self.input_keywords:
            return True
        folded = request.player_input.casefold()
        return any(keyword.casefold() in folded for keyword in self.input_keywords)


@dataclass(frozen=True)
class MockScenarioSet:
    provider_id: str
    content_version: str
    scenarios: tuple[MockScenario, ...]

    def find(self, request: ProviderRequest) -> MockScenario | None:
        for scenario in self.scenarios:
            if scenario.matches(request):
                return scenario
        return None


def parse_scenario_set(raw: object) -> MockScenarioSet:
    if not isinstance(raw, dict):
        raise ValueError("mock fixtures must be a JSON object")
    provider_id = raw.get("provider_id")
    content_version = raw.get("content_version")
    scenarios_raw = raw.get("scenarios")
    if not isinstance(provider_id, str) or not provider_id:
        raise ValueError("mock fixtures are missing provider_id")
    if not isinstance(content_version, str) or not content_version:
        raise ValueError("mock fixtures are missing content_version")
    if not isinstance(scenarios_raw, list) or not scenarios_raw:
        raise ValueError("mock fixtures must contain at least one scenario")

    scenarios: list[MockScenario] = []
    for index, item in enumerate(scenarios_raw):
        if not isinstance(item, dict):
            raise ValueError(f"mock fixtures scenario {index} is not an object")
        behavior = item.get("behavior", "reply")
        if behavior not in {"reply", "timeout", "transport_error"}:
            raise ValueError(f"mock fixtures scenario {index} has unknown behavior {behavior!r}")
        scenarios.append(
            MockScenario(
                scenario_id=str(item.get("scenario_id", "")),
                npc_id=str(item.get("npc_id", "")),
                behavior=behavior,
                input_keywords=tuple(item.get("input_keywords", []) or []),
                requires_evidence_ids=tuple(item.get("requires_evidence_ids", []) or []),
                excludes_evidence_ids=tuple(item.get("excludes_evidence_ids", []) or []),
                raw_reply_json=item.get("raw_reply_json"),
            )
        )
    return MockScenarioSet(
        provider_id=provider_id,
        content_version=content_version,
        scenarios=tuple(scenarios),
    )


def load_scenario_set(path: Path) -> MockScenarioSet:
    return parse_scenario_set(json.loads(path.read_text(encoding="utf-8")))


class MockAiProvider:
    kind = "mock"
    is_synthetic = True
    available = True

    def __init__(self, scenarios: MockScenarioSet, provider_id: str | None = None) -> None:
        self._scenarios = scenarios
        self.provider_id = provider_id or scenarios.provider_id or DEFAULT_PROVIDER_ID

    async def generate(self, request: ProviderRequest) -> ProviderResult:
        started = time.perf_counter()
        latency = lambda: int((time.perf_counter() - started) * 1000)  # noqa: E731

        if request.content_version != self._scenarios.content_version:
            return ProviderResult(
                outcome=OUTCOME_MODEL_UNAVAILABLE,
                provider_kind="fallback",
                provider_id=self.provider_id,
                is_synthetic=True,
                failure_detail="content_version_mismatch",
                latency_ms=latency(),
            )

        scenario = self._scenarios.find(request)
        if scenario is None:
            return ProviderResult(
                outcome=OUTCOME_UNKNOWN_INTENT,
                provider_kind="fallback",
                provider_id=self.provider_id,
                is_synthetic=True,
                failure_detail="no_fixture_match",
                latency_ms=latency(),
            )

        if scenario.behavior == "timeout":
            return ProviderResult(
                outcome=OUTCOME_TIMEOUT,
                provider_kind="fallback",
                provider_id=self.provider_id,
                is_synthetic=True,
                failure_detail="simulated_timeout",
                latency_ms=latency(),
            )
        if scenario.behavior == "transport_error":
            return ProviderResult(
                outcome=OUTCOME_MODEL_UNAVAILABLE,
                provider_kind="fallback",
                provider_id=self.provider_id,
                is_synthetic=True,
                failure_detail="simulated_transport_error",
                latency_ms=latency(),
            )

        try:
            text, suggestion = validate_model_reply(
                scenario.raw_reply_json or "",
                npc_id=request.npc_id,
                available_topic_ids=set(request.available_topic_ids),
            )
        except ModelOutputRejected as exc:
            return ProviderResult(
                outcome=OUTCOME_UNSAFE_OUTPUT if exc.fallback_reason == "unsafe_output" else OUTCOME_INVALID_OUTPUT,
                provider_kind="fallback",
                provider_id=self.provider_id,
                is_synthetic=True,
                failure_detail=f"{scenario.scenario_id}:{exc.detail}",
                latency_ms=latency(),
            )

        return ProviderResult(
            outcome=OUTCOME_COMPLETED,
            provider_kind=self.kind,
            provider_id=self.provider_id,
            is_synthetic=True,
            text=text,
            suggested_topic_id=suggestion,
            latency_ms=latency(),
        )
