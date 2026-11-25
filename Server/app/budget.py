"""Durable, fail-closed request **and token** budget for paid model calls.

Design rules (M5-C-A / M5-C-A-R1):

* **Reserve before request.**  A request is counted -- and its worst-case token
  cost is reserved -- before the upstream call is made, so a crash cannot give
  away a free call.  Failures stay counted and stay paid for.
* **One transaction.**  The global quota, the per-session quota and the token
  reservation are checked and the row is inserted inside a single
  ``BEGIN IMMEDIATE`` transaction, so concurrent turns cannot both observe
  "one slot left".
* **Unknown usage is not zero.**  When the upstream does not report usage
  (timeout, 5xx, missing ``usage`` object) the *reserved* amount is charged and
  the attempt is flagged ``usage_known=0`` / ``billing_uncertain=1``.  Zero is
  never assumed.
* **No silent recovery.**  A missing, truncated, corrupt, read-only, moved or
  epoch-mismatched ledger makes the budget *unavailable*; it never resets
  itself and never creates a new ledger at runtime.
* **Lost ledger is detected.**  The expected epoch, a monotonically growing
  request high-water mark and a token high-water mark live in a separate small
  file.  Restoring an older copy of the database (a rollback) makes
  ``count < high_water`` or ``tokens < token_high_water`` and blocks live mode.
* **Explicit administration.**  Only ``python -m app.ledger_admin init`` /
  ``reset`` (with ``--confirm``) may create a ledger or grant fresh quota.

The database is plain SQLite, as required by the project constraints (no new
paid database or Redis dependency).
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 2
STATUS_RESERVED = "reserved"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

RESERVE_OK = "ok"
RESERVE_GLOBAL_EXHAUSTED = "budget_global_exhausted"
RESERVE_SESSION_EXHAUSTED = "budget_session_exhausted"
RESERVE_TOKEN_EXHAUSTED = "budget_token_exhausted"
RESERVE_LEDGER_UNAVAILABLE = "ledger_unavailable"

ORPHAN_ERROR = "restart_orphan"


class LedgerUnavailable(RuntimeError):
    """The ledger cannot be trusted; live model calls must stay disabled."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class ReserveResult:
    allowed: bool
    attempt_id: int | None
    reason: str | None
    global_used: int = 0
    session_used: int = 0
    tokens_reserved: int = 0
    tokens_used: int = 0

    @property
    def ok(self) -> bool:
        return self.allowed


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _atomic_write_json(path: Path, payload: dict, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def _read_sentinel(epoch_path: Path) -> dict:
    try:
        raw = epoch_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise LedgerUnavailable("epoch_missing", str(epoch_path)) from exc
    except OSError as exc:
        raise LedgerUnavailable("epoch_unreadable", str(exc)) from exc
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise LedgerUnavailable("epoch_corrupt", str(exc)) from exc
    if not isinstance(payload, dict):
        raise LedgerUnavailable("epoch_corrupt", "sentinel_not_object")
    epoch = payload.get("epoch")
    high_water = payload.get("high_water")
    token_high_water = payload.get("token_high_water", 0)
    if not isinstance(epoch, str) or not epoch:
        raise LedgerUnavailable("epoch_corrupt", "missing_epoch")
    if not isinstance(high_water, int) or high_water < 0:
        raise LedgerUnavailable("epoch_corrupt", "invalid_high_water")
    if not isinstance(token_high_water, int) or token_high_water < 0:
        raise LedgerUnavailable("epoch_corrupt", "invalid_token_high_water")
    payload["high_water"] = high_water
    payload["token_high_water"] = token_high_water
    return payload


def _file_identity(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return (stat.st_dev, stat.st_ino)


class RequestBudget:
    """A single-process SQLite ledger shared by all sessions in the service."""

    def __init__(
        self,
        path: Path,
        epoch_path: Path,
        *,
        limit: int,
        per_session_limit: int,
        epoch: str,
        high_water: int,
        connection: sqlite3.Connection,
        token_limit: int = 0,
        token_high_water: int = 0,
    ) -> None:
        self.path = Path(path)
        self.epoch_path = Path(epoch_path)
        self.limit = int(limit)
        self.per_session_limit = int(per_session_limit)
        self.token_limit = max(0, int(token_limit))
        self.epoch = epoch
        self._high_water = int(high_water)
        self._token_high_water = int(token_high_water)
        self._conn = connection
        self._lock = threading.Lock()
        self._unavailable: str | None = None
        self._closed = False
        self._identity = None
        self._identity = _file_identity(self.path)

    # ------------------------------------------------------------- lifecycle

    @classmethod
    def initialize(
        cls,
        path: Path,
        epoch_path: Path,
        *,
        limit: int,
        per_session_limit: int,
        reset: bool = False,
        token_limit: int = 0,
    ) -> "RequestBudget":
        """Create a brand-new ledger generation.  Admin operation only.

        Raises ``FileExistsError`` when a ledger or epoch file already exists
        and ``reset`` is false, so a restart cannot accidentally grant quota.
        """

        path = Path(path)
        epoch_path = Path(epoch_path)
        if not reset and (path.exists() or epoch_path.exists()):
            raise FileExistsError(
                "ledger already exists; use the explicit reset operation "
                "to start a new quota generation"
            )
        for parent in {path.parent, epoch_path.parent}:
            parent.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(parent, 0o700)
            except OSError:
                pass

        epoch = uuid.uuid4().hex
        for stale in (
            path,
            path.with_name(path.name + "-journal"),
            path.with_name(path.name + "-wal"),
            path.with_name(path.name + "-shm"),
        ):
            try:
                stale.unlink()
            except FileNotFoundError:
                pass
        connection = sqlite3.connect(
            str(path), timeout=5.0, isolation_level=None, check_same_thread=False
        )
        try:
            connection.execute("PRAGMA journal_mode=DELETE")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA busy_timeout=5000")
            connection.execute("BEGIN")
            connection.execute(
                """
                CREATE TABLE meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    npc_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    latency_ms INTEGER NOT NULL DEFAULT 0,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    reserved_tokens INTEGER NOT NULL DEFAULT 0,
                    usage_known INTEGER NOT NULL DEFAULT 0,
                    billing_uncertain INTEGER NOT NULL DEFAULT 0,
                    error TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX idx_attempts_session ON attempts(session_id)"
            )
            created = _utcnow()
            connection.executemany(
                "INSERT INTO meta (key, value) VALUES (?, ?)",
                [
                    ("schema_version", str(SCHEMA_VERSION)),
                    ("ledger_epoch", epoch),
                    ("usage_count", "0"),
                    ("token_used", "0"),
                    ("token_reserved", "0"),
                    ("created_at", created),
                ],
            )
            connection.execute("COMMIT")
        except Exception:
            connection.close()
            raise
        finally:
            # Always close the initialization handle; load() reopens it.
            try:
                connection.close()
            except Exception:  # pragma: no cover - defensive
                pass
        _atomic_write_json(
            epoch_path,
            {
                "epoch": epoch,
                "high_water": 0,
                "token_high_water": 0,
                "updated_at": _utcnow(),
            },
        )
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return cls.load(
            path,
            epoch_path,
            limit=limit,
            per_session_limit=per_session_limit,
            token_limit=token_limit,
        )

    @classmethod
    def load(
        cls,
        path: Path,
        epoch_path: Path,
        *,
        limit: int,
        per_session_limit: int,
        token_limit: int = 0,
        epoch_pin: str = "",
    ) -> "RequestBudget":
        """Open and *prove* the existing ledger; never creates one."""

        path = Path(path)
        epoch_path = Path(epoch_path)
        sentinel = _read_sentinel(epoch_path)
        if epoch_pin and sentinel["epoch"] != epoch_pin:
            raise LedgerUnavailable(
                "ledger_epoch_pin_mismatch",
                "sentinel epoch does not match the independently pinned generation",
            )
        if not path.exists():
            raise LedgerUnavailable("ledger_missing", str(path))
        try:
            connection = sqlite3.connect(
                str(path), timeout=5.0, isolation_level=None, check_same_thread=False
            )
        except sqlite3.Error as exc:
            raise LedgerUnavailable("ledger_unreadable", str(exc)) from exc
        try:
            connection.execute("PRAGMA busy_timeout=5000")
            check = connection.execute("PRAGMA integrity_check").fetchone()
            if not check or check[0] != "ok":
                raise LedgerUnavailable("ledger_corrupt", "integrity_check_failed")
            meta = {
                str(key): str(value)
                for key, value in connection.execute("SELECT key, value FROM meta")
            }
            if meta.get("schema_version") != str(SCHEMA_VERSION):
                raise LedgerUnavailable(
                    "ledger_schema_mismatch", meta.get("schema_version", "")
                )
            if meta.get("ledger_epoch") != sentinel["epoch"]:
                raise LedgerUnavailable(
                    "ledger_epoch_mismatch", "epoch_generation_mismatch"
                )
            count = int(connection.execute("SELECT COUNT(*) FROM attempts").fetchone()[0])
            recorded = int(meta.get("usage_count", "-1"))
            if recorded != count:
                raise LedgerUnavailable(
                    "ledger_inconsistent", f"usage_count={recorded} rows={count}"
                )
            if count < sentinel["high_water"]:
                raise LedgerUnavailable(
                    "ledger_rollback_detected",
                    f"count={count} high_water={sentinel['high_water']}",
                )
            # Reconcile the token counters with the rows: a crash between the
            # reserve transaction and the finish transaction leaves a
            # ``reserved`` row.  It is charged conservatively (the player paid
            # for a call we cannot prove the outcome of) and never refunded.
            token_used = int(meta.get("token_used", "0"))
            outstanding = int(
                connection.execute(
                    "SELECT COALESCE(SUM(reserved_tokens), 0) FROM attempts "
                    "WHERE status = ?",
                    (STATUS_RESERVED,),
                ).fetchone()[0]
            )
            recorded_reserved = int(meta.get("token_reserved", "0"))
            if recorded_reserved != outstanding:
                # The reservation column is the source of truth.
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "UPDATE meta SET value = ? WHERE key = 'token_reserved'",
                    (str(outstanding),),
                )
                connection.execute("COMMIT")
            if token_used + outstanding < sentinel["token_high_water"]:
                raise LedgerUnavailable(
                    "ledger_rollback_detected",
                    f"tokens={token_used + outstanding} "
                    f"token_high_water={sentinel['token_high_water']}",
                )
            if outstanding:
                # Settle crash-window orphan reservations.
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    "SELECT id, reserved_tokens FROM attempts WHERE status = ?",
                    (STATUS_RESERVED,),
                ).fetchall()
                for attempt_id, reserved in rows:
                    reserved = max(0, int(reserved))
                    connection.execute(
                        """
                        UPDATE attempts
                           SET status = ?, usage_known = 0, billing_uncertain = 1,
                               error = ?, latency_ms = 0
                         WHERE id = ?
                        """,
                        (STATUS_FAILED, ORPHAN_ERROR, int(attempt_id)),
                    )
                    token_used += reserved
                connection.execute(
                    "UPDATE meta SET value = ? WHERE key = 'token_used'",
                    (str(token_used),),
                )
                connection.execute(
                    "UPDATE meta SET value = '0' WHERE key = 'token_reserved'"
                )
                connection.execute("COMMIT")
                outstanding = 0
            # Prove the file *and its directory* accept writes; a read-only
            # mount must block live calls before any paid request happens.
            # The SQLite probe must COMMIT (not ROLLBACK): SQLite only creates
            # its journal when pages are actually flushed, so a rolled-back
            # write can succeed even in a directory that denies creation.
            try:
                probe = path.parent / f".write-probe-{os.getpid()}-{uuid.uuid4().hex}"
                with open(probe, "xb") as handle:
                    handle.write(b"probe")
                    handle.flush()
                    os.fsync(handle.fileno())
                probe.unlink()
            except OSError as exc:
                raise LedgerUnavailable("ledger_read_only", str(exc)) from exc
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "UPDATE meta SET value = value WHERE key = 'ledger_epoch'"
                )
                connection.execute("COMMIT")
            except sqlite3.Error as exc:
                raise LedgerUnavailable("ledger_read_only", str(exc)) from exc
            budget = cls(
                path,
                epoch_path,
                limit=limit,
                per_session_limit=per_session_limit,
                epoch=str(sentinel["epoch"]),
                high_water=sentinel["high_water"],
                connection=connection,
                token_limit=token_limit,
                token_high_water=sentinel["token_high_water"],
            )
            # A crash between the DB commit and the sentinel fsync is
            # legitimate; raising the mark preserves the stronger proof.
            target_high = max(count, sentinel["high_water"])
            target_tokens = max(token_used, sentinel["token_high_water"])
            if target_high != sentinel["high_water"] or target_tokens != sentinel[
                "token_high_water"
            ]:
                budget._write_sentinel(target_high, target_tokens)
            return budget
        except LedgerUnavailable:
            connection.close()
            raise
        except sqlite3.Error as exc:
            connection.close()
            raise LedgerUnavailable("ledger_corrupt", str(exc)) from exc
        except Exception:
            connection.close()
            raise

    def close(self) -> None:
        with self._lock:
            self._closed = True
            try:
                self._conn.close()
            except sqlite3.Error:  # pragma: no cover - defensive
                pass

    # ------------------------------------------------------------- operations

    def reserve(
        self,
        *,
        session_id: str,
        request_id: str,
        model: str,
        npc_id: str,
        reserved_tokens: int = 0,
    ) -> ReserveResult:
        reserved_tokens = max(0, int(reserved_tokens))
        with self._lock:
            if self._closed:
                return ReserveResult(False, None, RESERVE_LEDGER_UNAVAILABLE)
            if self._unavailable:
                return ReserveResult(False, None, self._unavailable)
            if not self._ledger_is_intact():
                return ReserveResult(False, None, RESERVE_LEDGER_UNAVAILABLE)
            try:
                cursor = self._conn.cursor()
                cursor.execute("BEGIN IMMEDIATE")
                global_used = int(
                    cursor.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
                )
                session_used = int(
                    cursor.execute(
                        "SELECT COUNT(*) FROM attempts WHERE session_id = ?",
                        (session_id,),
                    ).fetchone()[0]
                )
                tokens_used = int(
                    cursor.execute(
                        "SELECT value FROM meta WHERE key = 'token_used'"
                    ).fetchone()[0]
                )
                tokens_reserved = int(
                    cursor.execute(
                        "SELECT value FROM meta WHERE key = 'token_reserved'"
                    ).fetchone()[0]
                )
                if global_used >= self.limit:
                    cursor.execute("ROLLBACK")
                    return ReserveResult(
                        False,
                        None,
                        RESERVE_GLOBAL_EXHAUSTED,
                        global_used,
                        session_used,
                    )
                if session_used >= self.per_session_limit:
                    cursor.execute("ROLLBACK")
                    return ReserveResult(
                        False,
                        None,
                        RESERVE_SESSION_EXHAUSTED,
                        global_used,
                        session_used,
                    )
                if reserved_tokens and self.token_limit:
                    if tokens_used + tokens_reserved + reserved_tokens > self.token_limit:
                        cursor.execute("ROLLBACK")
                        return ReserveResult(
                            False,
                            None,
                            RESERVE_TOKEN_EXHAUSTED,
                            global_used,
                            session_used,
                            0,
                            tokens_used,
                        )
                cursor.execute(
                    """
                    INSERT INTO attempts
                        (started_at, request_id, session_id, model, npc_id,
                         status, reserved_tokens)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _utcnow(),
                        request_id,
                        session_id,
                        model,
                        npc_id,
                        STATUS_RESERVED,
                        reserved_tokens,
                    ),
                )
                attempt_id = int(cursor.lastrowid)
                cursor.execute(
                    "UPDATE meta SET value = ? WHERE key = 'usage_count'",
                    (str(global_used + 1),),
                )
                if reserved_tokens:
                    cursor.execute(
                        "UPDATE meta SET value = ? WHERE key = 'token_reserved'",
                        (str(tokens_reserved + reserved_tokens),),
                    )
                cursor.execute("COMMIT")
            except sqlite3.Error:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                self._disable("ledger_write_failed")
                return ReserveResult(False, None, RESERVE_LEDGER_UNAVAILABLE)
            used_after = global_used + 1
        try:
            # The token marker tracks *settled* spend only; an outstanding
            # reservation is already durable in the database row.
            self._write_sentinel(used_after, tokens_used)
        except OSError:
            # The attempt was counted but we cannot prove the epoch file is
            # durable: refuse to spend on the upstream and fail closed.
            self._disable("epoch_write_failed")
            try:
                self.finish(attempt_id, STATUS_FAILED, error="epoch_write_failed")
            except LedgerUnavailable:
                pass
            return ReserveResult(False, None, RESERVE_LEDGER_UNAVAILABLE)
        return ReserveResult(
            True,
            attempt_id,
            RESERVE_OK,
            used_after,
            session_used + 1,
            reserved_tokens,
            tokens_used,
        )

    def finish(
        self,
        attempt_id: int,
        status: str,
        *,
        latency_ms: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        error: str | None = None,
        tokens_known: bool | None = None,
        billing_uncertain: bool | None = None,
    ) -> None:
        """Close an attempt and settle its token reservation.

        ``tokens_known`` defaults to "only a completed call with reported
        usage is known"; everything else is charged the reservation.  There is
        no path that refunds a reservation to zero without proof.
        """

        if status not in {STATUS_COMPLETED, STATUS_FAILED}:
            # Keep the accepted statuses explicit; reserved must be finished.
            status = STATUS_FAILED
        prompt_tokens = max(0, int(prompt_tokens))
        completion_tokens = max(0, int(completion_tokens))
        if tokens_known is None:
            tokens_known = (
                status == STATUS_COMPLETED and (prompt_tokens + completion_tokens) > 0
            )
        if billing_uncertain is None:
            billing_uncertain = not tokens_known
        with self._lock:
            if self._closed:
                return
            try:
                row = self._conn.execute(
                    "SELECT reserved_tokens, status FROM attempts WHERE id = ?",
                    (int(attempt_id),),
                ).fetchone()
                if row is None:
                    return
                reserved, current = int(row[0]), str(row[1])
                if current != STATUS_RESERVED:
                    # Idempotent: never settle the same reservation twice.
                    return
                consumed = prompt_tokens + completion_tokens if tokens_known else reserved
                self._conn.execute("BEGIN IMMEDIATE")
                self._conn.execute(
                    """
                    UPDATE attempts
                       SET status = ?, latency_ms = ?, prompt_tokens = ?,
                           completion_tokens = ?, usage_known = ?,
                           billing_uncertain = ?, error = ?
                     WHERE id = ?
                    """,
                    (
                        status,
                        max(0, int(latency_ms)),
                        prompt_tokens,
                        completion_tokens,
                        1 if tokens_known else 0,
                        1 if billing_uncertain else 0,
                        error,
                        int(attempt_id),
                    ),
                )
                tokens_used = int(
                    self._conn.execute(
                        "SELECT value FROM meta WHERE key = 'token_used'"
                    ).fetchone()[0]
                )
                tokens_reserved = int(
                    self._conn.execute(
                        "SELECT value FROM meta WHERE key = 'token_reserved'"
                    ).fetchone()[0]
                )
                tokens_used += max(0, consumed)
                tokens_reserved = max(0, tokens_reserved - reserved)
                self._conn.execute(
                    "UPDATE meta SET value = ? WHERE key = 'token_used'",
                    (str(tokens_used),),
                )
                self._conn.execute(
                    "UPDATE meta SET value = ? WHERE key = 'token_reserved'",
                    (str(tokens_reserved),),
                )
                self._conn.execute("COMMIT")
            except sqlite3.Error:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                self._disable("ledger_write_failed")
                return
        try:
            self._write_sentinel(
                max(self._high_water, self._count_attempts()),
                tokens_used,
            )
        except OSError:
            # The charge is committed; an unprovable epoch file blocks further
            # spending.  The player still gets the answer that was already paid
            # for, so this must not raise into the request path.
            self._disable("epoch_write_failed")

    # --------------------------------------------------------------- queries

    def usage(self) -> dict:
        try:
            with self._lock:
                global_used = int(
                    self._conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
                )
                meta = {
                    str(key): str(value)
                    for key, value in self._conn.execute(
                        "SELECT key, value FROM meta WHERE key IN "
                        "('token_used', 'token_reserved')"
                    )
                }
                unknown = int(
                    self._conn.execute(
                        "SELECT COUNT(*) FROM attempts WHERE usage_known = 0 "
                        "AND status != ?",
                        (STATUS_RESERVED,),
                    ).fetchone()[0]
                )
                uncertain = int(
                    self._conn.execute(
                        "SELECT COUNT(*) FROM attempts WHERE billing_uncertain = 1"
                    ).fetchone()[0]
                )
            tokens_used = int(meta.get("token_used", "0"))
            tokens_reserved = int(meta.get("token_reserved", "0"))
            return {
                "status": "ready" if self._unavailable is None else self._unavailable,
                "global_used": global_used,
                "global_limit": self.limit,
                "session_limit": self.per_session_limit,
                "tokens_used": tokens_used,
                "tokens_reserved": tokens_reserved,
                "token_limit": self.token_limit,
                "unknown_usage_attempts": unknown,
                "uncertain_billing_attempts": uncertain,
                "epoch_fingerprint": self.epoch[:12],
                "persistent": self._unavailable is None,
            }
        except sqlite3.Error:
            self._disable("ledger_read_failed")
            return {
                "status": "ledger_read_failed",
                "global_used": None,
                "global_limit": self.limit,
                "session_limit": self.per_session_limit,
                "tokens_used": None,
                "tokens_reserved": None,
                "token_limit": self.token_limit,
                "unknown_usage_attempts": None,
                "uncertain_billing_attempts": None,
                "epoch_fingerprint": self.epoch[:12],
                "persistent": False,
            }

    @property
    def unavailable_reason(self) -> str | None:
        if self._closed:
            return "ledger_closed"
        return self._unavailable

    # ------------------------------------------------------------- internals

    def _count_attempts(self) -> int:
        try:
            return int(self._conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0])
        except sqlite3.Error:
            return self._high_water

    def _ledger_is_intact(self) -> bool:
        """Detect a ledger file deleted, moved or swapped under the process."""

        if not self.path.exists():
            self._disable("ledger_missing")
            return False
        if _file_identity(self.path) != self._identity:
            self._disable("ledger_replaced")
            return False
        return True

    def _write_sentinel(self, high_water: int, token_high_water: int) -> None:
        if not self.epoch_path.exists():
            raise OSError("epoch sentinel disappeared")
        _atomic_write_json(
            self.epoch_path,
            {
                "epoch": self.epoch,
                "high_water": int(high_water),
                "token_high_water": max(0, int(token_high_water)),
                "updated_at": _utcnow(),
            },
        )
        self._high_water = int(high_water)
        self._token_high_water = max(0, int(token_high_water))

    def _disable(self, reason: str) -> None:
        if self._unavailable is None:
            self._unavailable = reason


# Kept for callers that import the old constant name.
RESERVE_LEDGER_CLOSED = "ledger_closed"
