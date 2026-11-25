"""Truthful model-connection state.

Three things are deliberately kept apart, because conflating them is how a
project ends up claiming "real AI connected" without ever having called a
model:

* **configured** -- settings are present (base URL, model id, API key);
* **verified** -- a *real* upstream request actually succeeded;
* **available right now** -- not blocked by the breaker, the token/request
  budget or an unusable ledger.

A success from a synthetic/test upstream (the local fake LLM, a stub, a
recording, or a response marked by ``x-test-upstream``) sets
``verified_test_upstream`` but never ``verified_real``.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

MODE_MOCK = "mock"
MODE_LIVE = "live"

STATUS_MOCK = "mock"
STATUS_NOT_CONFIGURED = "not_configured"
STATUS_CONFIGURED_UNVERIFIED = "configured_unverified"
STATUS_CONNECTED = "connected"
STATUS_TEST_UPSTREAM_VERIFIED = "test_upstream_verified"
STATUS_UPSTREAM_ERROR = "upstream_error"
STATUS_BUDGET_EXHAUSTED = "budget_exhausted"
STATUS_CIRCUIT_OPEN = "circuit_open"
STATUS_BUDGET_UNAVAILABLE = "budget_unavailable"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class ModelState:
    """Per-process record of what actually happened with the upstream."""

    entry_mode: str = MODE_MOCK
    provider_kind: str = "mock"
    provider_id: str = "mock"
    configured: bool = False
    synthetic_by_config: bool = False
    successes: int = 0
    test_successes: int = 0
    failures: int = 0
    last_success_at: str | None = None
    last_success_synthetic: bool | None = None
    last_failure_at: str | None = None
    last_failure_detail: str | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # -- recording -----------------------------------------------------
    def record_success(self, *, synthetic: bool) -> None:
        with self._lock:
            self.successes += 1
            if synthetic:
                self.test_successes += 1
            self.last_success_at = _now()
            self.last_success_synthetic = synthetic

    def record_failure(self, detail: str) -> None:
        with self._lock:
            self.failures += 1
            self.last_failure_at = _now()
            self.last_failure_detail = detail

    # -- derived -------------------------------------------------------
    @property
    def verified_real(self) -> bool:
        with self._lock:
            return (
                self.successes - self.test_successes > 0
                and self.last_success_synthetic is False
            )

    @property
    def verified_test_upstream(self) -> bool:
        with self._lock:
            return self.test_successes > 0

    def status(
        self,
        *,
        budget_usage: dict | None = None,
        breaker: dict | None = None,
    ) -> str:
        """Current, honest status of the model connection."""

        if self.entry_mode != MODE_LIVE or self.provider_kind != "external_model":
            return STATUS_MOCK
        if not self.configured:
            return STATUS_NOT_CONFIGURED
        usage = budget_usage or {}
        usage_status = usage.get("status")
        if usage_status not in (None, "ready"):
            return STATUS_BUDGET_UNAVAILABLE
        if breaker and breaker.get("state") == "open":
            return STATUS_CIRCUIT_OPEN
        limit = usage.get("global_limit")
        used = usage.get("global_used")
        if isinstance(limit, int) and isinstance(used, int) and limit and used >= limit:
            return STATUS_BUDGET_EXHAUSTED
        token_limit = usage.get("token_limit")
        token_used = usage.get("tokens_used")
        if (
            isinstance(token_limit, int)
            and isinstance(token_used, int)
            and token_limit
            and token_used >= token_limit
        ):
            return STATUS_BUDGET_EXHAUSTED
        if self.verified_real:
            return STATUS_CONNECTED
        if self.verified_test_upstream:
            return STATUS_TEST_UPSTREAM_VERIFIED
        with self._lock:
            if self.failures and not self.successes:
                return STATUS_UPSTREAM_ERROR
        return STATUS_CONFIGURED_UNVERIFIED

    def snapshot(
        self,
        *,
        budget_usage: dict | None = None,
        breaker: dict | None = None,
    ) -> dict:
        with self._lock:
            successes = self.successes
            test_successes = self.test_successes
            failures = self.failures
            last_success_at = self.last_success_at
            last_success_synthetic = self.last_success_synthetic
            last_failure_at = self.last_failure_at
            last_failure_detail = self.last_failure_detail
        status = self.status(budget_usage=budget_usage, breaker=breaker)
        return {
            "status": status,
            "verified": status == STATUS_CONNECTED,
            "verified_test_upstream": test_successes > 0,
            "configured": self.configured,
            "entry_mode": self.entry_mode,
            "successes": successes,
            "test_successes": test_successes,
            "failures": failures,
            "last_success_at": last_success_at,
            "last_success_synthetic": last_success_synthetic,
            "last_failure_at": last_failure_at,
            "last_failure_detail": last_failure_detail,
        }
