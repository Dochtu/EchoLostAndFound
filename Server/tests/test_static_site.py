"""C5 预检：统一部署时 WebGL 静态资源与 /api/v1 同源提供。

这些测试用临时目录模拟 Unity WebGL 构建产物，验证：

- 预压缩文件按 ``Content-Encoding: gzip`` 返回，基础 MIME 正确；
- 客户端不接受 gzip 时不会把 gzip 内容当明文返回；
- 目录穿越被拒绝；
- 未设置 WEB_ROOT 时行为完全不变（仍只有 API）；
- 挂载静态站点后 API 仍然先行匹配。

ASGI 层面的断言直接调用 ``StaticWebBuild``，因为 ``TestClient``/httpx 会自动声明
``Accept-Encoding`` 并透明解压，无法观察原始响应头。
"""

from __future__ import annotations

import asyncio
import gzip
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.static_site import StaticWebBuild


def _build_site(root: Path) -> None:
    (root / "Build").mkdir(parents=True)
    (root / "index.html").write_text("<!doctype html><title>Echo</title>", encoding="utf-8")
    (root / "Build" / "game.loader.js").write_text("console.log('loader');", encoding="utf-8")
    (root / "Build" / "game.wasm.gz").write_bytes(gzip.compress(b"\0asm-fake", mtime=0))
    (root / "Build" / "game.data.gz").write_bytes(gzip.compress(b"data-block", mtime=0))


@pytest.fixture()
def site(tmp_path: Path) -> Path:
    _build_site(tmp_path)
    return tmp_path


def _client(web_root: Path) -> TestClient:
    return TestClient(create_app(settings=Settings(web_root=str(web_root))))


def _call(site: Path, path: str, *, accepts_gzip: bool = True, method: str = "GET") -> tuple[int, dict[str, str], bytes]:
    """直接以 ASGI scope 调用静态站点，观察未经 httpx 处理的原始响应。"""
    app = StaticWebBuild(site)
    messages: list[dict] = []
    headers = [(b"accept-encoding", b"gzip, deflate")] if accepts_gzip else []

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict) -> None:
        messages.append(message)

    asyncio.run(app({"type": "http", "method": method, "path": path, "headers": headers}, receive, send))
    start = messages[0]
    body = b"".join(message.get("body", b"") for message in messages[1:])
    return start["status"], {k.decode(): v.decode() for k, v in start["headers"]}, body


def test_index_is_served_at_root(site: Path) -> None:
    with _client(site) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.text.startswith("<!doctype html>")
    assert response.headers["cache-control"] == "no-store"


def test_precompressed_assets_keep_their_mime_type(site: Path) -> None:
    status, headers, body = _call(site, "/Build/game.wasm")
    assert status == 200
    assert headers["content-encoding"] == "gzip"
    assert headers["content-type"] == "application/wasm"
    assert headers["vary"] == "Accept-Encoding"
    assert gzip.decompress(body) == b"\0asm-fake"


def test_explicit_precompressed_name_is_still_declared_as_gzip(site: Path) -> None:
    # Unity WebGL 的 loader 会直接索取 *.data.gz / *.framework.js.gz。
    status, headers, body = _call(site, "/Build/game.data.gz")
    assert status == 200
    assert headers["content-encoding"] == "gzip"
    assert headers["content-type"] == "application/octet-stream"
    assert gzip.decompress(body) == b"data-block"


def test_explicit_precompressed_name_without_accept_gzip_is_refused(site: Path) -> None:
    status, headers, _body = _call(site, "/Build/game.data.gz", accepts_gzip=False)
    assert status == 404
    assert "content-encoding" not in headers


def test_plain_assets_are_served_unencoded(site: Path) -> None:
    status, headers, body = _call(site, "/Build/game.loader.js")
    assert status == 200
    assert "content-encoding" not in headers
    assert headers["content-type"].startswith("text/javascript")
    assert body == b"console.log('loader');"


def test_gzip_is_never_served_to_a_client_that_did_not_ask_for_it(site: Path) -> None:
    status, headers, body = _call(site, "/Build/game.wasm", accepts_gzip=False)
    assert status == 404
    assert "content-encoding" not in headers
    assert b"\x1f\x8b" not in body


def test_directory_traversal_is_rejected(site: Path) -> None:
    (site.parent / "secret.txt").write_text("top secret", encoding="utf-8")
    status, _headers, body = _call(site, "/../../secret.txt")
    assert status == 404
    assert b"top secret" not in body


def test_api_routes_win_over_the_static_mount(site: Path) -> None:
    with _client(site) as client:
        health = client.get("/api/v1/health")
        missing = client.get("/no-such-page")
    assert health.status_code == 200
    assert health.json()["data"]["ready"] is True
    assert missing.status_code == 404


def test_static_assets_are_not_rate_limited(site: Path) -> None:
    """WebGL 页面一次加载就要十几份静态资源，静态请求不能吃业务 API 的限流配额。"""
    settings = Settings(web_root=str(site), rate_limit_per_minute=1, rate_limit_burst=1)
    with TestClient(create_app(settings=settings)) as client:
        for _ in range(6):
            assert client.get("/Build/game.loader.js").status_code == 200
        assert client.get("/api/v1/meta").status_code == 200
        assert client.get("/api/v1/meta").status_code == 429


def test_without_web_root_the_api_only_behaviour_is_unchanged() -> None:
    with TestClient(create_app(settings=Settings())) as client:
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/").status_code == 404


def test_a_missing_web_root_fails_fast(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        create_app(settings=Settings(web_root=str(tmp_path / "does-not-exist")))
