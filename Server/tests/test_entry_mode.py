"""APP_ENTRY_MODE contract: mock is the default and blocks paid calls."""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from conftest import CONTENT_DIR, create_session, take_turn

from app.budget import RequestBudget
from app.config import Settings
from app.content import load_content
from app.main import create_app
from app.providers.llm_provider import LlmProvider

SECRET = "test-key-not-a-real-secret"


def _clean_env(monkeypatch) -> None:
    for name in (
        "APP_ENTRY_MODE",
        "MODEL_PROVIDER",
        "LLM_BASE_URL",
        "LLM_API_KEY",
        "LLM_MODEL",
        "LLM_USAGE_PATH",
        "LLM_LEDGER_EPOCH_PATH",
        "TRUST_FORWARDED_FOR",
        "TRUSTED_PROXY_CIDRS",
    ):
        monkeypatch.delenv(name, raising=False)


def _live_settings(tmp_path, **overrides) -> Settings:
    values = dict(
        entry_mode="live",
        model_provider="llm",
        llm_base_url="https://llm.invalid/v1",
        llm_model="fake-model",
        llm_api_key=SECRET,
        allowed_origins=("http://localhost:8080",),
        llm_usage_path=tmp_path / "ledger.sqlite3",
        llm_ledger_epoch_path=tmp_path / "epoch" / "ledger-epoch.json",
    )
    values.update(overrides)
    settings = Settings(**values)
    settings.validate()
    return settings


def _make_ledger(settings: Settings) -> RequestBudget:
    return RequestBudget.initialize(
        settings.llm_usage_path,
        settings.llm_ledger_epoch_path,
        limit=settings.llm_request_limit,
        per_session_limit=settings.llm_request_limit_per_session,
    )


def test_default_entry_mode_is_mock_and_mock_is_the_default_provider(monkeypatch):
    _clean_env(monkeypatch)
    settings = Settings.from_env()
    assert settings.entry_mode == "mock"
    assert settings.model_provider == "mock"
    assert settings.validate is not None


def test_from_env_accepts_live_and_defaults_to_the_llm_provider(monkeypatch, tmp_path):
    _clean_env(monkeypatch)
    monkeypatch.setenv("APP_ENTRY_MODE", "live")
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.invalid/v1")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setenv("LLM_API_KEY", SECRET)
    monkeypatch.setenv("LLM_USAGE_PATH", str(tmp_path / "ledger.sqlite3"))
    monkeypatch.setenv("LLM_LEDGER_EPOCH_PATH", str(tmp_path / "epoch.json"))
    settings = Settings.from_env()
    assert settings.entry_mode == "live"
    assert settings.model_provider == "llm"
    assert SECRET not in repr(settings)


