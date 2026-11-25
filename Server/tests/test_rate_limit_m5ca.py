"""Rate limiting: global, client, session-turn, new-session, trusted proxies."""

from __future__ import annotations

import pytest

from conftest import build_client, create_session, take_turn

from app.config import Settings
from app.network import resolve_client_ip
from app.rate_limit import SlidingWindowLimiter


def _client(content, scenarios, **overrides):
    defaults = dict(
        rate_limit_per_minute=1000,
        rate_limit_burst=1000,
        client_rate_limit_per_minute=1000,
        client_rate_limit_burst=1000,
        session_turn_rate_per_minute=1000,
        session_turn_rate_burst=1000,
        new_session_rate_per_minute=1000,
        new_session_rate_burst=1000,
    )
    defaults.update(overrides)
    return build_client(content, scenarios, **defaults)


def test_global_request_limit_returns_429_with_retry_after(content, scenarios):
    with _client(
        content,
        scenarios,
        rate_limit_per_minute=2,
        rate_limit_burst=2,
        client_rate_limit_per_minute=1000,
        client_rate_limit_burst=1000,
    ) as client:
        assert client.get("/api/v1/meta").status_code == 200
        assert client.get("/api/v1/meta").status_code == 200
        limited = client.get("/api/v1/meta")
    assert limited.status_code == 429
    body = limited.json()
    assert body["error"]["code"] == "RATE_LIMITED"
    assert int(limited.headers["Retry-After"]) >= 1
    assert body["error"]["details"]["retry_after_seconds"] >= 0


def test_health_is_exempt_from_rate_limiting(content, scenarios):
    with _client(
        content,
        scenarios,
        rate_limit_per_minute=1,
        rate_limit_burst=1,
        client_rate_limit_per_minute=1,
        client_rate_limit_burst=1,
    ) as client:
        assert client.get("/api/v1/meta").status_code == 200
        assert client.get("/api/v1/meta").status_code == 429
        for _ in range(5):
            assert client.get("/api/v1/health").status_code == 200


def test_client_limit_is_separate_from_global_limit(content, scenarios):
    with _client(
        content,
        scenarios,
        rate_limit_per_minute=1000,
        rate_limit_burst=1000,
        client_rate_limit_per_minute=1,
        client_rate_limit_burst=1,
    ) as client:
        assert client.get("/api/v1/meta").status_code == 200
        limited = client.get("/api/v1/meta")
    assert limited.status_code == 429


def test_new_session_creation_is_limited(content, scenarios):
    with _client(
        content,
        scenarios,
        new_session_rate_per_minute=1,
        new_session_rate_burst=1,
    ) as client:
        assert client.post(
            "/api/v1/sessions", json={"npc_id": "npc_laozhou"}
        ).status_code == 201
        limited = client.post("/api/v1/sessions", json={"npc_id": "npc_laozhou"})
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"


def test_session_turn_limit_is_per_session(content, scenarios):
    with _client(
        content,
        scenarios,
        session_turn_rate_per_minute=1,
        session_turn_rate_burst=1,
    ) as client:
        first = create_session(client, "npc_laozhou")
        second = create_session(client, "npc_laozhou")
        assert take_turn(client, first, text="灯还亮着吗")["status"] == "completed"
        limited = client.post(
            f"/api/v1/sessions/{first}/turns", json={"text": "灯还亮着吗"}
        )
        assert limited.status_code == 429
        # A different conversation is unaffected by another session's bucket.
        response = client.post(
            f"/api/v1/sessions/{second}/turns", json={"text": "灯还亮着吗"}
        )
        assert response.status_code == 200


def test_static_assets_are_not_model_rate_limited(content, scenarios, tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<html>ok</html>", encoding="utf-8")
    with _client(
        content,
        scenarios,
        web_root=site,
        rate_limit_per_minute=1,
        rate_limit_burst=1,
        client_rate_limit_per_minute=1,
        client_rate_limit_burst=1,
    ) as client:
        assert client.get("/api/v1/meta").status_code == 200
        assert client.get("/api/v1/meta").status_code == 429
        for _ in range(4):
            response = client.get("/")
            assert response.status_code == 200


# ------------------------------------------------------------ trusted proxies


def test_forwarded_for_is_ignored_from_an_untrusted_peer():
    assert (
        resolve_client_ip("203.0.113.9", "198.51.100.7", ("10.0.0.0/8",))
        == "203.0.113.9"
    )


def test_forwarded_for_is_used_only_through_a_trusted_proxy():
    assert (
        resolve_client_ip("10.1.2.3", "198.51.100.7", ("10.0.0.0/8",))
        == "198.51.100.7"
    )


def test_forwarded_chain_skips_trusted_hops_from_the_right():
    forwarded = "198.51.100.7, 10.1.2.3, 10.9.9.9"
    assert (
        resolve_client_ip("10.1.2.3", forwarded, ("10.0.0.0/8",))
        == "198.51.100.7"
    )


def test_invalid_forwarded_values_fail_to_unknown():
    assert resolve_client_ip("10.1.2.3", "not-an-ip", ("10.0.0.0/8",)) == "unknown"


def test_no_trusted_proxies_never_uses_forwarded_for():
    assert resolve_client_ip("192.0.2.5", "198.51.100.7", ()) == "192.0.2.5"


def test_settings_reject_forwarding_without_a_trusted_topology(tmp_path):
    with pytest.raises(ValueError):
        Settings(
            entry_mode="live",
            model_provider="llm",
            llm_base_url="https://llm.invalid/v1",
            llm_model="fake-model",
            llm_api_key="test-key-not-a-real-secret",
            allowed_origins=("http://localhost:8080",),
            llm_usage_path=tmp_path / "ledger.sqlite3",
            llm_ledger_epoch_path=tmp_path / "epoch.json",
            trust_forwarded_for=True,
            trusted_proxy_cidrs=(),
        ).validate()


def test_limiter_is_thread_safe_under_concurrent_checks():
    limiter = SlidingWindowLimiter(5, 5)
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda _: limiter.check("global")[0], range(20)))
    assert sum(results) == 5
