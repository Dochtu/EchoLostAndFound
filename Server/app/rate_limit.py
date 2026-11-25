"""Small in-process limiter for public deployments.

A reverse proxy should also rate limit by IP; this guard makes the standalone
container safe by itself.  The key is always server-derived (client address or
explicitly trusted proxy header), never a client-supplied identity.

Memory is bounded twice: buckets are ordered by last activity, expired buckets
are dropped, and the table never exceeds ``max_keys`` entries.  An unbounded
dict would let an attacker consuming one address per request grow the process
until it is killed.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict

_PRUNE_INTERVAL = 256


class SlidingWindowLimiter:
    def __init__(
        self,
        per_minute: int,
        burst: int,
        window_seconds: float = 60.0,
        max_keys: int = 2048,
    ) -> None:
        self._per_minute = max(1, per_minute)
        self._limit = max(1, min(per_minute, burst))
        self._window = window_seconds
        self._max_keys = max(16, max_keys)
        self._hits: OrderedDict[str, list[float]] = OrderedDict()
        self._lock = threading.Lock()
        self._ops_since_prune = 0

    def check(self, key: str, now: float | None = None) -> tuple[bool, float]:
        """Return (allowed, retry_after_seconds)."""

        timestamp = time.monotonic() if now is None else now
        cutoff = timestamp - self._window
        with self._lock:
            self._ops_since_prune += 1
            if self._ops_since_prune >= _PRUNE_INTERVAL:
                self._ops_since_prune = 0
                self._prune_stale(cutoff)

            bucket = self._hits.get(key)
            if bucket is None:
                self._make_room(cutoff)
                bucket = []
                self._hits[key] = bucket
            else:
                self._hits.move_to_end(key)
                while bucket and bucket[0] <= cutoff:
                    bucket.pop(0)

            if len(bucket) >= self._limit:
                retry_after = max(0.1, bucket[0] + self._window - timestamp)
                return False, retry_after
            bucket.append(timestamp)
            return True, 0.0

    # -- memory hygiene ---------------------------------------------------
    def _prune_stale(self, cutoff: float) -> None:
        """Drop expired buckets; the ordering makes this stop at the first live one."""

        while self._hits:
            oldest_key = next(iter(self._hits))
            bucket = self._hits[oldest_key]
            if bucket and bucket[-1] > cutoff:
                return
            del self._hits[oldest_key]

    def _make_room(self, cutoff: float) -> None:
        """Guarantee the bucket table stays bounded before inserting a new key."""

        while len(self._hits) >= self._max_keys:
            self._prune_stale(cutoff)
            while len(self._hits) >= self._max_keys:
                self._hits.popitem(last=False)

    def tracked_keys(self) -> int:
        """Number of live buckets (diagnostics/tests only)."""

        with self._lock:
            return len(self._hits)
