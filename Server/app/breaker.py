"""Consecutive-error circuit breaker for the upstream model.

A failing paid endpoint must stop being called: every retry costs money and
adds latency.  After ``threshold`` consecutive failures the breaker opens for
``cooldown_seconds``; while open the provider fails fast with
``circuit_open`` and *no* budget slot is reserved.  One half-open trial is
allowed after the cooldown; success closes the breaker, failure re-opens it.
"""

from __future__ import annotations

import threading
import time

STATE_CLOSED = "closed"
STATE_OPEN = "open"
STATE_HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        threshold: int,
        cooldown_seconds: float,
        *,
        clock=time.monotonic,
    ) -> None:
        self._threshold = max(1, int(threshold))
        self._cooldown = max(0.1, float(cooldown_seconds))
        self._clock = clock
        self._lock = threading.Lock()
        self._failures = 0
        self._opened_at: float | None = None
        self._state = STATE_CLOSED
        self._trial_in_flight = False

    def allow(self) -> bool:
        """Return True when a call may be attempted right now."""

        with self._lock:
            now = self._clock()
            if self._state == STATE_CLOSED:
                return True
            if self._state == STATE_OPEN:
                if self._opened_at is not None and now - self._opened_at >= self._cooldown:
                    self._state = STATE_HALF_OPEN
                    self._trial_in_flight = True
                    return True
                return False
            # half-open: exactly one trial at a time
            if self._trial_in_flight:
                return False
            self._trial_in_flight = True
            return True

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._state = STATE_CLOSED
            self._opened_at = None
            self._trial_in_flight = False

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            self._trial_in_flight = False
            if self._state == STATE_HALF_OPEN or self._failures >= self._threshold:
                self._state = STATE_OPEN
                self._opened_at = self._clock()

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "state": self._state,
                "consecutive_failures": self._failures,
                "threshold": self._threshold,
            }
