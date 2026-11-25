"""M5-C-A-R2 secret scan.

The M5-C-A scanner is deliberately *not* reused: this round extends the pattern
set to ModelScope access tokens and to the wider deployment surface added in
R1.  The scan is a heuristic, not a proof -- see M5CAR2_SecurityReview.md for
the residual-risk statement.

Run with:
    Server\\.venv\\Scripts\\python.exe M5CAR2\\tools\\scan_secrets.py
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]

TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".cfg",
    ".env",
    ".example",
    ".ps1",
    ".sh",
    ".bat",
    ".html",
    ".js",
    ".css",
    ".csv",
}

SKIP_DIR_NAMES = {
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".git",
    "node_modules",
    "Library",
    "Temp",
    "obj",
    "Logs",
}

SENSITIVE_SUFFIXES = {".sqlite3", ".sqlite", ".db", ".pem", ".pfx", ".p12", ".key"}


@dataclass(frozen=True)
class Pattern:
    name: str
    regex: re.Pattern[str]
    note: str = ""


# ModelScope tokens: the platform never documented a format, so both a strict
# UUID-shaped rule and a loose `ms-` rule are applied.  Flagged as heuristic in
# the security review; the loose rule is the one that matters.
PATTERNS: tuple[Pattern, ...] = (
    Pattern("modelscope_token_strict", re.compile(r"\bms-[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "heuristic"),
    Pattern("modelscope_token_loose", re.compile(r"\bms-[A-Za-z0-9_-]{20,}\b"), "heuristic"),
    Pattern("openai_style_key", re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}")),
    Pattern("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    Pattern("bearer_literal", re.compile(r"Bearer\s+[A-Za-z0-9._\-]{24,}")),
    Pattern("jwt_like", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    Pattern("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    Pattern(
        "assigned_secret",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret|token|password|passwd|access[_-]?key)\b\s*[:=]\s*[\"']?([A-Za-z0-9_\-]{16,})"
        ),
    ),
)

ALLOWLIST = {
    "sk-live-0123456789abcdef",
    "test-key-not-a-real-secret",
    "local-secret-token",
    "not-a-real-secret",
    "changeme-changeme-changeme",
}

ALLOWLIST_FRAGMENTS = (
    "${",
    "<your",
    "<token>",
    "example.invalid",
    "xxxxxxxx",
    "placeholder",
)


@dataclass
class ScanResult:
    scanned_files: list[str] = field(default_factory=list)
    credential_hits: list[dict] = field(default_factory=list)
    sensitive_files: list[str] = field(default_factory=list)
    skipped_reasons: dict[str, int] = field(default_factory=dict)


def _iter_files(root: Path, extra_roots: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for base in [root, *extra_roots]:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            files.append(path)
    return files


def _is_allowlisted(value: str) -> bool:
    if value in ALLOWLIST:
        return True
    lowered = value.lower()
    return any(fragment in lowered for fragment in ALLOWLIST_FRAGMENTS)


def _redact(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"


def scan(paths: Iterable[Path]) -> ScanResult:
    result = ScanResult()
    for path in paths:
        rel = path.relative_to(REPO_ROOT).as_posix()
        if path.suffix.lower() in SENSITIVE_SUFFIXES or path.name == ".env":
            result.sensitive_files.append(rel)
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {".env.example", ".gitignore"}:
            result.skipped_reasons["not_text"] = result.skipped_reasons.get("not_text", 0) + 1
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            result.skipped_reasons["unreadable"] = result.skipped_reasons.get("unreadable", 0) + 1
            continue
        result.scanned_files.append(rel)
        for pattern in PATTERNS:
            for match in pattern.regex.finditer(text):
                candidate = match.group(match.lastindex or 0)
                if _is_allowlisted(candidate):
                    continue
                line = text.count("\n", 0, match.start()) + 1
                result.credential_hits.append(
                    {
                        "file": rel,
                        "line": line,
                        "pattern": pattern.name,
                        "note": pattern.note,
                        "value": _redact(candidate),
                    }
                )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(REPO_ROOT / "M5CAR2" / "evidence" / "security" / "secret_scan.json"))
    args = parser.parse_args()

    extra_roots = [REPO_ROOT / "M5CAR1", REPO_ROOT / "M5CAR2", REPO_ROOT / "Deploy"]
    files = _iter_files(REPO_ROOT / "Server", extra_roots)
    # Root-level configuration files are part of the tracked surface.
    for name in (".gitignore", "AGENTS.md", "README.md"):
        candidate = REPO_ROOT / name
        if candidate.exists():
            files.append(candidate)

    unique = sorted({p for p in files})
    result = scan(unique)
    per_root: dict[str, int] = {}
    for path in unique:
        try:
            rel = path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            rel = str(path)
        root = rel.split("/", 1)[0] if "/" in rel else "(root files)"
        per_root[root] = per_root.get(root, 0) + 1
    payload = {
        "generated_at": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
        "scanner": "M5CAR2/tools/scan_secrets_r2.py",
        "roots": ["Server", "M5CAR1", "M5CAR2", "Deploy", "root config files"],
        "files_considered": len(unique),
        "files_considered_per_root": per_root,
        "scanned_files": len(result.scanned_files),
        "scanned_file_list": result.scanned_files,
        "credential_hit_count": len(result.credential_hits),
        "credential_hits": result.credential_hits,
        "sensitive_files_present": result.sensitive_files,
        "skipped": result.skipped_reasons,
        "allowlist": sorted(ALLOWLIST),
        "patterns": [p.name for p in PATTERNS],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"files_considered={len(unique)} scanned={len(result.scanned_files)} hits={len(result.credential_hits)}")
    for hit in result.credential_hits:
        print(f"  {hit['file']}:{hit['line']} {hit['pattern']} {hit['value']}")
    if result.sensitive_files:
        print("sensitive files present:")
        for name in result.sensitive_files:
            print("  " + name)
    return 0 if not result.credential_hits else 1


if __name__ == "__main__":
    raise SystemExit(main())
