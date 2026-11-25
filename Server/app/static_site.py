"""把 WebGL 构建产物与 ``/api/v1`` 放在同一个源下（魔搭创空间统一部署）。

只有设置 ``WEB_ROOT`` 时才挂载；本地开发、pytest 与既有部署完全不受影响。

设计要点：

- Unity WebGL 构建默认输出预压缩文件（``*.wasm.gz`` / ``*.data.gz`` /
  ``*.framework.js.gz``），因此优先返回 ``.gz`` 并在响应头声明
  ``Content-Encoding: gzip``，同时保留正确的基础 MIME 类型；
- 客户端不带 ``Accept-Encoding: gzip`` 时回退到未压缩文件（若存在），否则 406，
  绝不把 gzip 内容当明文返回；
- 路径不接受 ``..`` 与绝对路径，解析后必须仍位于 ``WEB_ROOT`` 内；
- 统一 ``Cache-Control: no-store``（构建文件名不带内容哈希，缓存收益有限，
  而错误缓存会长期卡住玩家）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from starlette.types import ASGIApp, Receive, Scope, Send

INDEX_FILE = "index.html"
CACHE_CONTROL = "no-store"

MIME_TYPES: dict[str, str] = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".wasm": "application/wasm",
    ".data": "application/octet-stream",
    ".bundle": "application/octet-stream",
    ".unityweb": "application/octet-stream",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".ttf": "font/ttf",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".txt": "text/plain; charset=utf-8",
}

# 只有这些扩展名允许返回 ``.gz`` 变体；防止把任意文件误标成 gzip。
GZIP_ELIGIBLE = {".js", ".mjs", ".wasm", ".data", ".bundle", ".unityweb", ".css", ".json", ".svg", ".txt", ".html"}


def _mime_type(path: Path) -> str:
    return MIME_TYPES.get(path.suffix.lower(), "application/octet-stream")


def _without_gz_suffix(path: Path) -> Path:
    """``game.data.gz`` → ``game.data``，用于在预压缩响应上给出基础 MIME。"""
    if path.suffix.lower() != ".gz":
        return path
    return path.with_name(path.name[: -len(".gz")])


def _accepts_gzip(scope: Scope) -> bool:
    for name, value in scope.get("headers", []):
        if name == b"accept-encoding":
            return b"gzip" in value.lower()
    return False


class StaticWebBuild:
    """最小静态服务器：只处理未命中 API 路由的 GET/HEAD 请求。"""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise ValueError(f"WEB_ROOT does not exist or is not a directory: {self.root}")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return
        method = scope.get("method", "GET").upper()
        if method not in {"GET", "HEAD"}:
            await self._plain(send, 405, "method_not_allowed")
            return
        target = self._resolve(scope.get("path", "/"))
        resolved = self._pick(target, _accepts_gzip(scope))
        if resolved is None:
            await self._plain(send, 404, "not_found")
            return
        file_path, gzip_encoded = resolved
        try:
            body = file_path.read_bytes()
        except OSError:
            await self._plain(send, 404, "not_found")
            return
        headers: list[tuple[bytes, bytes]] = [
            (b"content-type", _mime_type(_without_gz_suffix(target)).encode("latin-1")),
            (b"cache-control", CACHE_CONTROL.encode("latin-1")),
            (b"x-content-type-options", b"nosniff"),
            (b"content-length", str(len(body)).encode("latin-1")),
        ]
        if gzip_encoded:
            headers.append((b"content-encoding", b"gzip"))
            headers.append((b"vary", b"Accept-Encoding"))
        await send({"type": "http.response.start", "status": 200, "headers": headers})
        if method == "HEAD":
            await send({"type": "http.response.body", "body": b"", "more_body": False})
        else:
            await send({"type": "http.response.body", "body": body, "more_body": False})

    def _resolve(self, raw_path: str) -> Path:
        cleaned = raw_path.split("?", 1)[0].strip("/")
        if not cleaned:
            return self.root / INDEX_FILE
        candidate = (self.root / cleaned).resolve()
        if self.root not in candidate.parents and candidate != self.root:
            return self.root / "__forbidden__"
        return candidate

    def _pick(self, target: Path, accepts_gzip: bool) -> tuple[Path, bool] | None:
        if target.is_dir():
            target = target / INDEX_FILE
        # Unity WebGL 的 loader 在 decompressionFallback=false 时会直接索取
        # ``*.data.gz`` 这样的预压缩文件名，此时同样必须声明 Content-Encoding。
        if target.suffix.lower() == ".gz":
            if not accepts_gzip or not target.is_file():
                return None
            return target, True
        suffix = target.suffix.lower()
        if accepts_gzip and suffix in GZIP_ELIGIBLE:
            gz = target.with_name(target.name + ".gz")
            if gz.is_file():
                return gz, True
        if target.is_file():
            return target, False
        return None

    @staticmethod
    async def _plain(send: Send, status: int, code: str) -> None:
        body = ('{"error":{"code":"%s"}}' % code).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json; charset=utf-8"),
                    (b"cache-control", CACHE_CONTROL.encode("latin-1")),
                    (b"content-length", str(len(body)).encode("latin-1")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body, "more_body": False})


def install_static_site(app: ASGIApp, root: str | Path) -> StaticWebBuild:
    """把静态站点挂到 ``/``（必须在所有 API 路由之后调用）。"""
    site = StaticWebBuild(root)
    app.mount("/", site, name="webgl")  # type: ignore[attr-defined]
    return site


def iter_missing_files(root: str | Path, required: Iterable[str]) -> list[str]:
    """部署自检：返回缺失的必需文件列表。"""
    base = Path(root)
    return [name for name in required if not (base / name).is_file()]
