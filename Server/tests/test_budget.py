"""Durable request-budget ledger tests (M5-C-A section 5).

Every test uses a real SQLite file in pytest's temp dir; nothing is mocked
except time where noted.  No network is involved.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.budget import (
    RESERVE_GLOBAL_EXHAUSTED,
    RESERVE_SESSION_EXHAUSTED,
    LedgerUnavailable,
    RequestBudget,
)

LIMIT = 5
PER_SESSION = 2


def _init(tmp_path, *, limit=LIMIT, per_session=PER_SESSION) -> RequestBudget:
    return RequestBudget.initialize(
        tmp_path / "ledger.sqlite3",
        tmp_path / "epoch" / "ledger-epoch.json",
        limit=limit,
        per_session_limit=per_session,
    )


def _reserve(budget, session="s1", request_id=None):
    return budget.reserve(
        session_id=session,
        request_id=request_id or f"req-{session}-{budget.usage()['global_used']}",
        model="fake-model",
        npc_id="npc_laozhou",
    )


def test_initialize_creates_dirs_and_refuses_a_second_generation(tmp_path):
    budget = _init(tmp_path)
    assert (tmp_path / "epoch" / "ledger-epoch.json").exists()
    budget.close()
    with pytest.raises(FileExistsError):
        _init(tmp_path)


def test_reserve_counts_before_the_request_and_failures_stay_counted(tmp_path):
    budget = _init(tmp_path, limit=10, per_session=10)
    first = _reserve(budget, "s1")
    assert first.allowed and first.attempt_id
    # Simulate a request that fails upstream: the attempt is still consumed.
    budget.finish(first.attempt_id, "failed", error="upstream_status_500")
    assert budget.usage()["global_used"] == 1
    second = _reserve(budget, "s1")
    assert second.allowed
    budget.finish(second.attempt_id, "completed", prompt_tokens=11, completion_tokens=7)
    budget.close()

    reopened = RequestBudget.load(
        tmp_path / "ledger.sqlite3",
        tmp_path / "epoch" / "ledger-epoch.json",
        limit=10,
        per_session_limit=10,
    )
    assert reopened.usage()["global_used"] == 2
    with sqlite3.connect(tmp_path / "ledger.sqlite3") as connection:
        rows = connection.execute(
            "SELECT status, prompt_tokens, completion_tokens, error FROM attempts ORDER BY id"
        ).fetchall()
    assert rows[0][0] == "failed"
    assert rows[1] == ("completed", 11, 7, None)
    reopened.close()


def test_global_limit_is_enforced(tmp_path):
    budget = _init(tmp_path, limit=3, per_session=3)
    for index in range(3):
        assert _reserve(budget, f"s{index}").allowed
    refused = _reserve(budget, "s9")
    assert refused.allowed is False
    assert refused.reason == RESERVE_GLOBAL_EXHAUSTED
    assert budget.usage()["global_used"] == 3
    budget.close()


def test_one_session_cannot_exhaust_the_whole_service(tmp_path):
    budget = _init(tmp_path, limit=5, per_session=2)
    assert _reserve(budget, "greedy").allowed
    assert _reserve(budget, "greedy").allowed
    refused = _reserve(budget, "greedy")
    assert refused.allowed is False
    assert refused.reason == RESERVE_SESSION_EXHAUSTED
    # Another session still has budget; the greedy one did not eat it all.
    assert _reserve(budget, "other").allowed
    assert budget.usage()["global_used"] == 3
    budget.close()


def test_concurrent_reservations_never_exceed_the_limit(tmp_path):
    budget = _init(tmp_path, limit=4, per_session=4)

    def attempt(index: int) -> bool:
        return _reserve(budget, "shared").allowed

    with ThreadPoolExecutor(max_workers=12) as pool:
        granted = list(pool.map(attempt, range(12)))
    assert sum(granted) == 4
    assert budget.usage()["global_used"] == 4
    budget.close()


def test_reservations_survive_process_restart(tmp_path):
    budget = _init(tmp_path, limit=2, per_session=2)
    assert _reserve(budget).allowed
    budget.close()  # simulates process exit without finishing the attempt
    reopened = RequestBudget.load(
        tmp_path / "ledger.sqlite3",
        tmp_path / "epoch" / "ledger-epoch.json",
        limit=2,
        per_session_limit=2,
    )
    assert reopened.usage()["global_used"] == 1
    assert _reserve(reopened, "s2").allowed
    refused = _reserve(reopened, "s3")
    assert refused.allowed is False
    reopened.close()


def test_missing_ledger_is_detected_and_never_recreated(tmp_path):
    budget = _init(tmp_path)
    budget.close()
    (tmp_path / "ledger.sqlite3").unlink()
    with pytest.raises(LedgerUnavailable) as excinfo:
        RequestBudget.load(
            tmp_path / "ledger.sqlite3",
            tmp_path / "epoch" / "ledger-epoch.json",
            limit=LIMIT,
            per_session_limit=PER_SESSION,
        )
    assert excinfo.value.reason == "ledger_missing"
    assert not (tmp_path / "ledger.sqlite3").exists()


def test_truncated_ledger_is_corrupt_not_reset(tmp_path):
    budget = _init(tmp_path)
    budget.close()
    path = tmp_path / "ledger.sqlite3"
    raw = path.read_bytes()
    path.write_bytes(raw[: len(raw) // 3])
    with pytest.raises(LedgerUnavailable) as excinfo:
        RequestBudget.load(
            path,
            tmp_path / "epoch" / "ledger-epoch.json",
            limit=LIMIT,
            per_session_limit=PER_SESSION,
        )
    assert excinfo.value.reason in {"ledger_corrupt", "ledger_unreadable"}


def test_garbage_sqlite_file_is_rejected(tmp_path):
    ledger = _init(tmp_path)
    ledger.close()
    path = tmp_path / "ledger.sqlite3"
    path.write_bytes(b"not a database at all" * 100)
    with pytest.raises(LedgerUnavailable) as excinfo:
        RequestBudget.load(
            path,
            tmp_path / "epoch" / "ledger-epoch.json",
            limit=LIMIT,
            per_session_limit=PER_SESSION,
        )
    assert excinfo.value.reason in {"ledger_corrupt", "ledger_unreadable"}


def test_missing_or_corrupt_epoch_sentinel_blocks_use(tmp_path):
    budget = _init(tmp_path)
    budget.close()
    epoch_path = tmp_path / "epoch" / "ledger-epoch.json"
    epoch_path.unlink()
    with pytest.raises(LedgerUnavailable) as excinfo:
        RequestBudget.load(
            tmp_path / "ledger.sqlite3", epoch_path, limit=LIMIT, per_session_limit=PER_SESSION
        )
    assert excinfo.value.reason == "epoch_missing"

    epoch_path.write_text("{not json", encoding="utf-8")
    with pytest.raises(LedgerUnavailable) as excinfo:
        RequestBudget.load(
            tmp_path / "ledger.sqlite3", epoch_path, limit=LIMIT, per_session_limit=PER_SESSION
        )
    assert excinfo.value.reason == "epoch_corrupt"


def test_epoch_mismatch_is_refused(tmp_path):
    budget = _init(tmp_path)
    budget.close()
    epoch_path = tmp_path / "epoch" / "ledger-epoch.json"
    payload = json.loads(epoch_path.read_text(encoding="utf-8"))
    payload["epoch"] = "different-generation"
    epoch_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(LedgerUnavailable) as excinfo:
        RequestBudget.load(
            tmp_path / "ledger.sqlite3", epoch_path, limit=LIMIT, per_session_limit=PER_SESSION
        )
    assert excinfo.value.reason == "ledger_epoch_mismatch"


def test_rollback_of_the_database_is_detected(tmp_path):
    budget = _init(tmp_path, limit=10, per_session=10)
    assert _reserve(budget, "s1").allowed
    assert _reserve(budget, "s1").allowed
    backup = tmp_path / "backup.sqlite3"
    shutil.copyfile(tmp_path / "ledger.sqlite3", backup)
    assert _reserve(budget, "s1").allowed
    budget.close()

    # Restore an older copy: the sentinel high-water mark now exceeds the
    # number of rows, which is exactly the "ledger rolled back" signal.
    shutil.copyfile(backup, tmp_path / "ledger.sqlite3")
    with pytest.raises(LedgerUnavailable) as excinfo:
        RequestBudget.load(
            tmp_path / "ledger.sqlite3",
            tmp_path / "epoch" / "ledger-epoch.json",
            limit=10,
            per_session_limit=10,
        )
    assert excinfo.value.reason == "ledger_rollback_detected"


def test_usage_count_tampering_is_detected(tmp_path):
    budget = _init(tmp_path, limit=10, per_session=10)
    _reserve(budget, "s1")
    budget.close()
    with sqlite3.connect(tmp_path / "ledger.sqlite3") as connection:
        connection.execute("UPDATE meta SET value = '0' WHERE key = 'usage_count'")
    with pytest.raises(LedgerUnavailable) as excinfo:
        RequestBudget.load(
            tmp_path / "ledger.sqlite3",
            tmp_path / "epoch" / "ledger-epoch.json",
            limit=10,
            per_session_limit=10,
        )
    assert excinfo.value.reason == "ledger_inconsistent"


def test_read_only_ledger_blocks_live_use(tmp_path):
    budget = _init(tmp_path)
    budget.close()
    path = tmp_path / "ledger.sqlite3"
    os.chmod(path, 0o444)
    try:
        with pytest.raises(LedgerUnavailable) as excinfo:
            RequestBudget.load(
                path,
                tmp_path / "epoch" / "ledger-epoch.json",
                limit=LIMIT,
                per_session_limit=PER_SESSION,
            )
        assert excinfo.value.reason in {"ledger_read_only", "ledger_unreadable"}
    finally:
        os.chmod(path, 0o600)


def test_reset_is_an_explicit_new_generation(tmp_path):
    budget = _init(tmp_path, limit=2, per_session=2)
    _reserve(budget, "s1")
    _reserve(budget, "s1")
    old_epoch = budget.epoch
    budget.close()

    fresh = RequestBudget.initialize(
        tmp_path / "ledger.sqlite3",
        tmp_path / "epoch" / "ledger-epoch.json",
        limit=2,
        per_session_limit=2,
        reset=True,
    )
    assert fresh.epoch != old_epoch
    assert fresh.usage()["global_used"] == 0
    assert _reserve(fresh, "s1").allowed
    fresh.close()


def test_sentinel_high_water_tracks_every_reservation(tmp_path):
    budget = _init(tmp_path, limit=5, per_session=5)
    _reserve(budget, "s1")
    sentinel = json.loads(
        (tmp_path / "epoch" / "ledger-epoch.json").read_text(encoding="utf-8")
    )
    assert sentinel["high_water"] == 1
    assert sentinel["epoch"] == budget.epoch
    budget.close()
