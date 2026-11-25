"""Explicit ledger administration CLI: init / reset / verify."""

from __future__ import annotations

import json
import os
import subprocess
import sys

from conftest import SERVER_ROOT


def _run(*args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SERVER_ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("LLM_USAGE_PATH", None)
    env.pop("LLM_LEDGER_EPOCH_PATH", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "app.ledger_admin", *args],
        cwd=SERVER_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )


def _paths(tmp_path):
    return tmp_path / "ledger.sqlite3", tmp_path / "epoch" / "ledger-epoch.json"


def test_init_requires_explicit_confirmation(tmp_path):
    ledger, epoch = _paths(tmp_path)
    result = _run("init", "--path", str(ledger), "--epoch-path", str(epoch), "--limit", "5", "--per-session", "2")
    assert result.returncode == 2
    assert "require --confirm" in result.stderr
    assert not ledger.exists() and not epoch.exists()


def test_init_verify_reset_cycle(tmp_path):
    ledger, epoch = _paths(tmp_path)
    base = ["--path", str(ledger), "--epoch-path", str(epoch)]

    init = _run("init", *base, "--limit", "5", "--per-session", "2", "--confirm")
    assert init.returncode == 0, init.stderr
    created = json.loads(init.stdout)
    assert created["status"] == "created"
    assert created["global_limit"] == 5 and created["session_limit"] == 2
    assert created["global_used"] == 0
    assert ledger.exists() and epoch.exists()
    fingerprint = created["epoch_fingerprint"]

    again = _run("init", *base, "--limit", "5", "--per-session", "2", "--confirm")
    assert again.returncode == 2
    assert "already exists" in again.stderr

    verify = _run("verify", *base, "--limit", "5", "--per-session", "2")
    assert verify.returncode == 0, verify.stderr
    report = json.loads(verify.stdout)
    assert report["status"] == "ready"
    assert report["global_used"] == 0

    refused = _run("reset", *base, "--limit", "5", "--per-session", "2")
    assert refused.returncode == 2
    assert json.loads(_run("verify", *base, "--limit", "5", "--per-session", "2").stdout)[
        "epoch_fingerprint"
    ] == fingerprint

    reset = _run("reset", *base, "--limit", "7", "--per-session", "3", "--confirm")
    assert reset.returncode == 0, reset.stderr
    rotated = json.loads(reset.stdout)
    assert rotated["status"] == "rotated"
    assert rotated["epoch_fingerprint"] != fingerprint
    assert rotated["global_limit"] == 7 and rotated["session_limit"] == 3
    assert rotated["global_used"] == 0


def test_verify_reports_a_corrupt_ledger_without_recreating(tmp_path):
    ledger, epoch = _paths(tmp_path)
    base = ["--path", str(ledger), "--epoch-path", str(epoch), "--limit", "5", "--per-session", "2"]
    assert _run("init", *base, "--confirm").returncode == 0
    ledger.write_bytes(b"this is not a sqlite database" * 10)

    verify = _run("verify", *base)
    assert verify.returncode == 3
    report = json.loads(verify.stdout)
    assert report["status"] == "unusable"
    assert report["reason"] in {"ledger_corrupt", "ledger_unreadable"}
    # verify must never silently recreate or reset quota.
    assert ledger.stat().st_size > 0


def test_verify_reports_missing_epoch(tmp_path):
    ledger, epoch = _paths(tmp_path)
    base = ["--path", str(ledger), "--epoch-path", str(epoch), "--limit", "5", "--per-session", "2"]
    assert _run("init", *base, "--confirm").returncode == 0
    epoch.unlink()

    verify = _run("verify", *base)
    assert verify.returncode == 3
    report = json.loads(verify.stdout)
    assert report["reason"] == "epoch_missing"
    assert not epoch.exists()


def test_full_app_refuses_live_after_ledger_delete(tmp_path):
    """ledger_admin cannot be used to silently re-grant quota mid-generation."""

    ledger, epoch = _paths(tmp_path)
    base = ["--path", str(ledger), "--epoch-path", str(epoch), "--limit", "5", "--per-session", "2"]
    assert _run("init", *base, "--confirm").returncode == 0

    env = {
        "PYTHONPATH": str(SERVER_ROOT),
        "APP_ENTRY_MODE": "live",
        "MODEL_PROVIDER": "llm",
        "LLM_BASE_URL": "https://llm.invalid/v1",
        "LLM_MODEL": "fake-model",
        "LLM_API_KEY": "test-key-not-a-real-secret",
        "LLM_USAGE_PATH": str(ledger),
        "LLM_LEDGER_EPOCH_PATH": str(epoch),
        "LLM_REQUEST_LIMIT": "5",
        "LLM_REQUEST_LIMIT_PER_SESSION": "2",
    }
    ok = _run("verify", *base)
    assert ok.returncode == 0
    epoch.unlink()
    refused = subprocess.run(
        [sys.executable, "-c", "from app.entry import app"],
        cwd=SERVER_ROOT,
        env={**os.environ.copy(), **env},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    assert refused.returncode != 0
    assert "budget ledger unusable" in (refused.stderr + refused.stdout)
