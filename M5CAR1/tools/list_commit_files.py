"""Produce the exact file list proposed for the (not yet authorized) git commit.

Nothing is staged or committed here. The list exists so the reviewer can accept
or reject a concrete set of paths instead of ``git add -A``.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SERVER_INCLUDE_DIRS = ("app", "tests", "tools")
SERVER_INCLUDE_FILES = (
    "requirements.txt",
    "requirements-dev.txt",
    ".env.example",
    ".gitignore",
    ".dockerignore",
    "Dockerfile",
    "Dockerfile.modelscope",
    "docker-compose.yml",
    "pytest.ini",
    "README.md",
    "DEPLOYMENT.md",
    "API_CONTRACT.md",
    "UnityIntegrationGuide.md",
    "HandoffToCodex_M4B.md",
)
EXCLUDE_PARTS = {".venv", "__pycache__", ".pytest_cache", ".local", "htmlcov"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".sqlite3", ".sqlite", ".db"}

M5CAR1_KEEP = ("reports", "tools", "e2e", "deploy", "evidence")
M5CAR1_EXCLUDE_SUFFIXES = {".pyc", ".sqlite3", ".sqlite", ".db"}
M5CAR1_EXCLUDE_PARTS = {"__pycache__", "state", "chrome-profile", "profile-virtual_60s", "profile-virtual_120s"}


def _walk(base: Path, exclude_parts: set[str], exclude_suffixes: set[str]):
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        if any(part in exclude_parts for part in path.parts):
            continue
        if path.suffix.lower() in exclude_suffixes:
            continue
        yield path


def main() -> int:
    tracked: list[str] = []
    for name in SERVER_INCLUDE_DIRS:
        base = ROOT / "Server" / name
        if base.exists():
            tracked += [str(p.relative_to(ROOT)).replace("\\", "/") for p in _walk(base, EXCLUDE_PARTS, EXCLUDE_SUFFIXES)]
    for name in SERVER_INCLUDE_FILES:
        path = ROOT / "Server" / name
        if path.exists():
            tracked.append(f"Server/{name}")
    for name in M5CAR1_KEEP:
        base = ROOT / "M5CAR1" / name
        if base.exists():
            tracked += [
                str(p.relative_to(ROOT)).replace("\\", "/")
                for p in _walk(base, M5CAR1_EXCLUDE_PARTS, M5CAR1_EXCLUDE_SUFFIXES)
            ]

    excluded: list[str] = []
    for pattern, reason in [
        ("Server/.venv/**", "virtualenv"),
        ("Server/.local/**", "local state dir (ledger, epoch)"),
        ("M5CAR1/evidence/e2e/state/*.sqlite3", "private ledgers"),
        ("M5CAR1/evidence/browser/*profile*/**", "browser profile"),
        ("*.zip", "delivery archives (untracked by design)"),
        ("Builds/M5CAR1/**", "assembled candidate output"),
        ("Server/pytest-verbose.txt", "generated log"),
    ]:
        excluded.append(f"{pattern}  # {reason}")

    out = ROOT / "M5CAR1" / "evidence" / "git" / "commit_file_list.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "# Proposed commit file list (generated, NOT applied)\n"
        "# command: git add -- <paths listed below>\n"
        f"# files: {len(tracked)}\n\n" + "\n".join(tracked) + "\n\n"
        "# deliberately NOT added\n" + "\n".join(excluded) + "\n",
        encoding="utf-8",
    )
    print(f"files: {len(tracked)} -> {out}")
    both = [p for p in tracked if "/" not in p]
    print("root-level entries:", both)
    return 0


if __name__ == "__main__":
    sys.exit(main())
