"""Assemble the M5-C-A-R1 delivery packages.

Design rules (mirrors the M5CA audit finding about ``build_candidate.ps1``):
* never delete an existing directory or archive -- refuse instead;
* hash every packed file into ``MANIFEST.txt``;
* exclude private state (SQLite ledgers, browser profiles, caches, venvs).

Run with the workspace venv:
    Server\\.venv\\Scripts\\python.exe M5CAR1\\tools\\build_packages.py
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "Server"
M5CAR1 = ROOT / "M5CAR1"

SERVER_SOURCE_EXCLUDE_DIRS = {
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".local",
    "htmlcov",
}
SERVER_SOURCE_EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".sqlite3", ".sqlite", ".db"}

DEPLOY_FILES = [
    "requirements.txt",
    "Dockerfile",
    "Dockerfile.modelscope",
    "docker-compose.yml",
    ".dockerignore",
    ".env.example",
    "DEPLOYMENT.md",
    "README.md",
    "API_CONTRACT.md",
]

REPORTS_EXCLUDE_DIRS = {
    "__pycache__",
    "state",
    "packages",
    "chrome-profile",
    "profile-virtual_60s",
    "profile-virtual_120s",
}
REPORTS_EXCLUDE_SUFFIXES = {".sqlite3", ".pyc"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter(base: Path, exclude_dirs: set[str], exclude_suffixes: set[str]):
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        if any(part in exclude_dirs for part in path.parts):
            continue
        if path.suffix.lower() in exclude_suffixes:
            continue
        yield path


def _refuse_if_exists(*paths: Path) -> None:
    for path in paths:
        if path.exists():
            raise SystemExit(f"refusing to overwrite existing artifact: {path}")


def build_zip(target: Path, entries: list[tuple[Path, str]]) -> dict:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source, arcname in entries:
            archive.write(source, arcname)
    return {"path": str(target.relative_to(ROOT)), "files": len(entries), "bytes": target.stat().st_size, "sha256": sha256(target)}


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    server_zip = ROOT / "ServerSource.zip"
    deploy_zip = ROOT / "DeploymentCandidate.zip"
    reports_zip = ROOT / "M5CAR1_Reports.zip"
    candidate_zip = ROOT / f"M5CAR1_LocalWebGLCandidate_{stamp}.zip"
    _refuse_if_exists(server_zip, deploy_zip, reports_zip, candidate_zip)

    server_entries: list[tuple[Path, str]] = []
    for path in _iter(SERVER, SERVER_SOURCE_EXCLUDE_DIRS, SERVER_SOURCE_EXCLUDE_SUFFIXES):
        rel = path.relative_to(SERVER)
        if rel.parts[0] == "app" and "content" not in rel.parts and rel.suffix != ".py":
            continue
        server_entries.append((path, f"Server/{rel.as_posix()}"))
    source_manifest = {f"Server/{p.relative_to(SERVER).as_posix()}": sha256(p) for p, _ in server_entries}
    (M5CAR1 / "evidence" / "git" / "source_sha256.txt").parent.mkdir(parents=True, exist_ok=True)
    (M5CAR1 / "evidence" / "git" / "source_sha256.txt").write_text(
        "\n".join(f"{digest}  {name}" for name, digest in sorted(source_manifest.items())) + "\n",
        encoding="utf-8",
    )
    server_result = build_zip(server_zip, server_entries)

    deploy_entries: list[tuple[Path, str]] = []
    for path in _iter(SERVER / "app", {"__pycache__"}, {".pyc"}):
        deploy_entries.append((path, f"app/{path.relative_to(SERVER / 'app').as_posix()}"))
    for name in DEPLOY_FILES:
        path = SERVER / name
        if path.exists():
            deploy_entries.append((path, name))
    deploy_entries.append((M5CAR1 / "deploy" / "DEPLOY_R1.md", "DEPLOY_R1.md"))
    deploy_result = build_zip(deploy_zip, deploy_entries)

    reports_entries: list[tuple[Path, str]] = []
    manifest_lines: list[str] = []
    for path in _iter(M5CAR1, REPORTS_EXCLUDE_DIRS, REPORTS_EXCLUDE_SUFFIXES):
        rel = path.relative_to(M5CAR1)
        if rel.parts[0] == "local_candidate":
            continue
        if rel.as_posix() in ("MANIFEST.txt", "evidence/packages.json"):
            continue
        reports_entries.append((path, f"M5CAR1/{rel.as_posix()}"))
        manifest_lines.append(f"{sha256(path)}  {rel.as_posix()}")
    (M5CAR1 / "MANIFEST.txt").write_text(
        "# M5-C-A-R1 report package manifest\n"
        f"# generated: {datetime.now().astimezone().isoformat(timespec='seconds')}\n"
        f"# files: {len(manifest_lines)}\n"
        "# local_candidate/ and private state are packed separately or excluded\n\n"
        + "\n".join(sorted(manifest_lines))
        + "\n",
        encoding="utf-8",
    )
    reports_entries.append((M5CAR1 / "MANIFEST.txt", "M5CAR1/MANIFEST.txt"))
    reports_result = build_zip(reports_zip, reports_entries)

    candidate_entries = [
        (path, path.relative_to(M5CAR1 / "local_candidate" / "webgl").as_posix())
        for path in _iter(M5CAR1 / "local_candidate" / "webgl", set(), set())
    ]
    candidate_result = build_zip(candidate_zip, candidate_entries)

    summary = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "server_source": server_result,
        "deployment_candidate": deploy_result,
        "reports": reports_result,
        "local_webgl_candidate": candidate_result,
        "excluded_private_state": sorted(
            str(p.relative_to(ROOT)).replace("\\", "/")
            for p in (M5CAR1 / "evidence" / "e2e" / "state").glob("*")
            if p.is_file()
        ),
    }
    (M5CAR1 / "evidence" / "packages.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / f"M5CAR1_LocalWebGLCandidate_{stamp}.sha256").write_text(
        f"{candidate_result['sha256']}  {candidate_zip.name}\n", encoding="utf-8"
    )
    (ROOT / "M5CAR1_Package_SHA256.txt").write_text(
        "\n".join(
            f"{item['sha256']}  {item['path']}"
            for item in (server_result, deploy_result, reports_result, candidate_result)
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
