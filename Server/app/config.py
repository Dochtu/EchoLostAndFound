"""Runtime configuration for the EchoLostAndFound NPC AI service.

M5-C-A adds one explicit service entry mode:

  * ``APP_ENTRY_MODE=mock`` (default) -- the service is a deterministic mock.
    No external model client is ever constructed, so a misconfigured or even
    fully configured LLM endpoint cannot receive a request.
  * ``APP_ENTRY_MODE=live`` -- the real model path.  Startup is refused unless
    provider credentials, budget limits and a *usable* durable ledger are all
    present.  A live service that cannot prove its budget is not allowed to
    call a paid model.

All values come from environment variables.  No secret is ever written to
code, JSON content, logs, evidence files or responses.
"""

from __future__ import annotations

import ipaddress
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DEFAULT_CONTENT_DIR = APP_DIR / "content"
DEFAULT_STATE_DIR = APP_DIR.parent / ".local"
DEFAULT_USAGE_PATH = DEFAULT_STATE_DIR / "llm-usage.sqlite3"
DEFAULT_LEDGER_EPOCH_PATH = DEFAULT_STATE_DIR / "epoch" / "ledger-epoch.json"

VALID_ENTRY_MODES = frozenset({"mock", "live"})
_VALID_PROVIDERS = frozenset({"disabled", "mock", "llm"})

# Networks that would make every peer a "trusted proxy" and therefore make
# X-Forwarded-For spoofable again.  Refused at startup.
_UNRESTRICTED_NETWORKS = frozenset({"0.0.0.0/0", "::/0"})


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


def _env_list(name: str) -> tuple[str, ...]:
    raw = os.environ.get(name, "")
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def _env_path(name: str, default: Path) -> Path:
    raw = _env_str(name)
    return Path(raw).expanduser() if raw else default


