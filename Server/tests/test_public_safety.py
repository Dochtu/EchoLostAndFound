"""Public-deployment safety (M4-C C1.4).

The service is reachable without authentication once it is published, so:
bodies are size-capped even without ``Content-Length``, logs are redacted, and
no credential is ever echoed in a response, an error envelope, or the shipped
configuration template.
"""

from __future__ import annotations

import json
import logging

import httpx

from conftest import CONTENT_DIR, SERVER_ROOT, build_client, make_settings

from app.budget import RequestBudget
from app.content import load_content
from app.logging_utils import RedactingFilter, redact
from app.main import LOGGER, create_app
from app.middleware import BodySizeLimitMiddleware

CONTENT = load_content(CONTENT_DIR)
SECRET = "sk-live-0123456789abcdef"


# ------------------------------------------------------------------ body size


def test_declared_oversized_body_is_rejected_before_parsing(client):
    response = client.post(
        "/api/v1/sessions", content=b"{" + b"a" * 40000, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "REQUEST_TOO_LARGE"
    assert response.json()["error"]["details"]["limit_bytes"] == 32768


def test_middleware_rejects_chunked_body_without_content_length():
    """A chunked upload declares no length; the ASGI middleware must cap it."""

    calls = {"inner": 0}

    async def inner_app(scope, receive, send):  # pragma: no cover - must not run
        calls["inner"] += 1
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    chunk = b"x" * 4096
    chunks = [{"type": "http.request", "body": chunk, "more_body": True} for _ in range(4)]
    chunks.append({"type": "http.request", "body": chunk, "more_body": False})

    import asyncio

    sent: list[dict] = []

    async def receive():
        return chunks.pop(0)

    async def send(message):
        sent.append(message)

    async def run():
        middleware = BodySizeLimitMiddleware(inner_app, max_bytes=8192)
        await middleware(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/v1/sessions",
                "headers": [(b"x-request-id", b"chunk-0001"), (b"transfer-encoding", b"chunked")],
            },
            receive,
            send,
        )

    asyncio.run(run())
    assert calls["inner"] == 0, "oversized chunked body reached the application"
    assert sent[0]["status"] == 413
    payload = json.loads(sent[1]["body"])
    assert payload["error"]["code"] == "REQUEST_TOO_LARGE"
    assert payload["request_id"] == "chunk-0001"
    headers = dict(sent[0]["headers"])
    assert headers[b"x-request-id"] == b"chunk-0001"
    assert headers[b"cache-control"] == b"no-store"


def test_middleware_passes_small_bodies_through_unchanged():
    import asyncio

    seen: dict = {}

    async def inner_app(scope, receive, send):
        message = await receive()
        seen["body"] = message["body"]
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def run():
        middleware = BodySizeLimitMiddleware(inner_app, max_bytes=1024)

        async def receive():
            return {"type": "http.request", "body": b'{"npc_id":"npc_laozhou"}', "more_body": False}

        async def send(message):
            return None

        await middleware(
            {"type": "http", "method": "POST", "path": "/", "headers": []}, receive, send
        )

    asyncio.run(run())
    assert seen["body"] == b'{"npc_id":"npc_laozhou"}'


# -------------------------------------------------------------------- logging


def test_redact_masks_credentials():
    assert SECRET not in redact(f"token={SECRET}")
    assert "Bearer" in redact("Authorization: Bearer abcdef123456789")
    assert "abcdef123456789" not in redact("Authorization: Bearer abcdef123456789")
    assert SECRET not in redact(f"call failed api_key={SECRET} status=500")
    # Ordinary text stays readable.
    assert redact("provider=external-llm latency_ms=120") == "provider=external-llm latency_ms=120"


def test_log_filter_scrubs_records(caplog):
    logger = logging.getLogger("echolostfound.tests.redaction")
    logger.addFilter(RedactingFilter())
    with caplog.at_level(logging.INFO, logger="echolostfound.tests.redaction"):
        logger.info("upstream rejected key=%s", SECRET)
    assert SECRET not in caplog.text
    assert "[REDACTED]" in caplog.text


def test_server_logger_is_redacted_by_default(caplog):
    with caplog.at_level(logging.WARNING, logger="echolostfound.server"):
        LOGGER.warning("provider config %s", f"api_key={SECRET}")
    assert SECRET not in caplog.text


# --------------------------------------------------------------------- secrets


def test_llm_key_never_appears_in_health_or_meta(tmp_path):
    from fastapi.testclient import TestClient

    settings = make_settings(
        entry_mode="live",
        model_provider="llm",
        llm_base_url="https://llm.invalid/v1",
        llm_model="fake-model",
        llm_api_key=SECRET,
        llm_usage_path=tmp_path / "ledger.sqlite3",
        llm_ledger_epoch_path=tmp_path / "epoch" / "ledger-epoch.json",
    )
    settings.validate()
    RequestBudget.initialize(
        settings.llm_usage_path,
        settings.llm_ledger_epoch_path,
        limit=settings.llm_request_limit,
        per_session_limit=settings.llm_request_limit_per_session,
    )
    app = create_app(settings, content=CONTENT)
    with TestClient(app) as client:
        health = client.get("/api/v1/health")
        meta = client.get("/api/v1/meta")
    for response in (health, meta):
        assert response.status_code == 200
        assert SECRET not in response.text
    assert meta.json()["data"]["provider"]["available"] is True
    assert SECRET not in repr(settings)


def test_local_auth_token_never_echoed_on_rejection(content, scenarios):
    with build_client(content, scenarios, local_auth_token="local-secret-token") as client:
        response = client.get("/api/v1/meta")
    assert response.status_code == 401
    assert "local-secret-token" not in response.text


def test_env_example_contains_only_placeholders():
    text = (SERVER_ROOT / ".env.example").read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, _, value = stripped.partition("=")
        if name in {"LOCAL_AUTH_TOKEN", "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"}:
            assert value == "" or "replace" in value or "example.com" in value, name
        assert "sk-" not in value.lower()


def test_no_key_is_baked_into_the_content_bundle():
    for path in CONTENT_DIR.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert "sk-" not in text, path.name
        assert "api_key" not in text.lower(), path.name
