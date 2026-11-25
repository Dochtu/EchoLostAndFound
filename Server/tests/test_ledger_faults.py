"""M5-C-A-R1 section 5: what the SQLite ledger can and cannot prove.

Every scenario here is a fault-injection test against ``RequestBudget``; no
network, no real model.  The documented *gap* (a consistent rollback of both
the database and the sentinel to the same older snapshot) is pinned as a test
so the limitation stays visible instead of silently regressing.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

import pytest

import app.budget as budget_module
from app.budget import (
    RESERVE_LEDGER_UNAVAILABLE,
    RESERVE_OK,
    LedgerUnavailable,
    RequestBudget,
)

LEDGER_NAME = "ledger.sqlite3"
EPOCH_NAME = "ledger-epoch.json"
TOKENS = 1756


def _paths(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / LEDGER_NAME, tmp_path / "epoch" / EPOCH_NAME


def _init(tmp_path: Path, *, limit: int = 5, per_session: int = 3, token_limit: int = 10000):
    path, epoch_path = _paths(tmp_path)
    return RequestBudget.initialize(
        path,
        epoch_path,
        limit=limit,
        per_session_limit=per_session,
        token_limit=token_limit,
    )


def _load(tmp_path: Path, *, limit: int = 5, per_session: int = 3, token_limit: int = 10000, **kwargs):
    path, epoch_path = _paths(tmp_path)
    return RequestBudget.load(
        path,
        epoch_path,
        limit=limit,
        per_session_limit=per_session,
        token_limit=token_limit,
        **kwargs,
    )


def _reserve(budget: RequestBudget, *, session: str = "s1", tokens: int = TOKENS):
    return budget.reserve(
        session_id=session,
        request_id=f"req-{session}",
        model="fake-model",
        npc_id="npc_laozhou",
        reserved_tokens=tokens,
    )


def _settle(budget: RequestBudget, attempt_id: int, *, prompt: int = 6, completion: int = 4):
    budget.finish(
        attempt_id,
        "completed",
        prompt_tokens=prompt,
        completion_tokens=completion,
    )


def _sentinel_payload(epoch_path: Path) -> dict:
    return json.loads(epoch_path.read_text(encoding="utf-8"))


def _write_sentinel_json(epoch_path: Path, payload: dict) -> None:
    epoch_path.write_text(json.dumps(payload), encoding="utf-8")


class _BrokenConnection:
    """A connection whose every operation fails like a full disk."""

    def cursor(self):  # noqa: D401 - test double
        raise sqlite3.OperationalError("disk I/O error")

    def execute(self, *args, **kwargs):  # noqa: D401 - test double
        raise sqlite3.OperationalError("disk I/O error")

    def close(self) -> None:
        pass


# --------------------------------------------------------------- lost state


def test_lost_ledger_and_sentinel_never_auto_initialize(tmp_path):
    budget = _init(tmp_path)
    budget.close()
    path, epoch_path = _paths(tmp_path)
    path.unlink()
    epoch_path.unlink()

    with pytest.raises(LedgerUnavailable) as excinfo:
        _load(tmp_path)

    # Either check may fire first; both are fail-closed and neither recreates.
    assert excinfo.value.reason in {"epoch_missing", "ledger_missing"}
    assert not path.exists()
    assert not epoch_path.exists()


def test_missing_database_only_is_reported_as_lost(tmp_path):
    budget = _init(tmp_path)
    budget.close()
    path, _ = _paths(tmp_path)
    path.unlink()

    with pytest.raises(LedgerUnavailable) as excinfo:
        _load(tmp_path)

    assert excinfo.value.reason == "ledger_missing"
    assert not path.exists(), "a missing ledger must never be recreated"


def test_lost_sentinel_blocks_and_is_not_recreated(tmp_path):
    budget = _init(tmp_path)
    _settle(budget, _reserve(budget).attempt_id)
    budget.close()
    path, epoch_path = _paths(tmp_path)
    epoch_path.unlink()

    with pytest.raises(LedgerUnavailable) as excinfo:
        _load(tmp_path)

    assert excinfo.value.reason == "epoch_missing"
    assert path.exists(), "the ledger itself must be left untouched"
    assert not epoch_path.exists()


def test_whole_snapshot_rollback_is_a_documented_gap(tmp_path):
    """Both files restored to the same older snapshot is *not* detectable.

    A monotonic high-water mark can only catch a rollback of one of the two
    files.  If an attacker (or a platform snapshot restore) rewinds the database
    and the sentinel together, the pair stays internally consistent.  This is
    why the platform persistence question is still an open launch blocker.
    """

    budget = _init(tmp_path, limit=10, per_session=8)
    for _ in range(2):
        _settle(budget, _reserve(budget).attempt_id)
    path, epoch_path = _paths(tmp_path)
    backup = tmp_path / "backup"
    shutil.copytree(epoch_path.parent, backup / "epoch")
    shutil.copy2(path, backup / LEDGER_NAME)

    for _ in range(2):
        _settle(budget, _reserve(budget).attempt_id)
    assert budget.usage()["global_used"] == 4
    budget.close()

    shutil.copy2(backup / LEDGER_NAME, path)
    shutil.copy2(backup / "epoch" / EPOCH_NAME, epoch_path)

    reopened = _load(tmp_path, limit=10)
    assert reopened.unavailable_reason is None
    assert reopened.usage()["global_used"] == 2, "the two newer turns were refunded"


def test_rollback_of_one_file_is_detected(tmp_path):
    budget = _init(tmp_path, limit=10, per_session=8)
    for _ in range(3):
        _settle(budget, _reserve(budget).attempt_id)
    path, epoch_path = _paths(tmp_path)
    older = tmp_path / "older.sqlite3"
    shutil.copy2(path, older)
    for _ in range(2):
        _settle(budget, _reserve(budget).attempt_id)
    budget.close()

    # Only the database is rewound; the sentinel keeps the newer high-water mark.
    shutil.copy2(older, path)

    with pytest.raises(LedgerUnavailable) as excinfo:
        _load(tmp_path, limit=10)
    assert excinfo.value.reason == "ledger_rollback_detected"


def test_epoch_pin_detects_a_regenerated_generation(tmp_path):
    budget = _init(tmp_path, limit=10)
    pinned = budget.epoch
    loaded = _load(tmp_path, limit=10, epoch_pin=pinned)
    assert loaded.usage()["epoch_fingerprint"] == pinned[:12]
    loaded.close()
    budget.close()

    # The administrator intentionally starts a fresh generation (new epoch).
    path, epoch_path = _paths(tmp_path)
    regenerated = RequestBudget.initialize(
        path,
        epoch_path,
        limit=10,
        per_session_limit=3,
        token_limit=10000,
        reset=True,
    )
    assert regenerated.epoch != pinned
    regenerated.close()

    with pytest.raises(LedgerUnavailable) as excinfo:
        _load(tmp_path, limit=10, epoch_pin=pinned)
    assert excinfo.value.reason == "ledger_epoch_pin_mismatch"


# ------------------------------------------------------------ write failures


def test_sentinel_write_failure_refuses_the_spend(tmp_path, monkeypatch):
    budget = _init(tmp_path, limit=10)

    def boom(high_water, token_high_water):
        raise OSError("disk full")

    monkeypatch.setattr(budget, "_write_sentinel", boom)
    result = _reserve(budget)

    assert result.allowed is False
    assert result.reason == RESERVE_LEDGER_UNAVAILABLE
    assert budget.unavailable_reason == "epoch_write_failed"
    usage = budget.usage()
    assert usage["global_used"] == 1
    assert usage["tokens_used"] == TOKENS, "an unprovable attempt is still charged"


def test_disk_full_during_reserve_fails_closed(tmp_path, monkeypatch):
    budget = _init(tmp_path, limit=10)
    monkeypatch.setattr(budget, "_conn", _BrokenConnection())

    result = _reserve(budget)

    assert result.allowed is False
    assert result.reason == RESERVE_LEDGER_UNAVAILABLE
    assert budget.unavailable_reason == "ledger_write_failed"


# ---------------------------------------------------------------- crash windows


def test_crash_after_commit_before_sentinel_is_repaired(tmp_path, monkeypatch):
    budget = _init(tmp_path, limit=10)
    monkeypatch.setattr(budget, "_write_sentinel", lambda *args: None)
    assert _reserve(budget).allowed is True
    epoch_path = _paths(tmp_path)[1]
    assert _sentinel_payload(epoch_path)["high_water"] == 0
    budget.close()

    reopened = _load(tmp_path, limit=10)

    assert reopened.usage()["global_used"] == 1
    assert _sentinel_payload(epoch_path)["high_water"] == 1


def test_crash_after_sentinel_before_upstream_is_settled_as_orphan(tmp_path):
    budget = _init(tmp_path, limit=10)
    result = _reserve(budget)
    assert result.allowed is True
    budget.close()  # process dies: the attempt stays "reserved"

    reopened = _load(tmp_path, limit=10)

    usage = reopened.usage()
    assert usage["global_used"] == 1
    assert usage["tokens_used"] == TOKENS
    assert usage["tokens_reserved"] == 0
    assert usage["unknown_usage_attempts"] == 1
    with sqlite3.connect(_paths(tmp_path)[0]) as conn:
        row = conn.execute(
            "SELECT status, error, usage_known, billing_uncertain, reserved_tokens"
            " FROM attempts ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert row == ("failed", "restart_orphan", 0, 1, TOKENS)


def test_restart_keeps_the_budget_consistent(tmp_path):
    budget = _init(tmp_path, limit=10)
    for _ in range(3):
        _settle(budget, _reserve(budget).attempt_id)
    before = budget.usage()
    budget.close()

    reopened = _load(tmp_path, limit=10)
    after = reopened.usage()

    assert after["global_used"] == 3
    assert after["tokens_used"] == before["tokens_used"] == 30
    assert after["tokens_reserved"] == 0
    assert after["epoch_fingerprint"] == before["epoch_fingerprint"]
    assert RESERVE_OK == "ok"


# ------------------------------------------------------- ledger swapped at runtime


def test_swapped_ledger_is_detected_at_runtime(tmp_path, monkeypatch):
    """Windows keeps the database handle open, so the swap is simulated.

    The service compares the ``(st_dev, st_ino)`` identity captured at load
    time with the file it is about to write to.
    """

    budget = _init(tmp_path, limit=10)
    monkeypatch.setattr(budget_module, "_file_identity", lambda path: (0, 0))

    result = _reserve(budget)

    assert result.allowed is False
    assert result.reason == RESERVE_LEDGER_UNAVAILABLE
    assert budget.unavailable_reason == "ledger_replaced"


def test_deleted_ledger_is_detected_at_runtime(tmp_path):
    budget = _init(tmp_path, limit=10)
    budget.path = Path(tmp_path / "somewhere-else.sqlite3")

    result = _reserve(budget)

    assert result.allowed is False
    assert budget.unavailable_reason == "ledger_missing"


# ------------------------------------------------------------- quota semantics


def test_orphan_and_failure_counting_is_never_refunded(tmp_path):
    budget = _init(tmp_path, limit=10)
    first = _reserve(budget)
    budget.finish(first.attempt_id, "failed", error="upstream_timeout")
    second = _reserve(budget)
    _settle(budget, second.attempt_id, prompt=11, completion=7)

    usage = budget.usage()
    assert usage["global_used"] == 2
    assert usage["tokens_used"] == TOKENS + 18
    assert usage["uncertain_billing_attempts"] == 1
    assert usage["unknown_usage_attempts"] == 1
