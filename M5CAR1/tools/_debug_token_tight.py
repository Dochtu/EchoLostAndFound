"""Ad-hoc debug: start the token-tight configuration and print the health body."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "Server"
PY = SERVER / ".venv" / "Scripts" / "python.exe"
STATE = ROOT / "M5CAR1" / "evidence" / "e2e" / "state"

ledger = STATE / "dbg-tokens.sqlite3"
epoch = STATE / "dbg-tokens-epoch" / "ledger-epoch.json"
for path in (ledger, epoch):
    if path.exists():
        path.unlink()

subprocess.run(
    [
        str(PY), "-m", "app.ledger_admin", "init", "--confirm",
        "--path", str(ledger), "--epoch-path", str(epoch),
        "--limit", "20", "--per-session", "10", "--token-limit", "1000",
    ],
    cwd=str(SERVER), check=True, capture_output=True, text=True,
)

env = {k: v for k, v in os.environ.items() if not k.startswith("LLM_")}
env.update({
    "PYTHONUNBUFFERED": "1",
    "PYTHONIOENCODING": "utf-8",
    "APP_ENTRY_MODE": "live",
    "MODEL_PROVIDER": "llm",
    "LLM_BASE_URL": "http://127.0.0.1:19100/v1",
    "LLM_MODEL": "fake-model",
    "LLM_API_KEY": "test-key-not-a-real-secret",
    "LLM_REQUEST_LIMIT": "20",
    "LLM_REQUEST_LIMIT_PER_SESSION": "10",
    "LLM_TOKEN_LIMIT": "1000",
    "LLM_CONTEXT_MAX_TOKENS": "512",
    "LLM_MAX_OUTPUT_TOKENS": "64",
    "LLM_SYSTEM_PROMPT_MAX_TOKENS": "512",
    "LLM_EVIDENCE_CONTEXT_MAX_TOKENS": "256",
    "LLM_INPUT_MAX_CHARS": "200",
    "LLM_USAGE_PATH": str(ledger),
    "LLM_LEDGER_EPOCH_PATH": str(epoch),
    "PORT": "18290",
})
log = open(STATE / "dbg-tokens.log", "w", encoding="utf-8")
proc = subprocess.Popen(
    [str(PY), "-m", "app.server_entry"], cwd=str(SERVER), env=env,
    stdout=log, stderr=subprocess.STDOUT,
)
try:
    for _ in range(120):
        try:
            with urllib.request.urlopen("http://127.0.0.1:18290/api/v1/health", timeout=2) as r:
                body = json.loads(r.read().decode("utf-8"))
            print(json.dumps(body["data"], ensure_ascii=False, indent=2))
            break
        except Exception:
            time.sleep(0.25)
    else:
        print("no health")
finally:
    proc.terminate()
    proc.wait(timeout=15)
    log.close()
    print((STATE / "dbg-tokens.log").read_text(encoding="utf-8")[-2000:])
