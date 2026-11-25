"""Shared helpers for the M5-C-A-R1 live-path tests.

Everything here uses ``httpx.MockTransport`` -- no real network, no real
credential.  ``FAKE_KEY`` is deliberately recognisable as a test value.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from conftest import CONTENT_DIR

from app.budget import RequestBudget
from app.config import Settings
from app.content import load_content
from app.main import create_app
from app.providers.llm_provider import LlmProvider

FAKE_KEY = "test-key-not-a-real-secret"
NPC = "npc_laozhou"


def llm_settings(tmp_path: Path, **overrides) -> Settings:
    """Live-mode settings pointing at an unreachable fake upstream."""

    values = dict(
        entry_mode="live",
        model_provider="llm",
        llm_base_url="https://llm.invalid/v1",
        llm_model="fake-model",
        llm_api_key=FAKE_KEY,
        allowed_origins=("http://localhost:8080",),
        llm_usage_path=tmp_path / "ledger.sqlite3",
        llm_ledger_epoch_path=tmp_path / "epoch" / "ledger-epoch.json",
        llm_request_limit=50,
        llm_request_limit_per_session=20,
        llm_token_limit=200_000,
    )
    values.update(overrides)
    settings = Settings(**values)
    settings.validate()
    return settings


def init_budget(settings: Settings) -> RequestBudget:
    return RequestBudget.initialize(
        settings.llm_usage_path,
        settings.llm_ledger_epoch_path,
        limit=settings.llm_request_limit,
        per_session_limit=settings.llm_request_limit_per_session,
        token_limit=settings.llm_token_limit,
    )


def chat_body(
    text: str,
    *,
    npc_id: str = NPC,
    usage: dict | None = None,
    finish_reason: str = "stop",
    suggested_topic_id: str | None = None,
) -> dict:
    """A minimal OpenAI-compatible chat completion body."""

    payload = {
        "npc_id": npc_id,
        "text": text,
    }
    if suggested_topic_id is not None:
        payload["suggested_topic_id"] = suggested_topic_id
    body: dict = {
        "choices": [
            {
                "message": {"role": "assistant", "content": json.dumps(payload, ensure_ascii=False)},
                "finish_reason": finish_reason,
            }
        ]
    }
    if usage is not None:
        body["usage"] = usage
    return body


def make_llm_app(tmp_path: Path, handler, *, settings: Settings | None = None):
    """Build a TestClient whose LlmProvider uses ``handler``.

    Returns ``(client, calls)`` where ``calls`` collects every request body the
    adapter sent upstream (so tests can inspect the real prompt).
    """

    resolved = settings or llm_settings(tmp_path)
    budget = init_budget(resolved)
    calls: list[dict] = []

    def recording_handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content.decode("utf-8")))
        return handler(request)

    provider = LlmProvider(
        resolved,
        budget=budget,
        transport=httpx.MockTransport(recording_handler),
    )
    content = load_content(CONTENT_DIR)
    app = create_app(resolved, provider=provider, content=content)
    client = TestClient(app)
    client.__enter__()
    client.calls = calls  # type: ignore[attr-defined]
    client.budget = budget  # type: ignore[attr-defined]
    client.provider = provider  # type: ignore[attr-defined]
    client.settings = resolved  # type: ignore[attr-defined]
    return client, calls


def reply_handler(text: str, **kwargs):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=chat_body(text, **kwargs))

    return handler


def prompt_of(call: dict) -> str:
    return call["messages"][0]["content"]
