"""Produce the exact ``git add --`` path list for the M5-C-A-R2 local commit.

Policy (decided in this round, recorded in M5CAR2_Git_Report.md):
* keep every path of the reviewed R1 list (``M5CAR1/evidence/git/commit_file_list.txt``)
  provided it still exists;
* add ``M5CAR2/{reports,tools,e2e,deploy,evidence}/**`` and
  ``M5CAR2/packages/**`` minus archives and private state;
* add the root ``.gitignore`` hardening patch;
* never add Unity project changes, ``Deploy/``, ``M6C_Work/``, ``Builds/``,
  root archives, SQLite ledgers, browser profiles, venvs or caches.

Run (dry run only, it never stages anything itself):
    Server\\.venv\\Scripts\\python.exe M5CAR2\\tools\\list_commit_files_r2.py
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
R1_LIST = ROOT / "M5CAR1" / "evidence" / "git" / "commit_file_list.txt"
OUT = ROOT / "M5CAR2" / "evidence" / "git" / "commit_file_list.txt"

EXCLUDE_DIR_PARTS = {
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".local",
    "htmlcov",
    "state",
    "node_modules",
}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".sqlite3", ".sqlite", ".db", ".zip", ".7z"}
EXCLUDE_NAMES = {"pytest-verbose.txt", ".env", ".env.local"}


def included(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDE_DIR_PARTS for part in rel.parts):
        return False
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return False
    if path.name in EXCLUDE_NAMES:
        return False
    return True


def main() -> int:
    r1_paths = [
        line.strip()
        for line in R1_LIST.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#") and "  #" not in line
    ]

    missing = [p for p in r1_paths if not (ROOT / p).exists()]
    kept = [p for p in r1_paths if (ROOT / p).exists()]

    additions: list[str] = []
    for sub in ("reports", "tools", "e2e", "deploy", "evidence", "packages"):
        base = ROOT / "M5CAR2" / sub
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and included(path):
                additions.append(path.relative_to(ROOT).as_posix())

    additions.append(".gitignore")

    paths = sorted(set(kept) | set(additions))
    conflicts = [p for p in paths if not (ROOT / p).exists()]

    # Drop anything the repository would refuse to add (e.g. *.log from .gitignore).
    check = subprocess.run(
        ["git", "-C", str(ROOT), "check-ignore", "--stdin"],
        input="\n".join(paths) + "\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    ignored = {line.strip() for line in check.stdout.splitlines() if line.strip()}
    if ignored:
        print(f"ignored paths dropped: {len(ignored)}")
        for path in sorted(ignored):
            print(f"  IGNORED {path}")
    paths = [p for p in paths if p not in ignored]

    header = [
        "# M5-C-A-R2 local commit file list (generated, reviewed before use)",
        "# command: git add -- <paths listed below>",
        f"# files: {len(paths)}",
        "# note: this list is not the commit record; see evidence/git/post-commit.txt",
        "",
    ]
    trailer = [
        "",
        "# deliberately NOT added",
        "Server/.venv/**  # virtualenv",
        "Server/.local/**  # local ledger/epoch state",
        "Server/.env  # never present; real secrets only via process env",
        "M5CAR1/evidence/e2e/state/**  # private SQLite ledgers",
        "M5CAR2/evidence/e2e/state/**  # private SQLite ledgers",
        "M5CAR2/packages/*.zip  # archives are untracked by design",
        "M5CAR2/local_candidate/**  # WebGL candidate stays out of Git",
        "Deploy/**  # Codex M6-C deployment context, not this round's artifact",
        "M6C_Work/**  # Codex M6-C workspace",
        "Builds/**  # build outputs",
        "EchoLostAndFound_WebGL/**  # Codex-managed Unity changes (uncommitted on purpose)",
        "Packages/**, ProjectSettings/**  # Codex-managed Unity changes",
        "root *.zip, *.sha256  # local delivery archives/manifests",
        "Server/pytest-verbose.txt  # generated log",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(header + paths + trailer) + "\n", encoding="utf-8")

    print(f"r1 listed: {len(r1_paths)}  kept: {len(kept)}  missing: {len(missing)}")
    for path in missing:
        print(f"  MISSING {path}")
    print(f"r2 additions: {len(additions)}  total: {len(paths)}  nonexistent: {len(conflicts)}")
    for path in conflicts:
        print(f"  MISSING {path}")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0 if not conflicts else 1


if __name__ == "__main__":
    raise SystemExit(main())