@dataclass(frozen=True)
class Settings:
    """Immutable settings snapshot built once at application startup."""

    service_name: str = "echolostfound-npc-ai"
    api_version: str = "1.0"
    schema_version: int = 1
    content_dir: Path = DEFAULT_CONTENT_DIR
    # Unified deployment: when set, the same process serves the WebGL site and
    # /api/v1 (same origin, so CORS is irrelevant for the bundled build).
    web_root: str = ""
    entry_mode: str = "mock"
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
    # Per-client and per-endpoint limits.  The global limiter alone cannot stop
    # one address from consuming every slot.
    client_rate_limit_per_minute: int = 60
    client_rate_limit_burst: int = 30
    session_turn_rate_per_minute: int = 30
    session_turn_rate_burst: int = 10
    new_session_rate_per_minute: int = 20
    new_session_rate_burst: int = 5
    # Only a peer inside one of these networks may supply X-Forwarded-For.
    # Empty means "trust the socket peer", which is the safe default.
    trusted_proxy_cidrs: tuple[str, ...] = ()
    trust_forwarded_for: bool = False  # deprecated, kept for old compose files
    local_auth_token: str = field(default="", repr=False)
    # ModelScope Studios reserve `Authorization` and `X-modelscope-*` headers,
    # so the optional shared token uses its own header by default.
    local_auth_header: str = "X-Dialogue-Token"
    llm_base_url: str = ""
    llm_model: str = ""
    llm_api_key: str = field(default="", repr=False)
    llm_provider_id: str = "external-llm"
    # Hard per-request output cap and input-context cap (characters).
    llm_max_output_tokens: int = 220
    llm_input_max_chars: int = 800
    llm_max_concurrency: int = 2
    llm_json_mode: bool = False
    # Token budget (M5-C-A-R1).  ``LLM_CONTEXT_MAX_TOKENS`` caps the whole
    # prompt -- system prompt plus evidence context plus history -- not just the
    # player's text.  The category budgets below are enforced before the
    # upstream call and checked again after the payload is assembled.
    llm_context_max_tokens: int = 1536
    llm_system_prompt_max_tokens: int = 768
    llm_evidence_context_max_tokens: int = 320
    llm_history_max_tokens: int = 0  # history is intentionally not sent
    # Lifetime token quota and the conservative per-request reservation.
    # 0 means "reserve the worst case": context cap + output cap.
    llm_token_limit: int = 60000
    llm_token_reserve_per_request: int = 0
    # Externally pinned ledger generation (independent trusted config).
    llm_ledger_epoch_pin: str = ""
    # Upstreams that are explicitly known to be synthetic/test-only.  A success
    # from such an upstream never counts as "real model verified".
    llm_test_upstream: bool = False
    # Response header the provider uses to self-identify as a synthetic
    # upstream (set by tools/fake_llm_server.py and trusted test deployments).
    llm_test_upstream_header: str = "x-test-upstream"
    # Durable budget.  ``LLM_REQUEST_LIMIT`` counts *attempts*, including
    # failures; the per-session quota is strictly smaller so one session can
    # never exhaust the service.
    llm_request_limit: int = 30
    llm_request_limit_per_session: int = 8
    llm_usage_path: Path = DEFAULT_USAGE_PATH
    llm_ledger_epoch_path: Path = DEFAULT_LEDGER_EPOCH_PATH
    # Consecutive upstream failures before the breaker opens.
    llm_breaker_threshold: int = 5
    llm_breaker_cooldown_seconds: int = 60
    log_level: str = "INFO"

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_model and self.llm_api_key)

    @property
    def llm_token_reservation(self) -> int:
        """Conservative per-request token reservation used by the ledger."""

        if self.llm_token_reserve_per_request > 0:
            return int(self.llm_token_reserve_per_request)
        return int(self.llm_context_max_tokens) + int(self.llm_max_output_tokens)

    @property
    def model_available(self) -> bool:
        if self.entry_mode == "mock" or self.model_provider == "mock":
            return True
        if self.model_provider == "llm":
            return self.llm_configured
        return False

    def validate(self) -> None:
        if self.entry_mode not in VALID_ENTRY_MODES:
            raise ValueError(
                "APP_ENTRY_MODE must be one of mock, live "
                f"(received {self.entry_mode!r})"
            )
        if self.model_provider not in _VALID_PROVIDERS:
            raise ValueError(
                "MODEL_PROVIDER must be one of disabled, mock, llm "
                f"(received {self.model_provider!r})"
            )
        if self.entry_mode == "mock" and self.model_provider == "llm":
            raise ValueError(
                "MODEL_PROVIDER=llm requires APP_ENTRY_MODE=live; "
                "mock mode never calls an external model"
            )
        if self.entry_mode == "live" and self.model_provider != "llm":
            raise ValueError(
                "APP_ENTRY_MODE=live requires MODEL_PROVIDER=llm "
                f"(received {self.model_provider!r})"
            )
        if self.entry_mode == "live":
            if not self.llm_configured:
                raise ValueError(
                    "APP_ENTRY_MODE=live refused: LLM_BASE_URL, LLM_MODEL and "
                    "LLM_API_KEY are all required"
                )
            if not self.llm_base_url.startswith(("http://", "https://")):
                raise ValueError("LLM_BASE_URL must start with http:// or https://")
            if "@" in self.llm_base_url.split("://", 1)[1].split("/", 1)[0]:
                raise ValueError("LLM_BASE_URL must not contain credentials")
            if not self.llm_usage_path:
                raise ValueError("LLM_USAGE_PATH is required in live mode")
            if not self.llm_ledger_epoch_path:
                raise ValueError("LLM_LEDGER_EPOCH_PATH is required in live mode")
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
        if not (1 <= self.llm_request_limit <= 10000):
            raise ValueError("LLM_REQUEST_LIMIT must be between 1 and 10000")
        if not (1 <= self.llm_request_limit_per_session <= 10000):
            raise ValueError("LLM_REQUEST_LIMIT_PER_SESSION must be between 1 and 10000")
        if self.llm_request_limit_per_session >= self.llm_request_limit:
            raise ValueError(
                "LLM_REQUEST_LIMIT_PER_SESSION must be smaller than "
                "LLM_REQUEST_LIMIT (one session must not exhaust the service)"
            )
        if not (32 <= self.llm_max_output_tokens <= 1024):
            raise ValueError("LLM_MAX_OUTPUT_TOKENS must be between 32 and 1024")
        if not (100 <= self.llm_input_max_chars <= 4000):
            raise ValueError("LLM_INPUT_MAX_CHARS must be between 100 and 4000")
        if not (1 <= self.llm_max_concurrency <= 8):
            raise ValueError("LLM_MAX_CONCURRENCY must be between 1 and 8")
        if not (256 <= self.llm_context_max_tokens <= 8192):
            raise ValueError("LLM_CONTEXT_MAX_TOKENS must be between 256 and 8192")
        if not (128 <= self.llm_system_prompt_max_tokens <= self.llm_context_max_tokens):
            raise ValueError(
                "LLM_SYSTEM_PROMPT_MAX_TOKENS must be between 128 and "
                "LLM_CONTEXT_MAX_TOKENS"
            )
        if not (64 <= self.llm_evidence_context_max_tokens <= self.llm_context_max_tokens):
            raise ValueError(
                "LLM_EVIDENCE_CONTEXT_MAX_TOKENS must be between 64 and "
                "LLM_CONTEXT_MAX_TOKENS"
            )
        if not (0 <= self.llm_history_max_tokens <= self.llm_context_max_tokens):
            raise ValueError("LLM_HISTORY_MAX_TOKENS must be between 0 and the context cap")
        if not (1000 <= self.llm_token_limit <= 10_000_000):
            raise ValueError("LLM_TOKEN_LIMIT must be between 1000 and 10000000")
        if self.llm_token_reserve_per_request < 0:
            raise ValueError("LLM_TOKEN_RESERVE_PER_REQUEST must not be negative")
        if not (0 <= self.llm_token_reserve_per_request <= self.llm_token_limit):
            raise ValueError(
                "LLM_TOKEN_RESERVE_PER_REQUEST must not exceed LLM_TOKEN_LIMIT"
            )
        worst_case = self.llm_context_max_tokens + self.llm_max_output_tokens
        if 0 < self.llm_token_reserve_per_request < worst_case:
            raise ValueError(
                "LLM_TOKEN_RESERVE_PER_REQUEST must be at least the worst-case "
                "request cost (LLM_CONTEXT_MAX_TOKENS + LLM_MAX_OUTPUT_TOKENS)"
            )
        if self.llm_token_limit < worst_case:
            raise ValueError(
                "LLM_TOKEN_LIMIT must be at least one worst-case request "
                "(LLM_CONTEXT_MAX_TOKENS + LLM_MAX_OUTPUT_TOKENS)"
            )
        if self.llm_ledger_epoch_pin and not re.fullmatch(
            r"[0-9a-fA-F-]{8,128}", self.llm_ledger_epoch_pin
        ):
            raise ValueError("LLM_LEDGER_EPOCH_PIN must be a generation id")
        if not re.fullmatch(r"[A-Za-z0-9-]{3,64}", self.llm_test_upstream_header):
            raise ValueError("LLM_TEST_UPSTREAM_HEADER must be a simple header name")
        if not (1 <= self.llm_breaker_threshold <= 50):
            raise ValueError("LLM_BREAKER_THRESHOLD must be between 1 and 50")
        if not (1 <= self.llm_breaker_cooldown_seconds <= 3600):
            raise ValueError("LLM_BREAKER_COOLDOWN_SECONDS must be between 1 and 3600")
        for cidr in self.trusted_proxy_cidrs:
            try:
                network = ipaddress.ip_network(cidr, strict=False)
            except ValueError as exc:
                raise ValueError(f"TRUSTED_PROXY_CIDRS entry is not a network: {cidr!r}") from exc
            if network.prefixlen == 0 or str(network) in _UNRESTRICTED_NETWORKS:
                raise ValueError(
                    "TRUSTED_PROXY_CIDRS must not trust every address; "
                    f"refused {cidr!r}"
                )
        if self.entry_mode == "live" and self.trust_forwarded_for and not self.trusted_proxy_cidrs:
            raise ValueError(
                "TRUST_FORWARDED_FOR without TRUSTED_PROXY_CIDRS is refused: "
                "configure the verified proxy topology instead"
            )

    @classmethod
    def from_env(cls) -> "Settings":
        entry_mode = _env_str("APP_ENTRY_MODE", "mock").lower()
        default_provider = "llm" if entry_mode == "live" else "mock"
        settings = cls(
            service_name=_env_str("SERVICE_NAME", "echolostfound-npc-ai"),
            api_version=_env_str("API_VERSION", "1.0"),
            schema_version=_env_int("SCHEMA_VERSION", 1),
            content_dir=Path(_env_str("CONTENT_DIR", str(DEFAULT_CONTENT_DIR))).resolve(),
            web_root=_env_str("WEB_ROOT", "").strip(),
            entry_mode=entry_mode,
            model_provider=_env_str("MODEL_PROVIDER", default_provider).lower(),
            allowed_origins=_env_origins("CORS_ALLOWED_ORIGINS"),
            player_input_max_chars=_env_int("PLAYER_INPUT_MAX_CHARS", 1000),
            request_max_bytes=_env_int("REQUEST_MAX_BYTES", 32768, minimum=256),
            ai_timeout_ms=_env_int("AI_TIMEOUT_MS", 12000, minimum=100),
            session_ttl_seconds=_env_float("SESSION_TTL_SECONDS", 1800.0, minimum=1.0),
            max_sessions=_env_int("MAX_SESSIONS", 512),
            rate_limit_per_minute=_env_int("RATE_LIMIT_PER_MINUTE", 60),
            rate_limit_burst=_env_int("RATE_LIMIT_BURST", 20),
            client_rate_limit_per_minute=_env_int("CLIENT_RATE_LIMIT_PER_MINUTE", 60),
            client_rate_limit_burst=_env_int("CLIENT_RATE_LIMIT_BURST", 30),
            session_turn_rate_per_minute=_env_int("SESSION_TURN_RATE_PER_MINUTE", 30),
            session_turn_rate_burst=_env_int("SESSION_TURN_RATE_BURST", 10),
            new_session_rate_per_minute=_env_int("NEW_SESSION_RATE_PER_MINUTE", 20),
            new_session_rate_burst=_env_int("NEW_SESSION_RATE_BURST", 5),
            trusted_proxy_cidrs=_env_list("TRUSTED_PROXY_CIDRS"),
            trust_forwarded_for=_env_bool("TRUST_FORWARDED_FOR", False),
            local_auth_token=_env_str("LOCAL_AUTH_TOKEN", ""),
            local_auth_header=_env_str("LOCAL_AUTH_HEADER", "X-Dialogue-Token"),
            llm_base_url=_env_str("LLM_BASE_URL", "").rstrip("/"),
            llm_model=_env_str("LLM_MODEL", ""),
            llm_api_key=_env_str("LLM_API_KEY", ""),
            llm_provider_id=_env_str("LLM_PROVIDER_ID", "external-llm"),
            llm_max_output_tokens=_env_int("LLM_MAX_OUTPUT_TOKENS", 220),
            llm_input_max_chars=_env_int("LLM_INPUT_MAX_CHARS", 800),
            llm_max_concurrency=_env_int("LLM_MAX_CONCURRENCY", 2),
            llm_json_mode=_env_bool("LLM_JSON_MODE", False),
            llm_context_max_tokens=_env_int("LLM_CONTEXT_MAX_TOKENS", 1536),
            llm_system_prompt_max_tokens=_env_int(
                "LLM_SYSTEM_PROMPT_MAX_TOKENS", 768
            ),
            llm_evidence_context_max_tokens=_env_int(
                "LLM_EVIDENCE_CONTEXT_MAX_TOKENS", 320
            ),
            llm_history_max_tokens=_env_int("LLM_HISTORY_MAX_TOKENS", 0, minimum=0),
            llm_token_limit=_env_int("LLM_TOKEN_LIMIT", 60000),
            llm_token_reserve_per_request=_env_int(
                "LLM_TOKEN_RESERVE_PER_REQUEST", 0, minimum=0
            ),
            llm_ledger_epoch_pin=_env_str("LLM_LEDGER_EPOCH_PIN", ""),
            llm_test_upstream=_env_bool("LLM_TEST_UPSTREAM", False),
            llm_test_upstream_header=_env_str(
                "LLM_TEST_UPSTREAM_HEADER", "x-test-upstream"
            ),
            llm_request_limit=_env_int("LLM_REQUEST_LIMIT", 30),
            llm_request_limit_per_session=_env_int("LLM_REQUEST_LIMIT_PER_SESSION", 8),
            llm_usage_path=_env_path("LLM_USAGE_PATH", DEFAULT_USAGE_PATH),
            llm_ledger_epoch_path=_env_path(
                "LLM_LEDGER_EPOCH_PATH", DEFAULT_LEDGER_EPOCH_PATH
            ),
            llm_breaker_threshold=_env_int("LLM_BREAKER_THRESHOLD", 5),
            llm_breaker_cooldown_seconds=_env_int("LLM_BREAKER_COOLDOWN_SECONDS", 60),
            log_level=_env_str("LOG_LEVEL", "INFO").upper(),
        )
        settings.validate()
        return settings