def test_invalid_entry_mode_is_refused(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv("APP_ENTRY_MODE", "automatic")
    with pytest.raises(ValueError, match="APP_ENTRY_MODE"):
        Settings.from_env()


def test_mock_mode_refuses_an_external_provider():
    settings = Settings(
        entry_mode="mock",
        model_provider="llm",
        llm_base_url="https://llm.invalid/v1",
        llm_model="fake-model",
        llm_api_key=SECRET,
        allowed_origins=("http://localhost:8080",),
    )
    with pytest.raises(ValueError, match="never calls an external model"):
        settings.validate()


@pytest.mark.parametrize(
    "overrides",
    [
        {"llm_api_key": ""},
        {"llm_base_url": ""},
        {"llm_model": ""},
        {"llm_base_url": "ftp://llm.invalid/v1"},
        {"llm_base_url": "https://user:pass@llm.invalid/v1"},
        {"llm_request_limit": 0},
        {"llm_request_limit_per_session": 30},
        {"llm_max_output_tokens": 4096},
        {"llm_max_concurrency": 0},
        {"trust_forwarded_for": True},
    ],
)
def test_live_mode_refuses_incomplete_or_unsafe_configuration(tmp_path, overrides):
    values = dict(
        entry_mode="live",
        model_provider="llm",
        llm_base_url="https://llm.invalid/v1",
        llm_model="fake-model",
        llm_api_key=SECRET,
        allowed_origins=("http://localhost:8080",),
        llm_usage_path=tmp_path / "ledger.sqlite3",
        llm_ledger_epoch_path=tmp_path / "epoch.json",
    )
    values.update(overrides)
    with pytest.raises(ValueError):
        Settings(**values).validate()


def test_trusted_proxy_cidr_rejects_wide_open_ranges(tmp_path):
    for cidr in ("0.0.0.0/0", "::/0"):
        with pytest.raises(ValueError):
            Settings(
                entry_mode="live",
                model_provider="llm",
                llm_base_url="https://llm.invalid/v1",
                llm_model="fake-model",
                llm_api_key=SECRET,
                allowed_origins=("http://localhost:8080",),
                llm_usage_path=tmp_path / "ledger.sqlite3",
                llm_ledger_epoch_path=tmp_path / "epoch.json",
                trust_forwarded_for=True,
                trusted_proxy_cidrs=(cidr,),
            ).validate()


def test_live_startup_is_refused_without_a_ledger(tmp_path):
    settings = _live_settings(tmp_path)
    with pytest.raises(RuntimeError, match="budget ledger unusable"):
        create_app(settings, content=load_content(CONTENT_DIR))


def test_live_startup_is_refused_when_ledger_epoch_was_lost(tmp_path):
    settings = _live_settings(tmp_path)
    _make_ledger(settings).close()
    (tmp_path / "epoch" / "ledger-epoch.json").unlink()
    with pytest.raises(RuntimeError, match="budget ledger unusable"):
        create_app(settings, content=load_content(CONTENT_DIR))


def test_live_startup_is_refused_when_ledger_was_deleted(tmp_path):
    settings = _live_settings(tmp_path)
    _make_ledger(settings).close()
    (tmp_path / "ledger.sqlite3").unlink()
    with pytest.raises(RuntimeError, match="budget ledger unusable"):
        create_app(settings, content=load_content(CONTENT_DIR))


def test_mock_startup_never_constructs_an_external_provider_and_reports_health():
    settings = Settings(
        content_dir=CONTENT_DIR,
        allowed_origins=("http://localhost:8080",),
    )
    settings.validate()
    app = create_app(settings, content=load_content(CONTENT_DIR))
    assert app.state.budget is None
    assert app.state.provider.kind == "mock"
    with TestClient(app) as client:
        health = client.get("/api/v1/health").json()["data"]
    assert health["entry_mode"] == "mock"
    assert health["model_mode"] == "mock"
    assert health["model_available"] is False
    assert health["model_ready"] is False
    assert health["is_synthetic"] is True
    assert health["game_ready"] is True
    assert health["provider"]["kind"] == "mock"
    assert health["provider"]["id"] == "mock-deterministic"
    assert health["ledger"]["status"] == "mock"
    assert health["ledger"]["persistent"] is False


def test_live_health_never_claims_the_model_is_ready_from_configuration_alone(tmp_path):
    """Configuration is not proof: no real upstream call has succeeded yet."""

    settings = _live_settings(tmp_path)
    _make_ledger(settings).close()
    app = create_app(settings, content=load_content(CONTENT_DIR))
    with TestClient(app) as client:
        health = client.get("/api/v1/health").json()["data"]
    assert health["entry_mode"] == "live"
    assert health["model_mode"] == "live"
    assert health["model_available"] is True
    # M5-C-A used to report model_ready == model_available, i.e. "configured
    # means connected".  R1 distinguishes them: readiness requires a verified
    # real-model request, which this test never makes.
    assert health["model_ready"] is False
    assert health["model_status"] == "configured_unverified"
    assert health["model"]["verified"] is False
    assert health["model"]["successes"] == 0
    assert health["game_ready"] is True
    assert health["is_synthetic"] is False
    assert health["provider"]["kind"] == "external_model"
    assert health["ledger"]["status"] == "ready"
    assert health["ledger"]["global_limit"] == 30
    assert health["ledger"]["session_limit"] == 8
    assert health["breaker"]["state"] == "closed"
    assert SECRET not in json.dumps(health)


def test_live_model_failure_still_serves_the_game_and_falls_back(tmp_path):
    settings = _live_settings(tmp_path)
    ledger = _make_ledger(settings)
    transport = httpx.MockTransport(lambda request: httpx.Response(500, text="boom"))
    provider = LlmProvider(settings, budget=ledger, transport=transport)
    app = create_app(settings, provider=provider, content=load_content(CONTENT_DIR), budget=ledger)
    with TestClient(app) as client:
        conversation_id = create_session(client, "npc_laozhou")
        turn = take_turn(client, conversation_id, text="那晚站台发生了什么")
        health = client.get("/api/v1/health").json()["data"]
    assert turn["status"] == "completed"
    assert turn["source"] == "fallback"
    assert turn["fallback_reason"] == "model_unavailable"
    assert health["game_ready"] is True
    # The failed call still consumed one paid-attempt slot.
    assert health["ledger"]["global_used"] == 1


def test_mock_mode_makes_zero_network_calls_even_for_free_text(monkeypatch):
    from app.providers import factory as factory_module

    def forbidden(*args, **kwargs):  # pragma: no cover - must not be called
        raise AssertionError("mock mode constructed an external provider")

    monkeypatch.setattr(factory_module, "LlmProvider", forbidden)
    settings = Settings(content_dir=CONTENT_DIR, allowed_origins=("http://localhost:8080",))
    app = create_app(settings, content=load_content(CONTENT_DIR))
    with TestClient(app) as client:
        conversation_id = create_session(client, "npc_laozhou")
        turn = take_turn(client, conversation_id, text="那晚站台发生了什么")
    assert turn["status"] == "completed"
    assert turn["provider"]["is_synthetic"] is True
    assert turn["provider"]["kind"] in {"mock", "fallback"}
