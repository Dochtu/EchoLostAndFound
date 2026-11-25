"""Write the SHA256 manifest for the local WebGL candidate build.

Artifact: M5CAR1/evidence/browser/build_manifest.sha256

Covers the entry page plus every file under Build/ (the runtime payload).
Also proves the copy under local_candidate/webgl is byte-identical to the
original build directory it was copied from.

Run with the project's venv Python:
    Server\\.venv\\Scripts\\python.exe M5CAR1\\tools\\make_build_manifest.py
"""

from __future__ import annotations

import hashlib
import pathlib

ROOT = pathlib.Path(r"G:\projects\EchoLostAndFound\M5CAR1\local_candidate\webgl")
SOURCE = pathlib.Path(r"G:\projects\EchoLostAndFound\Builds\M4C-Closeout-Player")
OUT = pathlib.Path(
    r"G:\projects\EchoLostAndFound\M5CAR1\evidence\browser\build_manifest.sha256"
)


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    targets = [ROOT / "index.html"]
    targets.extend(sorted((ROOT / "Build").glob("*")))
    lines = []
    for path in targets:
        if not path.is_file():
            print(f"MISSING {path}")
            return 2
        rel = path.relative_to(ROOT).as_posix()
        lines.append(f"{sha256_file(path)}  {rel}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT} ({len(lines)} entries)")
    print(OUT.read_text(encoding="utf-8"))

    mismatches = 0
    total = 0
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        total += 1
        rel = path.relative_to(ROOT)
        original = SOURCE / rel
        if not original.is_file() or sha256_file(path) != sha256_file(original):
            mismatches += 1
            print(f"MISMATCH {rel}")
    print(f"copy_vs_source_files={total} mismatches={mismatches}")
    return 0 if mismatches == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
