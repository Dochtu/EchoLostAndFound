"""Shared pytest fixtures for the NPC AI service."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.config import Settings
from app.content import ContentBundle, load_content
from app.main import create_app
from app.providers.mock_provider import MockAiProvider, MockScenarioSet, load_scenario_set

CONTENT_DIR = SERVER_ROOT / "app" / "content"
ALLOWED_ORIGIN = "http://localhost:8080"


def make_settings(**overrides) -> Settings:
    values = {
        "content_dir": CONTENT_DIR,
        "model_provider": "mock",
        "allowed_origins": (ALLOWED_ORIGIN,),
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture(scope="session")
def content() -> ContentBundle:
    return load_content(CONTENT_DIR)


@pytest.fixture(scope="session")
def scenarios() -> MockScenarioSet:
    return load_scenario_set(CONTENT_DIR / "mock_ai_fixtures.json")


def build_client(
    content: ContentBundle,
    scenarios: MockScenarioSet,
    *,
    provider=None,
    **settings_overrides,
) -> TestClient:
    ai_provider = provider if provider is not None else MockAiProvider(scenarios)
    app = create_app(
        make_settings(**settings_overrides),
        provider=ai_provider,
        content=content,
    )
    return TestClient(app)


@pytest.fixture
def client(content, scenarios):
    with build_client(content, scenarios) as test_client:
        yield test_client


# ----------------------------------------------------------------- helpers


def create_session(client: TestClient, npc_id: str, evidence=(), fields=()) -> str:
    response = client.post(
        "/api/v1/sessions",
        json={
            "npc_id": npc_id,
            "evidence_ids": list(evidence),
            "observed_field_ids": list(fields),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["conversation_id"]


def take_turn(client: TestClient, conversation_id: str, **body) -> dict:
    response = client.post(f"/api/v1/sessions/{conversation_id}/turns", json=body)
    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload["status"] == "completed"
    return payload


def present(client: TestClient, conversation_id: str, evidence_ids, fields=()) -> dict:
    response = client.post(
        f"/api/v1/sessions/{conversation_id}/evidence",
        json={"evidence_ids": list(evidence_ids), "observed_field_ids": list(fields)},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def assert_error(response, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    body = response.json()
    assert body["error"] is not None
    assert body["error"]["code"] == code
    assert body["data"] is None
    assert body["request_id"]


def fixed_texts(data: dict) -> list[str]:
    segments = data.get("fixed_segments", data.get("opening_segments", []))
    return [segment["text"] for segment in segments]
