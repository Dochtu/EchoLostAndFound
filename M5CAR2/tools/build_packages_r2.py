"""Assemble the M5-C-A-R2 delivery packages.

Rules:
* never overwrite an existing artifact -- refuse and report instead;
* hash every packed file into the package manifests;
* exclude private state (SQLite ledgers, browser profiles, caches, venvs);
* the WebGL candidate is *verified*, never rebuilt: rebuilding the client is
  M6-C's write scope and is forbidden to this round.

Run:
    Server\\.venv\\Scripts\\python.exe M5CAR2\\tools\\build_packages_r2.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "Server"
M5CAR2 = ROOT / "M5CAR2"
M5CAR1 = ROOT / "M5CAR1"
PACKAGES = M5CAR2 / "packages"

SERVER_SOURCE_EXCLUDE_DIRS = {
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".local",
    "htmlcov",
}
SERVER_SOURCE_EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".sqlite3", ".sqlite", ".db", ".log"}
SERVER_SOURCE_EXCLUDE_FILES = {"pytest-verbose.txt", ".env", ".env.local", ".env.production"}

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

WEBGL_CANDIDATE_DIR = M5CAR1 / "local_candidate" / "webgl"
WEBGL_CANDIDATE_ZIP = ROOT / "M5CAR1_LocalWebGLCandidate_20261125-1400.zip"
WEBGL_CANDIDATE_ZIP_SHA256 = "0e408df23251b1e4bdc56bdb6bfd44d83e8a41c3693f86dbfa0e87b8d2ae9bb2"
WEBGL_BUILD_DIR = ROOT / "Builds" / "M4C-Closeout-Player"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_files(base: Path, exclude_dirs: set[str], exclude_suffixes: set[str]):
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        if any(part in exclude_dirs for part in path.parts):
            continue
        if path.suffix.lower() in exclude_suffixes:
            continue
        if path.name in SERVER_SOURCE_EXCLUDE_FILES:
            continue
        yield path


def refuse(path: Path) -> None:
    if path.exists():
        raise SystemExit(f"refusing to overwrite existing artifact: {path}")


def build_zip(target: Path, entries: list[tuple[Path, str]]) -> dict:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source, arcname in entries:
            archive.write(source, arcname)
    return {
        "path": str(target.relative_to(ROOT)).replace("\\", "/"),
        "files": len(entries),
        "bytes": target.stat().st_size,
        "sha256": sha256(target),
    }


def verify_webgl() -> dict:
    if not WEBGL_CANDIDATE_DIR.is_dir():
        raise SystemExit(f"missing WebGL candidate dir: {WEBGL_CANDIDATE_DIR}")
    if not WEBGL_CANDIDATE_ZIP.is_file():
        raise SystemExit(f"missing WebGL candidate zip: {WEBGL_CANDIDATE_ZIP}")

    zip_digest = sha256(WEBGL_CANDIDATE_ZIP)
    if zip_digest != WEBGL_CANDIDATE_ZIP_SHA256:
        raise SystemExit(f"WebGL candidate zip hash changed: {zip_digest}")

    files = sorted(path for path in WEBGL_CANDIDATE_DIR.rglob("*") if path.is_file())
    manifest = {path.relative_to(WEBGL_CANDIDATE_DIR).as_posix(): sha256(path) for path in files}

    with zipfile.ZipFile(WEBGL_CANDIDATE_ZIP) as archive:
        members = {name: hashlib.sha256(archive.read(name)).hexdigest() for name in archive.namelist()}

    if members != manifest:
        missing = sorted(set(manifest) - set(members))
        extra = sorted(set(members) - set(manifest))
        changed = sorted(name for name in set(manifest) & set(members) if manifest[name] != members[name])
        raise SystemExit(f"zip/dir mismatch missing={missing} extra={extra} changed={changed}")

    provenance = None
    if WEBGL_BUILD_DIR.is_dir():
        mismatches = []
        total = 0
        for name, digest in manifest.items():
            original = WEBGL_BUILD_DIR / name
            total += 1
            if not original.is_file() or sha256(original) != digest:
                mismatches.append(name)
        provenance = {
            "source_dir": str(WEBGL_BUILD_DIR.relative_to(ROOT)).replace("\\", "/"),
            "files_compared": total,
            "mismatches": mismatches,
            "byte_identical": not mismatches,
        }

    lines = [f"{digest}  {name}" for name, digest in manifest.items()]
    out = M5CAR2 / "evidence" / "browser" / "build_manifest.sha256"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    (ROOT / "M5CAR2_LocalWebGLCandidate.sha256").write_text(
        f"{zip_digest}  {WEBGL_CANDIDATE_ZIP.name}\n", encoding="utf-8"
    )

    return {
        "directory": str(WEBGL_CANDIDATE_DIR.relative_to(ROOT)).replace("\\", "/"),
        "files": len(manifest),
        "bytes": sum(path.stat().st_size for path in files),
        "zip": str(WEBGL_CANDIDATE_ZIP.relative_to(ROOT)).replace("\\", "/"),
        "zip_bytes": WEBGL_CANDIDATE_ZIP.stat().st_size,
        "zip_sha256": zip_digest,
        "zip_matches_directory": True,
        "provenance": provenance,
        "manifest": str(out.relative_to(ROOT)).replace("\\", "/"),
        "rebuilt_this_round": False,
        "note": (
            "M4C-Closeout WebGL build reused for server-integration verification; "
            "not rebuilt because Unity/M6-C is outside this round's write scope."
        ),
    }


def refresh_reports() -> int:
    """Update only the reports entry of packages.json (zips already built)."""
    server_zip = PACKAGES / "ServerSource.zip"
    deploy_zip = PACKAGES / "DeploymentCandidate.zip"
    reports_zip = ROOT / "M5CAR2_Reports.zip"
    out = M5CAR2 / "evidence" / "packages.json"
    if not (server_zip.is_file() and deploy_zip.is_file() and out.is_file()):
        raise SystemExit("refresh requires the two package zips and packages.json")
    if not reports_zip.is_file():
        raise SystemExit(f"missing reports zip: {reports_zip}")

    summary = json.loads(out.read_text(encoding="utf-8"))
    summary["generated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    summary["reports"] = {
        "path": str(reports_zip.relative_to(ROOT)).replace("\\", "/"),
        "bytes": reports_zip.stat().st_size,
        "sha256": sha256(reports_zip),
    }
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"{summary['server_source']['sha256']}  {summary['server_source']['path']}",
        f"{summary['deployment_candidate']['sha256']}  {summary['deployment_candidate']['path']}",
        f"{summary['local_webgl_candidate']['zip_sha256']}  {summary['local_webgl_candidate']['zip']}",
        f"{summary['reports']['sha256']}  {summary['reports']['path']}",
    ]
    (ROOT / "M5CAR2_Package_SHA256.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary["reports"], ensure_ascii=False))
    return 0


def main() -> int:
    if "--refresh-reports" in sys.argv[1:]:
        return refresh_reports()
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    server_zip = PACKAGES / "ServerSource.zip"
    deploy_zip = PACKAGES / "DeploymentCandidate.zip"
    reports_zip = ROOT / "M5CAR2_Reports.zip"
    refuse(server_zip)
    refuse(deploy_zip)
    refuse(reports_zip)

    server_entries: list[tuple[Path, str]] = []
    for path in iter_files(SERVER, SERVER_SOURCE_EXCLUDE_DIRS, SERVER_SOURCE_EXCLUDE_SUFFIXES):
        server_entries.append((path, f"Server/{path.relative_to(SERVER).as_posix()}"))
    source_manifest = {arc: sha256(path) for path, arc in server_entries}
    source_list = M5CAR2 / "evidence" / "git" / "source_sha256.txt"
    source_list.parent.mkdir(parents=True, exist_ok=True)
    source_list.write_text(
        "\n".join(f"{digest}  {name}" for name, digest in sorted(source_manifest.items())) + "\n",
        encoding="utf-8",
    )
    server_result = build_zip(server_zip, server_entries)

    deploy_entries: list[tuple[Path, str]] = []
    for path in iter_files(SERVER / "app", {"__pycache__"}, {".pyc", ".pyo"}):
        deploy_entries.append((path, f"app/{path.relative_to(SERVER / 'app').as_posix()}"))
    for name in DEPLOY_FILES:
        path = SERVER / name
        if path.exists():
            deploy_entries.append((path, name))
    deploy_entries.append((M5CAR2 / "deploy" / "DEPLOY_R2.md", "DEPLOY_R2.md"))
    deploy_result = build_zip(deploy_zip, deploy_entries)

    # Cross-check: every app file in the deploy zip equals the source zip entry.
    with zipfile.ZipFile(server_zip) as src, zipfile.ZipFile(deploy_zip) as dep:
        src_app = {
            name[len("Server/app/"):]: hashlib.sha256(src.read(name)).hexdigest()
            for name in src.namelist()
            if name.startswith("Server/app/")
        }
        dep_app = {
            name[len("app/"):]: hashlib.sha256(dep.read(name)).hexdigest()
            for name in dep.namelist()
            if name.startswith("app/")
        }
    if src_app != dep_app:
        raise SystemExit("deployment app/ does not match server source app/")

    webgl = verify_webgl()

    summary = {
        "generated_at": stamp,
        "round": "M5-C-A-R2",
        "server_source": server_result,
        "deployment_candidate": deploy_result,
        "local_webgl_candidate": webgl,
        "source_manifest": str(source_list.relative_to(ROOT)).replace("\\", "/"),
        "deployment_app_matches_source": True,
        "excluded_private_state": [
            "Server/.venv/**",
            "Server/.local/**",
            "M5CAR2/evidence/e2e/state/*.sqlite3",
            "M5CAR1/evidence/e2e/state/*.sqlite3",
            "browser profiles",
            "*.zip inside M5CAR2/packages (the archives themselves)",
            "Server/pytest-verbose.txt",
        ],
    }

    if reports_zip.exists():
        summary["reports"] = {
            "path": str(reports_zip.relative_to(ROOT)).replace("\\", "/"),
            "bytes": reports_zip.stat().st_size,
            "sha256": sha256(reports_zip),
        }
    else:
        summary["reports"] = None

    out = M5CAR2 / "evidence" / "packages.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    hash_lines = [
        f"{server_result['sha256']}  {server_result['path']}",
        f"{deploy_result['sha256']}  {deploy_result['path']}",
        f"{webgl['zip_sha256']}  {webgl['zip']}",
    ]
    if summary["reports"]:
        hash_lines.append(f"{summary['reports']['sha256']}  {summary['reports']['path']}")
    (ROOT / "M5CAR2_Package_SHA256.txt").write_text("\n".join(hash_lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
