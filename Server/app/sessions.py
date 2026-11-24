"""In-memory conversation sessions.

Sessions are deliberately *not* persisted: Docs/DataSchema.md section 5 says a
restored save expires all conversations, and free player text never reaches
the durable command ledger.  A process restart therefore ends every session,
which is the safe behaviour this first version wants.

Isolation rules (M4-C):

* creating a session never touches another session -- two players (or two
  browser tabs) keep independent conversations, evidence acknowledgement and
  disclosure state;
* the store is bounded.  Expired sessions are swept on every write, terminal
  sessions are purged after a short retention window, and a hard cap evicts
  the oldest session when a public deployment would otherwise grow without
  limit.  Evicted sessions answer ``404 NOT_FOUND`` (they no longer exist),
  while sessions that ended normally answer ``404``/``410`` as documented.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field

from .errors import not_found, turn_expired

STATUS_OPEN = "open"
STATUS_CLOSED = "closed"
STATUS_CANCELLED = "cancelled"
STATUS_EXPIRED = "expired"

TERMINAL_STATUSES = frozenset({STATUS_CLOSED, STATUS_CANCELLED, STATUS_EXPIRED})
DEFAULT_MAX_SESSIONS = 512
# How long a finished session stays queryable (so a client can read the final
# state) before it is dropped from memory.
TERMINAL_RETENTION_SECONDS = 300.0


@dataclass
class Session:
    conversation_id: str
    npc_id: str
    ttl_seconds: float
    created_at: float
    expires_at: float
    status: str = STATUS_OPEN
    acquired_evidence_ids: set[str] = field(default_factory=set)
    observed_field_ids: set[str] = field(default_factory=set)
    presented_evidence_ids: set[str] = field(default_factory=set)
    presented_field_ids: set[str] = field(default_factory=set)
    triggered_disclosure_ids: set[str] = field(default_factory=set)
    last_turn_id: str | None = None
    ended_at: float | None = None

    @property
    def is_open(self) -> bool:
        return self.status == STATUS_OPEN

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    def touch(self, now: float) -> None:
        self.expires_at = now + self.ttl_seconds


class SessionStore:
    """Bounded, thread-safe session registry with strict per-session isolation."""

    def __init__(
        self,
        ttl_seconds: float,
        *,
        max_sessions: int = DEFAULT_MAX_SESSIONS,
        terminal_retention_seconds: float = TERMINAL_RETENTION_SECONDS,
    ) -> None:
        self._ttl = float(ttl_seconds)
        self._max_sessions = max(1, int(max_sessions))
        self._retention = max(0.0, float(terminal_retention_seconds))
        self._sessions: OrderedDict[str, Session] = OrderedDict()
        self._lock = threading.Lock()

    # ----------------------------------------------------------- inspection

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)

    def open_count(self) -> int:
        with self._lock:
            return sum(1 for session in self._sessions.values() if session.is_open)

    # ---------------------------------------------------------------- write

    def create(
        self,
        npc_id: str,
        evidence_ids: set[str],
        observed_field_ids: set[str],
    ) -> Session:
        now = time.monotonic()
        with self._lock:
            self._expire_locked(now)
            self._purge_locked(now)
            self._make_room_locked(now)
            session = Session(
                conversation_id=str(uuid.uuid4()),
                npc_id=npc_id,
                ttl_seconds=self._ttl,
                created_at=now,
                expires_at=now + self._ttl,
            )
            session.acquired_evidence_ids.update(evidence_ids)
            session.observed_field_ids.update(observed_field_ids)
            self._sessions[session.conversation_id] = session
            return session

    def get(self, conversation_id: str) -> Session:
        now = time.monotonic()
        with self._lock:
            session = self._sessions.get(conversation_id)
            if session is None:
                raise not_found("会话不存在或已关闭。")
            if session.is_open and now >= session.expires_at:
                self._terminate_locked(session, STATUS_EXPIRED, now)
            if not session.is_open:
                raise turn_expired("会话已关闭或过期，请重新进入对话。")
            session.touch(now)
            return session

    def cancel(self, conversation_id: str) -> Session:
        now = time.monotonic()
        with self._lock:
            session = self._sessions.get(conversation_id)
            if session is None:
                raise not_found("会话不存在或已关闭。")
            if session.is_open:
                self._terminate_locked(session, STATUS_CANCELLED, now)
            return session

    def close(self, conversation_id: str) -> Session:
        """Close an open session (normal end of a conversation, e.g. ``*.leave``)."""

        now = time.monotonic()
        with self._lock:
            session = self._sessions.get(conversation_id)
            if session is None:
                raise not_found("会话不存在或已关闭。")
            if session.is_open:
                self._terminate_locked(session, STATUS_CLOSED, now)
            return session

    def expire_all_open(self) -> None:
        now = time.monotonic()
        with self._lock:
            for session in self._sessions.values():
                if session.is_open:
                    self._terminate_locked(session, STATUS_EXPIRED, now)

    # -------------------------------------------------------------- private

    def _terminate_locked(self, session: Session, status: str, now: float) -> None:
        session.status = status
        session.ended_at = now

    def _expire_locked(self, now: float) -> None:
        for session in self._sessions.values():
            if session.is_open and now >= session.expires_at:
                self._terminate_locked(session, STATUS_EXPIRED, now)

    def _purge_locked(self, now: float) -> None:
        if self._retention <= 0:
            return
        stale = [
            conversation_id
            for conversation_id, session in self._sessions.items()
            if session.is_terminal
            and session.ended_at is not None
            and now - session.ended_at >= self._retention
        ]
        for conversation_id in stale:
            del self._sessions[conversation_id]

    def _make_room_locked(self, now: float) -> None:
        while len(self._sessions) >= self._max_sessions:
            victim_id, victim = self._pick_eviction_locked()
            self._sessions.pop(victim_id, None)
            if victim.is_open:
                # Hard cap wins over liveness: the client is told to start a
                # new conversation instead of the process growing unbounded.
                victim.status = STATUS_EXPIRED
                victim.ended_at = now

    def _pick_eviction_locked(self) -> tuple[str, Session]:
        for conversation_id, session in self._sessions.items():
            if session.is_terminal:
                return conversation_id, session
        conversation_id = next(iter(self._sessions))
        return conversation_id, self._sessions[conversation_id]
