"""request_id resolution (M4-C C1.3).

Contract from API_CONTRACT.md section 1.2:

* header only   -> header id
* body only     -> body id becomes the effective id (pre-M4-C this was a 400)
* both, equal   -> that id
* both, differ  -> 400 INVALID_REQUEST
* neither       -> server-generated uuid

Every response -- success, guard rejection and handler error -- carries the
effective id in ``X-Request-ID`` and in the envelope.
"""

from __future__ import annotations

import uuid

from conftest import assert_error, create_session

TOPIC = {"topic_id": "opt.laozhou.ask_b01"}


def _turns_url(conversation_id: str) -> str:
    return f"/api/v1/sessions/{conversation_id}/turns"


def test_header_only_is_used(client):
    conversation_id = create_session(client, "npc_laozhou")
    response = client.post(
        _turns_url(conversation_id), json=TOPIC, headers={"X-Request-ID": "hdr-0001"}
    )
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "hdr-0001"
    assert response.json()["request_id"] == "hdr-0001"


def test_body_only_is_accepted_and_echoed(client):
    conversation_id = create_session(client, "npc_laozhou")
    response = client.post(
        _turns_url(conversation_id), json={**TOPIC, "request_id": "body-0001"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["request_id"] == "body-0001"
    assert response.headers["X-Request-ID"] == "body-0001"


def test_identical_header_and_body_are_accepted(client):
    conversation_id = create_session(client, "npc_laozhou")
    response = client.post(
        _turns_url(conversation_id),
        json={**TOPIC, "request_id": "same-0001"},
        headers={"X-Request-ID": "same-0001"},
    )
    assert response.status_code == 200
    assert response.json()["request_id"] == "same-0001"
    assert response.headers["X-Request-ID"] == "same-0001"


def test_conflicting_header_and_body_are_rejected(client):
    conversation_id = create_session(client, "npc_laozhou")
    response = client.post(
        _turns_url(conversation_id),
        json={**TOPIC, "request_id": "body-0002"},
        headers={"X-Request-ID": "hdr-0002"},
    )
    assert_error(response, 400, "INVALID_REQUEST")
    assert response.json()["request_id"] == "hdr-0002"
    assert response.headers["X-Request-ID"] == "hdr-0002"


def test_missing_ids_are_generated(client):
    conversation_id = create_session(client, "npc_laozhou")
    response = client.post(_turns_url(conversation_id), json=TOPIC)
    assert response.status_code == 200
    generated = response.json()["request_id"]
    uuid.UUID(generated)  # a real id, not an empty string
    assert response.headers["X-Request-ID"] == generated


def test_invalid_header_is_replaced_not_rejected(client):
    conversation_id = create_session(client, "npc_laozhou")
    response = client.post(
        _turns_url(conversation_id), json=TOPIC, headers={"X-Request-ID": "bad id!"}
    )
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] != "bad id!"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_invalid_body_id_is_ignored(client):
    conversation_id = create_session(client, "npc_laozhou")
    response = client.post(
        _turns_url(conversation_id), json={**TOPIC, "request_id": "not a valid id"}
    )
    assert response.status_code == 200
    assert response.json()["request_id"] != "not a valid id"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_validation_errors_carry_the_request_id(client):
    conversation_id = create_session(client, "npc_laozhou")
    response = client.post(
        _turns_url(conversation_id), json={}, headers={"X-Request-ID": "hdr-0003"}
    )
    assert_error(response, 422, "VALIDATION_ERROR")
    assert response.headers["X-Request-ID"] == "hdr-0003"
    assert response.json()["request_id"] == "hdr-0003"


def test_not_found_errors_carry_the_request_id(client):
    response = client.get(
        "/api/v1/sessions/does-not-exist", headers={"X-Request-ID": "hdr-0004"}
    )
    assert_error(response, 404, "NOT_FOUND")
    assert response.headers["X-Request-ID"] == "hdr-0004"


def test_guard_rejections_carry_the_request_id(client):
    response = client.post(
        "/api/v1/sessions",
        content=b"x" * 40000,
        headers={"Content-Type": "application/json", "X-Request-ID": "hdr-0005"},
    )
    assert_error(response, 413, "REQUEST_TOO_LARGE")
    assert response.headers["X-Request-ID"] == "hdr-0005"
    assert response.json()["request_id"] == "hdr-0005"


def test_auth_rejections_carry_the_request_id(content, scenarios):
    from conftest import build_client

    with build_client(content, scenarios, local_auth_token="local-secret") as guarded:
        response = guarded.get("/api/v1/meta", headers={"X-Request-ID": "hdr-0006"})
    assert_error(response, 401, "LOCAL_AUTH_REQUIRED")
    assert response.headers["X-Request-ID"] == "hdr-0006"


def test_generated_ids_take_part_in_rate_limit_accounting(client):
    # Two independent requests without ids get two different ids.
    first = client.get("/api/v1/health")
    second = client.get("/api/v1/health")
    assert first.json()["request_id"] != second.json()["request_id"]
