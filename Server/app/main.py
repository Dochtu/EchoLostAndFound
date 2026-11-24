"""FastAPI application for the EchoLostAndFound NPC AI service.

The service is intentionally small:
  * deterministic fixed content (approved Chapter 01 lines) is served locally;
  * a model provider (mock or real LLM) can only add a short in-character
    bridge for free input;
  * failures become successful turn results with a `fallback_reason`, never a
    fake success or a leaked internal error;
  * all responses use the DataSchema-style envelope with an explicit
    `error: null` on success.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import Settings
from .content import ContentBundle, load_content
from .errors import (
    ApiError,
    ErrorCodes,
    invalid_request,
    not_found,
)
from .logging_utils import install_log_redaction
from .middleware import BodySizeLimitMiddleware
from .policy import DialoguePolicy
from .providers.base import NpcAiProvider
from .providers.factory import build_provider
from .rate_limit import SlidingWindowLimiter
from .schemas import CreateSessionRequest, PresentEvidenceRequest, TurnRequest
from .security import safe_request_id
from .sessions import SessionStore
from .static_site import install_static_site

LOGGER = logging.getLogger("echolostfound.server")
API_PREFIX = "/api/v1/"
HEALTH_PATH = "/api/v1/health"

install_log_redaction(LOGGER)


def _envelope(request_id: str | None, data: Any) -> dict[str, Any]:
    return {"request_id": request_id, "data": data, "error": None}


def _error_envelope(request_id: str | None, error: ApiError) -> dict[str, Any]:
    return {"request_id": request_id, "data": None, "error": error.payload()}


def create_app(
    settings: Settings | None = None,
    *,
    provider: NpcAiProvider | None = None,
    content: ContentBundle | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.validate()
    bundle = content or load_content(settings.content_dir)
    ai_provider = provider or build_provider(settings, settings.content_dir)
    policy = DialoguePolicy(bundle, settings, ai_provider)
    sessions = SessionStore(settings.session_ttl_seconds, max_sessions=settings.max_sessions)
    limiter = SlidingWindowLimiter(
        settings.rate_limit_per_minute, settings.rate_limit_burst
    )
    instance_id = str(uuid.uuid4())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        LOGGER.info(
            "npc-ai ready instance=%s provider=%s content_version=%s",
            instance_id,
            ai_provider.provider_id,
            bundle.content_version,
        )
        yield
        aclose = getattr(ai_provider, "aclose", None)
        if callable(aclose):
            await aclose()
            return
        close = getattr(ai_provider, "close", None)
        if callable(close):
            close()

    app = FastAPI(
        title="EchoLostAndFound NPC AI",
        version=settings.api_version,
        docs_url="/docs" if settings.model_provider != "llm" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.content = bundle
    app.state.policy = policy
    app.state.provider = ai_provider
    app.state.sessions = sessions
    app.state.limiter = limiter
    app.state.instance_id = instance_id

    # Registered before the request guard, so the guard (and CORS) wrap it:
    # rejected requests are never buffered, accepted ones are size-capped.
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.request_max_bytes)

    # ------------------------------------------------------------ guards

    @app.middleware("http")
    async def guard(request: Request, call_next):
        header_id = safe_request_id(request.headers.get("X-Request-ID"))
        request_id = header_id or str(uuid.uuid4())
        request.state.request_id = request_id
        # Tracked separately: a body-supplied id may legally become the
        # effective id when no header was sent (see _resolve_request_id).
        request.state.request_id_from_header = header_id is not None

        if settings.local_auth_token and request.url.path != HEALTH_PATH:
            provided = request.headers.get(settings.local_auth_header, "")
            if settings.local_auth_header.lower() == "authorization":
                expected = f"Bearer {settings.local_auth_token}"
                accepted = (
                    secrets.compare_digest(provided, expected)
                    or secrets.compare_digest(provided, settings.local_auth_token)
                )
            else:
                accepted = secrets.compare_digest(provided, settings.local_auth_token)
            if not accepted:
                return _json_error(
                    request_id,
                    ApiError(401, ErrorCodes.LOCAL_AUTH_REQUIRED, "缺少或无效的本机令牌。"),
                )

        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                return _json_error(
                    request_id,
                    invalid_request("Content-Length 无效。"),
                )
            if declared > settings.request_max_bytes:
                return _json_error(
                    request_id,
                    ApiError(
                        413,
                        ErrorCodes.REQUEST_TOO_LARGE,
                        "请求体超过大小上限。",
                        details={"limit_bytes": settings.request_max_bytes},
                    ),
                )

        # 只对业务 API 限流：WebGL 页面一次加载就要取十几份静态资源，
        # 若把静态请求也算进配额，刷新几轮就会把自己挡在门外（429 loader.js）。
        if request.url.path.startswith(API_PREFIX) and request.url.path != HEALTH_PATH:
            allowed, retry_after = limiter.check(_rate_key(request, settings))
            if not allowed:
                error = ApiError(
                    429,
                    ErrorCodes.RATE_LIMITED,
                    "请求过于频繁，请稍后再试。",
                    retryable=True,
                    details={"retry_after_seconds": round(retry_after, 2)},
                )
                return _json_error(request_id, error, extra_headers={"Retry-After": str(int(retry_after) + 1)})

        response = await call_next(request)
        # The turn route may adopt a body-supplied id when no header was sent;
        # always echo the id that ended up in the response envelope.
        effective_id = getattr(request.state, "request_id", None) or request_id
        response.headers["X-Request-ID"] = effective_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    # -------------------------------------------------------- error maps

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        return _json_error(_request_id(request), exc)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        details = {
            "errors": [
                {
                    "path": ".".join(str(part) for part in error.get("loc", ())),
                    "reason": str(error.get("type", "invalid")),
                }
                for error in exc.errors()
            ]
        }
        return _json_error(
            _request_id(request),
            ApiError(422, ErrorCodes.VALIDATION_ERROR, "请求参数不符合契约。", details=details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            error = not_found("资源不存在。")
        elif exc.status_code == 405:
            error = ApiError(405, ErrorCodes.INVALID_REQUEST, "方法不被允许。")
        else:
            error = ApiError(exc.status_code, ErrorCodes.INVALID_REQUEST, "请求失败。")
        return _json_error(_request_id(request), error)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):  # pragma: no cover - defensive
        LOGGER.exception("unhandled server error type=%s", type(exc).__name__)
        return _json_error(
            _request_id(request),
            ApiError(500, ErrorCodes.INTERNAL_ERROR, "服务器内部错误。", retryable=True),
        )

    # ------------------------------------------------------------- routes

    @app.get(HEALTH_PATH)
    async def health(request: Request):
        return _envelope(
            _request_id(request),
            {
                "service_instance_id": instance_id,
                "service_name": settings.service_name,
                "api_version": settings.api_version,
                "schema_version": settings.schema_version,
                "content_version": bundle.content_version,
                "ready": True,
                "model_available": bool(getattr(ai_provider, "available", False))
                and settings.model_provider == "llm",
                "model_mode": settings.model_provider,
                "provider": {
                    "kind": ai_provider.kind,
                    "id": ai_provider.provider_id,
                    "is_synthetic": ai_provider.is_synthetic,
                },
            },
        )

    @app.get("/api/v1/meta")
    async def meta(request: Request):
        dialogue = bundle.dialogue
        return _envelope(
            _request_id(request),
            {
                "content_version": bundle.content_version,
                "npcs": [
                    {
                        "npc_id": npc.npc_id,
                        "display_name": npc.display_name,
                        "allowed_evidence_ids": sorted(npc.allowed_evidence_ids),
                        "opening_segments": [s.to_payload() for s in npc.opening_segments],
                        "topics": [
                            {"topic_id": t.topic_id, "label": t.label} for t in npc.topics
                        ],
                    }
                    for npc in dialogue.npcs.values()
                ],
                "disclosures": [
                    {
                        "disclosure_id": d.disclosure_id,
                        "npc_id": d.npc_id,
                        "kind": d.kind,
                        "required_evidence_ids": sorted(d.required_evidence_ids),
                        "required_observed_field_ids": sorted(d.required_observed_field_ids),
                    }
                    for d in dialogue.disclosures
                ],
                "provisional_content_refs": list(dialogue.provisional_content_refs),
                "limits": {
                    "player_input_max_chars": settings.player_input_max_chars,
                    "request_max_bytes": settings.request_max_bytes,
                    "ai_timeout_ms": settings.ai_timeout_ms,
                    "session_ttl_seconds": settings.session_ttl_seconds,
                    "max_sessions": settings.max_sessions,
                },
                "provider": {
                    "kind": ai_provider.kind,
                    "id": ai_provider.provider_id,
                    "is_synthetic": ai_provider.is_synthetic,
                    "available": bool(getattr(ai_provider, "available", False)),
                },
            },
        )

    @app.post("/api/v1/sessions", status_code=201)
    async def create_session(request: Request, payload: CreateSessionRequest):
        request_id = _request_id(request)
        policy.validate_evidence_ids(payload.evidence_ids)
        policy.validate_field_ids(payload.observed_field_ids)
        profile = policy.npc(payload.npc_id)
        session = sessions.create(
            profile.npc_id,
            set(payload.evidence_ids),
            set(payload.observed_field_ids),
        )
        return _envelope(
            request_id,
            {
                "conversation_id": session.conversation_id,
                "npc_id": profile.npc_id,
                "status": session.status,
                "opening_segments": [s.to_payload() for s in policy.opening(profile)],
                "available_topic_ids": [
                    topic.topic_id for topic in policy.available_topics(profile, session)
                ],
                "expires_in_seconds": settings.session_ttl_seconds,
            },
        )

    @app.get("/api/v1/sessions/{conversation_id}")
    async def get_session(request: Request, conversation_id: str):
        session = sessions.get(conversation_id)
        profile = policy.npc(session.npc_id)
        return _envelope(
            _request_id(request),
            {
                "conversation_id": session.conversation_id,
                "npc_id": session.npc_id,
                "status": session.status,
                "presented_evidence_ids": sorted(session.presented_evidence_ids),
                "triggered_disclosure_ids": sorted(session.triggered_disclosure_ids),
                "available_topic_ids": [
                    topic.topic_id for topic in policy.available_topics(profile, session)
                ],
            },
        )

    @app.post("/api/v1/sessions/{conversation_id}/turns")
    async def take_turn(request: Request, conversation_id: str, payload: TurnRequest):
        request_id = _resolve_request_id(request, payload.request_id)
        session = sessions.get(conversation_id)
        profile = policy.npc(session.npc_id)
        turn = await policy.respond(
            profile,
            session,
            topic_id=payload.topic_id,
            text=payload.text,
            evidence_ids=payload.evidence_ids,
            observed_field_ids=payload.observed_field_ids,
            request_id=request_id,
            timeout_ms=payload.timeout_ms,
        )
        data = turn.to_payload()
        data["conversation_id"] = session.conversation_id
        data["npc_id"] = profile.npc_id
        return _envelope(request_id, data)

    @app.post("/api/v1/sessions/{conversation_id}/evidence")
    async def present_evidence(
        request: Request, conversation_id: str, payload: PresentEvidenceRequest
    ):
        request_id = _request_id(request)
        session = sessions.get(conversation_id)
        profile = policy.npc(session.npc_id)
        presentation = policy.present(
            profile,
            session,
            payload.evidence_ids,
            payload.observed_field_ids,
        )
        data = presentation.to_payload()
        data["conversation_id"] = session.conversation_id
        data["npc_id"] = profile.npc_id
        return _envelope(request_id, data)

    @app.post("/api/v1/sessions/{conversation_id}/cancel")
    async def cancel_session(request: Request, conversation_id: str):
        session = sessions.cancel(conversation_id)
        return _envelope(
            _request_id(request),
            {
                "conversation_id": session.conversation_id,
                "npc_id": session.npc_id,
                "status": "cancelled",
            },
        )

    # CORS is outermost so even guard rejections carry its headers.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID", "Authorization", settings.local_auth_header],
        expose_headers=["X-Request-ID", "Retry-After"],
        max_age=600,
    )
    if settings.web_root:
        # 统一部署（魔搭创空间）：同一进程既提供 /api/v1，也提供 WebGL 页面。
        # 未设置 WEB_ROOT 时不挂载，本地开发与测试行为不变。
        install_static_site(app, settings.web_root)
        LOGGER.info("webgl static site mounted root=%s", settings.web_root)
    return app


def _rate_key(request: Request, settings: Settings) -> str:
    if settings.trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip() or "unknown"
    client = request.client
    return client.host if client and client.host else "unknown"


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _resolve_request_id(request: Request, body_request_id: str | None) -> str:
    """Resolve the effective request id for a turn.

    Contract (API_CONTRACT.md section 1.2):

    * header only  -> the header id is used;
    * body only    -> the body id becomes the effective id and is echoed in
      both the envelope and ``X-Request-ID``;
    * both, equal  -> that id;
    * both, differ -> ``400 INVALID_REQUEST``;
    * neither      -> a server-generated uuid.

    A body id that is not a valid id is ignored (same rule as an invalid
    header), never a hard failure.
    """

    header_id = _request_id(request)
    from_header = bool(getattr(request.state, "request_id_from_header", False))
    candidate = safe_request_id(body_request_id)
    if candidate is None:
        return header_id or str(uuid.uuid4())
    if from_header and header_id:
        if header_id != candidate:
            raise invalid_request("请求头与请求体中的 request_id 不一致。")
        return header_id
    # No (valid) header: the body id wins and must be echoed consistently.
    request.state.request_id = candidate
    return candidate


def _json_error(
    request_id: str | None,
    error: ApiError,
    *,
    extra_headers: dict[str, str] | None = None,
) -> JSONResponse:
    headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
    if request_id:
        # Guard rejections and exception handlers bypass the http middleware,
        # so every error response carries the id itself.
        headers["X-Request-ID"] = request_id
    if extra_headers:
        headers.update(extra_headers)
    return JSONResponse(
        status_code=error.status_code,
        content=_error_envelope(request_id, error),
        headers=headers,
    )


# Uvicorn entry point: `uvicorn app.main:app`. Tests import create_app() instead
# so they can inject settings and a fake provider.
app = create_app()
