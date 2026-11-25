"""M5-C-A-R1 section 6: one owner for the client address, bounded limiter memory.

The application is the only layer allowed to decide who the client is.  These
tests prove that (a) Uvicorn's own proxy-header rewriting is off, (b) a forged
``X-Forwarded-For`` cannot buy a fresh rate-limit bucket, and (c) the limiter's
memory is bounded.
"""

from __future__ import annotations

import threading
import time

import httpx
import pytest
import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from conftest import ALLOWED_ORIGIN, assert_error, build_client, create_session

from app.network import resolve_client_ip
from app.rate_limit import SlidingWindowLimiter
from app.server_entry import build_config


# --------------------------------------------------------- address resolution


def test_header_is_ignored_without_trusted_proxies():
    assert resolve_client_ip("203.0.113.9", "198.51.100.7", ()) == "203.0.113.9"


def test_header_is_ignored_when_the_peer_is_not_a_trusted_proxy():
    cidrs = ("10.0.0.0/8",)
    assert resolve_client_ip("203.0.113.9", "198.51.100.7", cidrs) == "203.0.113.9"


def test_rightmost_untrusted_hop_wins_behind_a_trusted_proxy():
    cidrs = ("10.0.0.0/8",)
    chain = "203.0.113.9, 198.51.100.7, 10.1.2.3"
    assert resolve_client_ip("10.1.2.3", chain, cidrs) == "198.51.100.7"


def test_garbage_hop_never_becomes_a_bucket_key():
    cidrs = ("10.0.0.0/8",)
    assert resolve_client_ip("10.1.2.3", "not-an-ip, 10.1.2.3", cidrs) == "unknown"
    assert resolve_client_ip("not-an-ip", None, cidrs) == "unknown"


def test_all_trusted_hops_fall_back_to_the_peer():
    cidrs = ("10.0.0.0/8",)
    assert resolve_client_ip("10.1.2.3", "10.4.5.6", cidrs) == "10.1.2.3"


# ------------------------------------------------------------ uvicorn contract


def test_server_entry_disables_proxy_header_rewriting(monkeypatch):
    monkeypatch.setenv("PORT", "8123")
    config = build_config()

    assert config.proxy_headers is False, "Uvicorn must not rewrite request.client"
    assert config.forwarded_allow_ips == ""
    assert config.host == "0.0.0.0"
    assert config.port == 8123
    assert config.workers == 1


def _ip_app() -> Starlette:
    async def ip_endpoint(request):
        return JSONResponse(
            {
                "peer": request.client.host if request.client else None,
                "forwarded_for": request.headers.get("x-forwarded-for"),
            }
        )

    return Starlette(routes=[Route("/ip", ip_endpoint)])


def _serve(application, *, proxy_headers: bool):
    config = uvicorn.Config(
        application,
        host="127.0.0.1",
        port=0,
        proxy_headers=proxy_headers,
        forwarded_allow_ips="127.0.0.1",
        log_level="error",
        server_header=False,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started:
        if time.time() > deadline:  # pragma: no cover - environment failure
            raise AssertionError("uvicorn did not start")
        time.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    return server, thread, port


@pytest.mark.parametrize("proxy_headers", [False, True])
def test_real_http_request_shows_who_owns_the_address(proxy_headers):
    server, thread, port = _serve(_ip_app(), proxy_headers=proxy_headers)
    try:
        response = httpx.get(
            f"http://127.0.0.1:{port}/ip",
            headers={"X-Forwarded-For": "203.0.113.9"},
            timeout=10.0,
            trust_env=False,
        )
    finally:
        server.should_exit = True
        thread.join(timeout=10)

    body = response.json()
    if proxy_headers:
        # Why we disabled it: Uvicorn would let the header rewrite the peer, so
        # every request could pick its own rate-limit bucket.
        assert body["peer"] == "203.0.113.9"
    else:
        assert body["peer"] == "127.0.0.1"
        assert body["forwarded_for"] == "203.0.113.9"


# ------------------------------------------------ application-level enforcement


def test_forged_header_cannot_buy_a_new_bucket(content, scenarios):
    client = build_client(
        content,
        scenarios,
        client_rate_limit_per_minute=1,
        client_rate_limit_burst=1,
        rate_limit_per_minute=100,
        rate_limit_burst=100,
    )
    headers_a = {"X-Forwarded-For": "203.0.113.1"}
    headers_b = {"X-Forwarded-For": "203.0.113.2"}

    first = client.get("/api/v1/meta", headers=headers_a)
    assert first.status_code == 200
    second = client.get("/api/v1/meta", headers=headers_b)

    assert_error(second, 429, "RATE_LIMITED")
    assert second.headers["Retry-After"].isdigit()


def test_new_sessions_cannot_bypass_the_client_budget(content, scenarios):
    client = build_client(
        content,
        scenarios,
        new_session_rate_per_minute=2,
        new_session_rate_burst=2,
    )
    assert client.post("/api/v1/sessions", json={"npc_id": "npc_laozhou"}).status_code == 201
    assert client.post("/api/v1/sessions", json={"npc_id": "npc_laozhou"}).status_code == 201
    third = client.post("/api/v1/sessions", json={"npc_id": "npc_laozhou"})

    assert_error(third, 429, "RATE_LIMITED")
    fourth = client.post(
        "/api/v1/sessions",
        json={"npc_id": "npc_laozhou"},
        headers={"Origin": ALLOWED_ORIGIN, "X-Forwarded-For": "198.51.100.4"},
    )
    assert_error(fourth, 429, "RATE_LIMITED")


def test_many_sessions_share_one_client_bucket(content, scenarios):
    client = build_client(
        content,
        scenarios,
        client_rate_limit_per_minute=3,
        client_rate_limit_burst=3,
        new_session_rate_per_minute=100,
        new_session_rate_burst=100,
    )
    for _ in range(3):
        create_session(client, "npc_laozhou")
    blocked = client.post("/api/v1/sessions", json={"npc_id": "npc_laozhou"})
    assert_error(blocked, 429, "RATE_LIMITED")


# --------------------------------------------------------- limiter memory bound


def test_limiter_memory_is_bounded():
    # The table has a defensive floor of 16 buckets, so ask for exactly 16.
    limiter = SlidingWindowLimiter(per_minute=60, burst=60, max_keys=16)
    for index in range(200):
        limiter.check(f"client:10.0.0.{index}", now=1000.0)

    assert limiter.tracked_keys() <= 16


def test_limiter_prunes_stale_buckets_after_the_window():
    limiter = SlidingWindowLimiter(per_minute=60, burst=60, max_keys=1024)
    limiter.check("client:old", now=1000.0)
    assert limiter.tracked_keys() == 1

    # A later call prunes everything older than the window.
    for index in range(300):
        limiter.check(f"client:new-{index}", now=2000.0)

    assert limiter.tracked_keys() == 300, "the stale bucket must be gone"
    assert limiter.tracked_keys() <= 1024


def test_limiter_still_refuses_within_the_window():
    limiter = SlidingWindowLimiter(per_minute=2, burst=2, window_seconds=60.0)
    assert limiter.check("k", now=1000.0)[0] is True
    assert limiter.check("k", now=1000.5)[0] is True
    allowed, retry_after = limiter.check("k", now=1001.0)
    assert allowed is False
    assert 0 < retry_after <= 60
    assert limiter.check("k", now=1061.0)[0] is True
