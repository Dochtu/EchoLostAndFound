"""Secret / sensitive-file scan for the M5-C-A delivery.

Read-only. Scans the files that the M5-C-A delivery proposes to commit (source,
tests, docs, deployment assets) plus the current Git index, and reports any
credential-shaped strings.  It never prints a full secret: hits are redacted.

Run:  python M5CA/scan_secrets.py [--out M5CA/evidence/git/secret-scan.json]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCAN_ROOTS = ["Server/app", "Server/tests", "Server/tools", "M5CA", "Server/Docs"]
SCAN_FILES = [
    "Server/.env.example",
    "Server/Dockerfile",
    "Server/README.md",
    "Server/DEPLOYMENT.md",
    "Server/API_CONTRACT.md",
    "Server/requirements.txt",
    "Server/requirements-dev.txt",
    ".gitignore",
]

PATTERNS = [
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}")),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("bearer_literal", re.compile(r"Bearer\s+[A-Za-z0-9._\-]{24,}")),
    ("assigned_secret", re.compile(
        r"(?i)(?:api[_-]?key|secret|password|token)\s*[=:]\s*[\"']([A-Za-z0-9._\-]{16,})[\"']"
    )),
]

# Values that are obviously placeholders, not credentials.
ALLOWLIST = {'sk-live-0123456789abcdef', 'local-secret-token'}

PLACEHOLDER = re.compile(
    r"(?i)(replace|placeholder|example|dummy|fake|test|your-|xxx|todo|none|not-a-real)"
)

SENSITIVE_NAME = re.compile(
    r"(?i)(\.env$|\.env\.(?!example|template)|\.sqlite3|\.sqlite3-|edge-profile|"
    r"credentials|secrets\.local|id_rsa|\.pem$|\.pfx$)"
)


def redact(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


def iter_files() -> list[Path]:
    files: list[Path] = []
    for rel in SCAN_ROOTS:
        base = ROOT / rel
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            parts = set(path.parts)
            if parts & {".venv", "__pycache__", "node_modules", "build", "dist"}:
                continue
            if path.suffix in {".pyc", ".png", ".jpg", ".jpeg", ".webp", ".zip", ".gz"}:
                continue
            if "evidence" in path.parts:
                continue
            files.append(path)
    for rel in SCAN_FILES:
        path = ROOT / rel
        if path.exists():
            files.append(path)
    return sorted(set(files))


def scan_text(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    hits: list[dict] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        if "PLACEHOLDER" in line or line.lstrip().startswith("#"):
            continue
        for name, pattern in PATTERNS:
            for match in pattern.finditer(line):
                value = match.group(1) if match.groups() else match.group(0)
                if value in ALLOWLIST or PLACEHOLDER.search(value):
                    continue
                hits.append(
                    {
                        "file": str(path.relative_to(ROOT)),
                        "line": line_no,
                        "pattern": name,
                        "redacted": redact(value),
                    }
                )
    return hits


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="M5CA/evidence/git/secret-scan.json")
    args = parser.parse_args()

    files = iter_files()
    hits: list[dict] = []
    for path in files:
        hits.extend(scan_text(path))

    tracked = [line for line in git("ls-files").splitlines() if line]
    sensitive_tracked = [name for name in tracked if SENSITIVE_NAME.search(name)]

    payload = {
        "scanned_files": len(files),
        "scanned_roots": SCAN_ROOTS + SCAN_FILES,
        "credential_hits": hits,
        "tracked_files": len(tracked),
        "sensitive_tracked_files": sensitive_tracked,
        "index_clean": not hits and not sensitive_tracked,
        "notes": [
            "Scan is heuristic; .gitignore cannot detect a secret embedded in a normal file.",
            "Fake/test keys (test-key-not-a-real-secret) are placeholders and are excluded.",
        ],
    }
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("scanned_files", "index_clean", "sensitive_tracked_files")}, ensure_ascii=False))
    return 0 if payload["index_clean"] else 1


if __name__ == "__main__":
    sys.exit(main())

