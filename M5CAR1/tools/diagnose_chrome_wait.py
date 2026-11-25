"""Supplementary diagnostic for the browser smoke run.

The primary harness (``browser_smoke.py``) launches Chrome exactly once with
``--virtual-time-budget=30000``.  That flag fast-forwards timers, so the 30 s
budget can expire while Unity is still compiling its 11 MB wasm bundle -- the
screenshot then shows the loading screen at 0% and ``.data.gz`` is never
requested.

This script does NOT replace the primary evidence.  It answers two narrower
questions:

  1. can the FastAPI static site serve ``.data.gz`` correctly over plain HTTP
     (Accept-Encoding: gzip)?
  2. if Chrome is given real wall-clock time instead of a virtual-time budget,
     does the Unity runtime get further (request the data bundle)?

Run with the project's venv Python.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import httpx  # noqa: E402

import browser_smoke as bs  # noqa: E402

OUT_DIR = bs.EVIDENCE / "diagnostics"
DATA_PATH = bs.DATA_PATH


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_variant(name: str, wait_flags: list[str]) -> dict:
    profile = Path(tempfile.mkdtemp(prefix=f"echo-{name}-"))
    shot = OUT_DIR / f"{name}.png"
    stderr_log = OUT_DIR / f"{name}.stderr.log"
    stdout_log = OUT_DIR / f"{name}.stdout.log"
    args = [
        str(bs.CHROME),
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--no-first-run",
        f"--user-data-dir={profile}",
        f"--window-size={bs.WINDOW_SIZE}",
        *wait_flags,
        "--enable-logging=stderr",
        "--v=0",
        f"--screenshot={shot}",
        bs.BASE_URL,
    ]
    try:
        result = bs.run_process(
            args,
            cwd=OUT_DIR,
            env=bs.os.environ.copy(),
            stdout_path=stdout_log,
            stderr_path=stderr_log,
            timeout=180,
        )
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    result["args"] = args
    result["screenshot"] = str(shot)
    result["screenshot_bytes"] = shot.stat().st_size if shot.is_file() else 0
    result["screenshot_sha256"] = sha256(shot) if shot.is_file() else None
    result["stderr_log"] = str(stderr_log)
    return result


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report: dict = {"generated_at": bs._dt.datetime.now().astimezone().isoformat()}
    server_log = OUT_DIR / "uvicorn_diagnostic.log"
    proc = None
    handle = None
    try:
        proc, handle, meta = bs.start_server(server_log)
        with httpx.Client(trust_env=False) as client:
            health = bs.wait_for_health(client, proc, server_log)
            report["health"] = {"ok": health.get("ok"), "elapsed_s": health.get("elapsed_s")}
            if not health.get("ok"):
                report["fatal"] = "server unhealthy"
                return _finish(report, server_log, proc, handle)

            # direct HTTP proof that the data bundle is servable
            response = client.get(bs.BASE_URL + DATA_PATH.lstrip("/"), timeout=60.0)
            report["direct_http_data"] = {
                "url": bs.BASE_URL + DATA_PATH.lstrip("/"),
                "status": response.status_code,
                "content_type": response.headers.get("content-type"),
                "content_encoding": response.headers.get("content-encoding"),
                "content_length": response.headers.get("content-length"),
                "decoded_bytes": len(response.content),
                "decoded_sha256": hashlib.sha256(response.content).hexdigest(),
            }

            variants = [
                ("virtual_time_30s", ["--virtual-time-budget=30000"]),
                ("real_timeout_20s", ["--timeout=20000"]),
                ("real_timeout_45s", ["--timeout=45000"]),
            ]
            results = []
            for name, flags in variants:
                before = len(bs.parse_access_log(bs.read_text_capped(server_log))["requests"])
                entry = run_variant(name, flags)
                access = bs.parse_access_log(bs.read_text_capped(server_log))
                new_requests = access["requests"][before:]
                paths = []
                seen = set()
                for item in new_requests:
                    if item["path"] not in seen:
                        seen.add(item["path"])
                        paths.append(item["path"])
                entry["requests_during_variant"] = len(new_requests)
                entry["paths_during_variant"] = paths
                entry["requested_paths"] = paths
                entry["data_requested"] = DATA_PATH in seen
                entry["wasm_requested"] = bs.WASM_PATH in [
                    p for p in paths
                ] or any("wasm" in p for p in paths)
                entry["result"] = "captured" if entry["screenshot_bytes"] else "no-screenshot"
                if entry["screenshot_bytes"]:
                    entry["screenshot_bytes"] = entry["screenshot_bytes"]
                results.append(entry)
                print(f"\n[{name}] exit={entry['exit_code']} dur={entry['duration_s']}s "
                      f"shot={entry['screenshot_bytes']}B data={entry['data_requested']}")
                for p in paths:
                    print("   ", p)
            report["variants"] = results

            # how the loader orders its downloads
            loader = (bs.WEB_ROOT / "Build" / "M4C-Closeout-Player.loader.js").read_text(
                encoding="utf-8", errors="replace"
            )
            snippets = {}
            for token in ("dataUrl", "getContext", "instantiateStreaming", "WebGL is not supported"):
                hits = []
                for match in re.finditer(re.escape(token), loader):
                    start = max(0, match.start() - 160)
                    hits.append(loader[start: match.end() + 200].replace("\n", " ")[:360])
                    if len(hits) >= 2:
                        break
                snippets[token] = hits
            report["loader_snippets"] = snippets
        return _finish(report, server_log, proc, handle)
    except Exception as exc:  # pragma: no cover - diagnostic best effort
        report["error"] = f"{type(exc).__name__}: {exc}"
        return _finish(report, server_log, proc, handle)


def _finish(report: dict, server_log: Path, proc, handle) -> int:
    if proc is not None:
        report["server_stop"] = bs.stop_server(proc, handle)
    report["access_log"] = bs.parse_access_log(bs.read_text_capped(server_log))
    out = OUT_DIR / "chrome_wait_diagnostic.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"\nwrote {out}")
    print(json.dumps(report.get("loader_snippets", {}), indent=2)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
