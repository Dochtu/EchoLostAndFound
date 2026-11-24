"""Request-body size enforcement for a publicly reachable service.

``Content-Length`` alone is not a limit: a chunked upload (or an HTTP/1.0
request without the header) bypasses it completely.  This pure-ASGI middleware
buffers the body up to ``max_bytes`` and rejects anything larger with the same
envelope shape the rest of the API uses, so a public deployment cannot be
driven into unbounded memory use by undeclared bodies.

It is registered *inside* the request guard: authentication, rate limiting and
the cheap ``Content-Length`` check run first, and only accepted requests get
their bodies buffered.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .errors import ErrorCodes
from .security import safe_request_id

_STATUS = 413
_CODE = ErrorCodes.REQUEST_TOO_LARGE
_MESSAGE = "请求体超过大小上限。"


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max(1, int(max_bytes))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        declared = _declared_length(scope)
        if declared is not None and declared > self.max_bytes:
            await _reject(scope, send, self.max_bytes)
            return

        buffered = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            buffered.extend(message.get("body", b""))
            if len(buffered) > self.max_bytes:
                await _reject(scope, send, self.max_bytes)
                return
            if not message.get("more_body", False):
                break

        body = bytes(buffered)
        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        await self.app(scope, replay, send)


def _declared_length(scope: Scope) -> int | None:
    for raw_name, raw_value in scope.get("headers", []):
        if raw_name.lower() == b"content-length":
            try:
                return int(raw_value.decode("latin-1").strip())
            except (UnicodeDecodeError, ValueError):
                return None
    return None


def _incoming_request_id(scope: Scope) -> str:
    for raw_name, raw_value in scope.get("headers", []):
        if raw_name.lower() == b"x-request-id":
            try:
                candidate = safe_request_id(raw_value.decode("latin-1"))
            except UnicodeDecodeError:
                candidate = None
            if candidate:
                return candidate
            break
    return str(uuid.uuid4())


async def _reject(scope: Scope, send: Send, limit: int) -> None:
    request_id = _incoming_request_id(scope)
    body: dict[str, Any] = {
        "request_id": request_id,
        "data": None,
        "error": {
            "code": _CODE,
            "message": _MESSAGE,
            "retryable": False,
            "details": {"limit_bytes": limit},
        },
    }
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = [
        (b"content-type", b"application/json; charset=utf-8"),
        (b"content-length", str(len(payload)).encode("ascii")),
        (b"cache-control", b"no-store"),
        (b"x-content-type-options", b"nosniff"),
        (b"x-request-id", request_id.encode("ascii")),
    ]
    await send({"type": "http.response.start", "status": _STATUS, "headers": headers})
    await send({"type": "http.response.body", "body": payload, "more_body": False})
