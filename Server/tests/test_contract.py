"""Envelope, health, meta, CORS and request-id contract tests."""

from __future__ import annotations

from conftest import ALLOWED_ORIGIN, assert_error

from app.content import CONTENT_VERSION


def test_health_envelope_and_fields(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"request_id", "data", "error"}
    assert body["error"] is None
    assert body["data"]["ready"] is True
    assert body["data"]["content_version"] == CONTENT_VERSION
    assert body["data"]["schema_version"] == 1
    assert body["data"]["provider"]["kind"] == "mock"
    # A mock provider must never be reported as a real model.
    assert body["data"]["model_available"] is False
    assert body["data"]["model_mode"] == "mock"


def test_meta_exposes_only_approved_public_content(client):
    data = client.get("/api/v1/meta").json()["data"]
    assert data["content_version"] == CONTENT_VERSION
    npcs = {npc["npc_id"]: npc for npc in data["npcs"]}
    assert set(npcs) == {"npc_laozhou", "npc_linyao"}
    assert "npc_xucheng" not in npcs  # reserved for a later chapter
    laozhou_text = npcs["npc_laozhou"]["opening_segments"][0]["text"]
    assert laozhou_text.startswith("这封从旧库搬过两回。")
    assert data["provisional_content_refs"]
    assert "dialogue.CH01.opening.laozhou" in data["provisional_content_refs"]
    disclosure_ids = {entry["disclosure_id"] for entry in data["disclosures"]}
    assert {"D01", "D02", "D03", "REC.engraving"} <= disclosure_ids
    assert data["provider"]["is_synthetic"] is True
    assert data["limits"]["player_input_max_chars"] == 1000


def test_request_id_is_echoed_when_valid(client):
    response = client.get("/api/v1/health", headers={"X-Request-ID": "req-abc-123"})
    assert response.json()["request_id"] == "req-abc-123"
    assert response.headers["X-Request-ID"] == "req-abc-123"
    assert response.headers["Cache-Control"] == "no-store"


def test_invalid_request_id_is_replaced(client):
    response = client.get("/api/v1/health", headers={"X-Request-ID": "bad id with spaces!"})
    assert response.json()["request_id"] != "bad id with spaces!"


def test_unknown_body_field_is_rejected(client):
    response = client.post(
        "/api/v1/sessions", json={"npc_id": "npc_laozhou", "unexpected": True}
    )
    assert_error(response, 422, "VALIDATION_ERROR")
    paths = {error["path"] for error in response.json()["error"]["details"]["errors"]}
    assert any("unexpected" in path for path in paths)


def test_malformed_npc_id_is_rejected_before_route(client):
    assert_error(client.post("/api/v1/sessions", json={"npc_id": "laozhou"}), 422, "VALIDATION_ERROR")
    assert_error(client.post("/api/v1/sessions", json={"npc_id": "npc_X"}), 422, "VALIDATION_ERROR")


def test_unknown_npc_is_not_found(client):
    assert_error(client.post("/api/v1/sessions", json={"npc_id": "npc_xucheng"}), 404, "NOT_FOUND")


def test_unknown_route_uses_envelope(client):
    assert_error(client.get("/api/v1/does-not-exist"), 404, "NOT_FOUND")


def test_cors_allowed_origin(client):
    response = client.get("/api/v1/meta", headers={"Origin": ALLOWED_ORIGIN})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_cors_preflight_for_allowed_origin(client):
    response = client.options(
        "/api/v1/sessions",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_cors_does_not_allow_unknown_origin(client):
    response = client.get("/api/v1/meta", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers
