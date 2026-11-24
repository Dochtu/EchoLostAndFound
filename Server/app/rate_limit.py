"""Small in-process limiter for public deployments.

A reverse proxy should also rate limit by IP; this guard makes the standalone
container safe by itself.  The key is always server-derived (client address or
explicitly trusted proxy header), never a client-supplied identity.
"""

from __future__ import annotations

import threading
import time


class SlidingWindowLimiter:
    def __init__(self, per_minute: int, burst: int, window_seconds: float = 60.0) -> None:
        self._per_minute = max(1, per_minute)
        self._limit = max(1, min(per_minute, burst))
        self._window = window_seconds
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, now: float | None = None) -> tuple[bool, float]:
        """Return (allowed, retry_after_seconds)."""

        timestamp = time.monotonic() if now is None else now
        cutoff = timestamp - self._window
        with self._lock:
            hits = [moment for moment in self._hits.get(key, []) if moment > cutoff]
            if len(hits) >= self._limit:
                retry_after = max(0.1, hits[0] + self._window - timestamp)
                self._hits[key] = hits
                return False, retry_after
            hits.append(timestamp)
            self._hits[key] = hits
            return True, 0.0
