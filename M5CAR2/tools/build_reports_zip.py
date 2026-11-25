"""Package the M5-C-A-R2 reports and evidence into M5CAR2_Reports.zip.

Excluded on purpose: private SQLite state, package archives, and
``evidence/packages.json`` (it records this zip's own hash, so it cannot be
inside the zip).  Report-referenced files are all included.

Run:
    Server\\.venv\\Scripts\\python.exe M5CAR2\\tools\\build_reports_zip.py
"""

from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
M5CAR2 = ROOT / "M5CAR2"
TARGET = ROOT / "M5CAR2_Reports.zip"

EXCLUDE_DIRS = {"state", "__pycache__", ".pytest_cache"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".sqlite3", ".sqlite", ".db", ".zip"}
EXCLUDE_NAMES = {"packages.json"}


def main() -> int:
    if TARGET.exists() and "--force" not in sys.argv[1:]:
        raise SystemExit(f"refusing to overwrite {TARGET} (use --force)")

    entries: list[tuple[Path, str]] = []
    for base, prefix in ((M5CAR2 / "reports", "reports"), (M5CAR2 / "evidence", "evidence"),
                         (M5CAR2 / "deploy", "deploy"), (M5CAR2 / "tools", "tools")):
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(base)
            if any(part in EXCLUDE_DIRS for part in rel.parts):
                continue
            if path.suffix.lower() in EXCLUDE_SUFFIXES or path.name in EXCLUDE_NAMES:
                continue
            entries.append((path, f"{prefix}/{rel.as_posix()}"))

    with zipfile.ZipFile(TARGET, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source, arcname in entries:
            archive.write(source, arcname)

    digest = hashlib.sha256(TARGET.read_bytes()).hexdigest()
    print(f"files={len(entries)} bytes={TARGET.stat().st_size}")
    print(f"sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
