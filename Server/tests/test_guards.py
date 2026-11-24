"""Guard-rails: local auth, rate limit, body size cap, malformed JSON."""

from __future__ import annotations

from conftest import assert_error, build_client


def test_health_is_public_but_dialogue_requires_local_token(content, scenarios):
    with build_client(content, scenarios, local_auth_token="local-secret") as client:
        assert client.get("/api/v1/health").status_code == 200
        assert_error(client.get("/api/v1/meta"), 401, "LOCAL_AUTH_REQUIRED")
        allowed = client.get(
            "/api/v1/meta", headers={"X-Dialogue-Token": "local-secret"}
        )
        assert allowed.status_code == 200


def test_authorization_header_alone_is_not_the_token(content, scenarios):
    # ModelScope Studios consume Authorization; the token header is separate.
    with build_client(content, scenarios, local_auth_token="local-secret") as client:
        assert_error(
            client.get("/api/v1/meta", headers={"Authorization": "Bearer local-secret"}),
            401,
            "LOCAL_AUTH_REQUIRED",
        )


def test_wrong_token_is_rejected(content, scenarios):
    with build_client(content, scenarios, local_auth_token="local-secret") as client:
        assert_error(
            client.get("/api/v1/meta", headers={"X-Dialogue-Token": "wrong"}),
            401,
            "LOCAL_AUTH_REQUIRED",
        )


def test_rate_limit_returns_429_with_retry_after(content, scenarios):
    with build_client(
        content, scenarios, rate_limit_per_minute=2, rate_limit_burst=2
    ) as client:
        for _ in range(2):
            assert (
                client.post("/api/v1/sessions", json={"npc_id": "npc_laozhou"}).status_code
                == 201
            )
        limited = client.post("/api/v1/sessions", json={"npc_id": "npc_laozhou"})
    assert_error(limited, 429, "RATE_LIMITED")
    assert limited.headers["Retry-After"]
    assert limited.json()["error"]["retryable"] is True


def test_body_larger_than_limit_is_413(client):
    body = b'{"npc_id":"npc_laozhou","padding":"' + b"a" * 40000 + b'"}'
    response = client.post(
        "/api/v1/sessions", content=body, headers={"Content-Type": "application/json"}
    )
    assert_error(response, 413, "REQUEST_TOO_LARGE")


def test_malformed_json_is_422(client):
    response = client.post(
        "/api/v1/sessions",
        content=b'{"npc_id": ',
        headers={"Content-Type": "application/json"},
    )
    assert_error(response, 422, "VALIDATION_ERROR")
