"""Runtime configuration for the EchoLostAndFound NPC AI service.

All values come from environment variables so the same image can run locally,
in CI, on a small VPS, or behind a ModelScope 创空间 proxy.  No secret is ever
written to code, JSON content, logs, or responses.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DEFAULT_CONTENT_DIR = APP_DIR / "content"

_VALID_PROVIDERS = frozenset({"disabled", "mock", "llm"})


def _env_str(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return default if value is None else value.strip()


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw.strip())
    except ValueError as exc:  # pragma: no cover - startup guard
        raise ValueError(f"environment variable {name} must be an integer") from exc
    if value < minimum:
        raise ValueError(f"environment variable {name} must be >= {minimum}")
    return value


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw.strip())
    except ValueError as exc:  # pragma: no cover - startup guard
        raise ValueError(f"environment variable {name} must be a number") from exc
    if value < minimum:
        raise ValueError(f"environment variable {name} must be >= {minimum}")
    return value


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_origins(name: str) -> tuple[str, ...]:
    raw = os.environ.get(name, "")
    return tuple(origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip())


@dataclass(frozen=True)
class Settings:
    """Immutable settings snapshot built once at application startup."""

    service_name: str = "echolostfound-npc-ai"
    api_version: str = "1.0"
    schema_version: int = 1
    content_dir: Path = DEFAULT_CONTENT_DIR
    # 统一部署：设置后同一进程同时提供 WebGL 页面与 /api/v1（同源，无需 CORS）。
    web_root: str = ""
    model_provider: str = "mock"
    allowed_origins: tuple[str, ...] = ()
    player_input_max_chars: int = 1000
    request_max_bytes: int = 32768
    ai_timeout_ms: int = 12000
    session_ttl_seconds: float = 1800.0
    # Hard cap on live conversations held in memory.  A public deployment has
    # no authentication, so the store must never grow without a bound.
    max_sessions: int = 512
    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 20
    trust_forwarded_for: bool = False
    local_auth_token: str = field(default="", repr=False)
    # ModelScope Studios reserve `Authorization` and `X-modelscope-*` headers,
    # so the optional shared token uses its own header by default.
    local_auth_header: str = "X-Dialogue-Token"
    llm_base_url: str = ""
    llm_model: str = ""
    llm_api_key: str = field(default="", repr=False)
    llm_provider_id: str = "external-llm"
    log_level: str = "INFO"

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_model and self.llm_api_key)

    @property
    def model_available(self) -> bool:
        if self.model_provider == "mock":
            return True
        if self.model_provider == "llm":
            return self.llm_configured
        return False

    def validate(self) -> None:
        if self.model_provider not in _VALID_PROVIDERS:
            raise ValueError(
                "MODEL_PROVIDER must be one of disabled, mock, llm "
                f"(received {self.model_provider!r})"
            )
        if self.model_provider == "llm" and not self.llm_configured:
            # Not fatal: the service still serves fixed lines and falls back
            # deterministically.  Health reports model_available=false.
            pass
        for origin in self.allowed_origins:
            if origin == "*":
                raise ValueError("CORS_ALLOWED_ORIGINS must list explicit origins, not '*'")
            if "://" not in origin:
                raise ValueError(f"CORS_ALLOWED_ORIGINS entry is not an origin: {origin!r}")
        if self.player_input_max_chars > 4000:
            raise ValueError("PLAYER_INPUT_MAX_CHARS above 4000 is not allowed")
        if not re.fullmatch(r"[A-Za-z0-9-]{3,64}", self.local_auth_header):
            raise ValueError("LOCAL_AUTH_HEADER must be a simple header name")
        if self.request_max_bytes > 1024 * 1024:
            raise ValueError("REQUEST_MAX_BYTES above 1 MiB is not allowed")
        if self.ai_timeout_ms < 100 or self.ai_timeout_ms > 60000:
            raise ValueError("AI_TIMEOUT_MS must be between 100 and 60000")
        if self.session_ttl_seconds <= 0:
            raise ValueError("SESSION_TTL_SECONDS must be positive")
        if self.max_sessions < 1 or self.max_sessions > 10000:
            raise ValueError("MAX_SESSIONS must be between 1 and 10000")

    @classmethod
    def from_env(cls) -> "Settings":
        settings = cls(
            service_name=_env_str("SERVICE_NAME", "echolostfound-npc-ai"),
            api_version=_env_str("API_VERSION", "1.0"),
            schema_version=_env_int("SCHEMA_VERSION", 1),
            content_dir=Path(_env_str("CONTENT_DIR", str(DEFAULT_CONTENT_DIR))).resolve(),
            web_root=_env_str("WEB_ROOT", "").strip(),
            model_provider=_env_str("MODEL_PROVIDER", "mock").lower(),
            allowed_origins=_env_origins("CORS_ALLOWED_ORIGINS"),
            player_input_max_chars=_env_int("PLAYER_INPUT_MAX_CHARS", 1000),
            request_max_bytes=_env_int("REQUEST_MAX_BYTES", 32768, minimum=256),
            ai_timeout_ms=_env_int("AI_TIMEOUT_MS", 12000, minimum=100),
            session_ttl_seconds=_env_float("SESSION_TTL_SECONDS", 1800.0, minimum=1.0),
            max_sessions=_env_int("MAX_SESSIONS", 512),
            rate_limit_per_minute=_env_int("RATE_LIMIT_PER_MINUTE", 60),
            rate_limit_burst=_env_int("RATE_LIMIT_BURST", 20),
            trust_forwarded_for=_env_bool("TRUST_FORWARDED_FOR", False),
            local_auth_token=_env_str("LOCAL_AUTH_TOKEN", ""),
            local_auth_header=_env_str("LOCAL_AUTH_HEADER", "X-Dialogue-Token"),
            llm_base_url=_env_str("LLM_BASE_URL", "").rstrip("/"),
            llm_model=_env_str("LLM_MODEL", ""),
            llm_api_key=_env_str("LLM_API_KEY", ""),
            llm_provider_id=_env_str("LLM_PROVIDER_ID", "external-llm"),
            log_level=_env_str("LOG_LEVEL", "INFO").upper(),
        )
        settings.validate()
        return settings
