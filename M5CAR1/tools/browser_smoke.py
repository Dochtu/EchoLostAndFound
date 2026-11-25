"""Local-only browser smoke harness for the EchoLostAndFound WebGL build.

What this proves (and only this):
  1. the FastAPI app under ``Server/`` starts in mock mode with ``WEB_ROOT``
     pointed at the copied build and serves ``/`` + ``/api/v1/health``;
  2. Chrome (headless) loads the page over 127.0.0.1 and requests the Unity
     runtime payload (loader / data / wasm / framework);
  3. what the DOM and screenshot artifacts look like afterwards.

What this does NOT prove: that Unity actually rendered a frame or that any
gameplay works.  There is no mouse/keyboard injection and no OCR here.

Design notes:
  * evidence, not assertions: the script always exits 0 and records failures
    as data, so a broken run still produces inspectable artifacts;
  * stdlib + httpx only; no network beyond 127.0.0.1;
  * the screenshot is *not* analysed (Pillow is unavailable); only its size
    and SHA256 are recorded and ``screenshot_non_blank`` stays null.

Run:
    G:\\projects\\EchoLostAndFound\\Server\\.venv\\Scripts\\python.exe ^
        G:\\projects\\EchoLostAndFound\\M5CAR1\\tools\\browser_smoke.py
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

import httpx

REPO = Path(r"G:\projects\EchoLostAndFound")
PYTHON = REPO / "Server" / ".venv" / "Scripts" / "python.exe"
SERVER_DIR = REPO / "Server"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
WEB_ROOT = REPO / "M5CAR1" / "local_candidate" / "webgl"
EVIDENCE = REPO / "M5CAR1" / "evidence" / "browser"

HOST = "127.0.0.1"
PORT = 18240
BASE_URL = f"http://{HOST}:{PORT}/"
HEALTH_URL = f"{BASE_URL}api/v1/health"
LOADER_PATH = "/Build/M4C-Closeout-Player.loader.js"
DATA_PATH = "/Build/M4C-Closeout-Player.data.gz"
WASM_PATH = "/Build/M4C-Closeout-Player.wasm.gz"
FRAMEWORK_PATH = "/Build/M4C-Closeout-Player.framework.js.gz"

SERVER_TIMEOUT_S = 60.0          # health wait budget, per the spec
CHROME_TIMEOUT_S = 120.0         # per Chrome invocation
VIRTUAL_TIME_BUDGET_MS = 30000
WINDOW_SIZE = "1280,800"

ERROR_LINE_RE = re.compile(r"Uncaught|SEVERE|ERROR:")
ACCESS_RE = re.compile(
    r'"(?P<method>[A-Z]+) (?P<path>[^ "]+) HTTP/[0-9.]+"\s+(?P<status>[0-9]{3})'
)
CANVAS_RE = re.compile(r'id=["\']unity-canvas["\']')

CREATIONFLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_text_capped(path: Path, limit: int = 32 * 1024 * 1024) -> str:
    try:
        with open(path, "rb") as handle:
            raw = handle.read(limit)
        return raw.decode("utf-8", errors="replace")
    except OSError:
        return ""


def port_is_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def kill_tree(pid: int) -> None:
    """Kill a Windows process tree; ignores already-dead processes."""
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            timeout=20,
            creationflags=CREATIONFLAGS,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def run_process(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    stdout_path: Path,
    stderr_path: Path,
    timeout: float,
) -> dict:
    """Run a process with file-backed output, kill the tree on timeout."""
    started = time.monotonic()
    timed_out = False
    with open(stdout_path, "wb") as out_f, open(stderr_path, "wb") as err_f:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            env=env,
            stdout=out_f,
            stderr=err_f,
            creationflags=CREATIONFLAGS,
        )
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            kill_tree(proc.pid)
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
    return {
        "exit_code": proc.returncode,
        "timed_out": timed_out,
        "duration_s": round(time.monotonic() - started, 3),
    }


# --------------------------------------------------------------------------- #
# server
# --------------------------------------------------------------------------- #
def start_server(log_path: Path) -> tuple[subprocess.Popen, object, dict]:
    env = os.environ.copy()
    env.update(
        {
            "APP_ENTRY_MODE": "mock",
            "MODEL_PROVIDER": "mock",
            "WEB_ROOT": str(WEB_ROOT),
            "LOG_LEVEL": "INFO",
            "PYTHONUNBUFFERED": "1",
        }
    )
    cmd = [
        str(PYTHON),
        "-m",
        "uvicorn",
        "app.entry:app",
        "--host",
        HOST,
        "--port",
        str(PORT),
        "--no-proxy-headers",
        "--log-level",
        "info",
    ]
    handle = open(log_path, "wb")
    proc = subprocess.Popen(
        cmd,
        cwd=str(SERVER_DIR),
        env=env,
        stdout=handle,
        stderr=subprocess.STDOUT,
        creationflags=CREATIONFLAGS,
    )
    meta = {
        "command": cmd,
        "cwd": str(SERVER_DIR),
        "env_overrides": {
            "APP_ENTRY_MODE": "mock",
            "MODEL_PROVIDER": "mock",
            "WEB_ROOT": str(WEB_ROOT),
            "LOG_LEVEL": "INFO",
            "PYTHONUNBUFFERED": "1",
        },
        "log_path": str(log_path),
    }
    return proc, handle, meta


def wait_for_health(client: httpx.Client, proc: subprocess.Popen, log_path: Path) -> dict:
    """Poll /api/v1/health until 200 or the 60 s budget expires."""
    started = time.monotonic()
    last_error = ""
    attempts = 0
    while time.monotonic() - started < SERVER_TIMEOUT_S:
        attempts += 1
        try:
            response = client.get(HEALTH_URL, timeout=5.0)
            if response.status_code == 200:
                try:
                    body = response.json()
                except ValueError:
                    body = None
                return {
                    "ok": True,
                    "status": 200,
                    "attempts": attempts,
                    "elapsed_s": round(time.monotonic() - started, 3),
                    "body": body,
                }
            last_error = f"HTTP {response.status_code}"
        except httpx.HTTPError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        if proc.poll() is not None:
            break
        time.sleep(0.5)
    return {
        "ok": False,
        "status": None,
        "attempts": attempts,
        "elapsed_s": round(time.monotonic() - started, 3),
        "last_error": last_error,
        "server_exit_code": proc.poll(),
        "log_tail": read_text_capped(log_path).splitlines()[-40:],
    }


def stop_server(proc: subprocess.Popen, handle) -> dict:
    """Terminate the server and return how it ended."""
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            kill_tree(proc.pid)
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
    try:
        handle.close()
    except Exception:  # pragma: no cover - defensive
        pass
    return {"exit_code": proc.returncode, "still_running": proc.poll() is None}


# --------------------------------------------------------------------------- #
# HTTP checks
# --------------------------------------------------------------------------- #
def check_http(
    client: httpx.Client, name: str, path: str, expected_file: Path | None = None
) -> dict:
    started = time.monotonic()
    entry: dict = {"name": name, "path": path, "url": BASE_URL + path.lstrip("/")}
    try:
        response = client.get(entry["url"], timeout=30.0)
        entry.update(
            {
                "status": response.status_code,
                "content_type": response.headers.get("content-type"),
                "content_length_header": response.headers.get("content-length"),
                "content_encoding": response.headers.get("content-encoding"),
                "bytes": len(response.content),
                "body_sha256": hashlib.sha256(response.content).hexdigest(),
                "elapsed_s": round(time.monotonic() - started, 3),
                "ok": response.status_code == 200,
            }
        )
        if expected_file is not None:
            # The body must be byte-identical to the file in WEB_ROOT: this is
            # what proves the response came from our copied build, not from
            # some other directory the app might fall back to.
            local_bytes = expected_file.read_bytes()
            entry["local_file"] = str(expected_file)
            entry["local_sha256"] = hashlib.sha256(local_bytes).hexdigest()
            entry["matches_local_file"] = entry["body_sha256"] == entry["local_sha256"]
        if path == "/":
            entry["body_contains_unity_canvas"] = bool(
                CANVAS_RE.search(response.text)
            )
            entry["title"] = _extract_title(response.text)
    except httpx.HTTPError as exc:
        entry.update(
            {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "elapsed_s": round(time.monotonic() - started, 3),
            }
        )
    return entry


def _extract_title(html: str) -> str | None:
    match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else None


# --------------------------------------------------------------------------- #
# Chrome
# --------------------------------------------------------------------------- #
def chrome_base_args(profile_dir: Path) -> list[str]:
    return [
        str(CHROME),
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--no-first-run",
        f"--user-data-dir={profile_dir}",
        f"--window-size={WINDOW_SIZE}",
        f"--virtual-time-budget={VIRTUAL_TIME_BUDGET_MS}",
        "--enable-logging=stderr",
        "--v=0",
    ]


def run_chrome_screenshot(profile_dir: Path, shot: Path) -> dict:
    args = chrome_base_args(profile_dir) + [
        f"--screenshot={shot}",
        BASE_URL,
    ]
    result = run_process(
        args,
        cwd=EVIDENCE,
        env=os.environ.copy(),
        stdout_path=EVIDENCE / "chrome_screenshot_stdout.log",
        stderr_path=EVIDENCE / "chrome_screenshot_stderr.log",
        timeout=CHROME_TIMEOUT_S,
    )
    result["args"] = args
    result["stderr_log"] = str(EVIDENCE / "chrome_screenshot_stderr.log")
    result["stdout_log"] = str(EVIDENCE / "chrome_screenshot_stdout.log")
    return result


def chrome_profile() -> Path:
    """mkdtemp instead of TemporaryDirectory: Chrome may leave locked files and
    a failing cleanup must not destroy the whole evidence run."""
    return Path(tempfile.mkdtemp(prefix="echo-chrome-"))


def run_chrome_dump_dom(profile_dir: Path, dom_path: Path) -> dict:
    args = chrome_base_args(profile_dir) + ["--dump-dom", BASE_URL]
    result = run_process(
        args,
        cwd=EVIDENCE,
        env=os.environ.copy(),
        stdout_path=dom_path,
        stderr_path=EVIDENCE / "chrome_dumpdom_stderr.log",
        timeout=CHROME_TIMEOUT_S,
    )
    result["args"] = args
    result["stdout_log"] = str(dom_path)
    result["stderr_log"] = str(EVIDENCE / "chrome_dumpdom_stderr.log")
    return result


def run_chrome_asset_probe(
    profile_dir: Path,
    server_log: Path,
    baseline: int = 0,
    timeout_s: float = 90.0,
    settle_s: float = 3.0,
) -> dict:
    """Keep a headless Chrome alive until the Unity data bundle is requested.

    ``--virtual-time-budget`` makes the screenshot/``--dump-dom`` invocations
    exit roughly one wall-clock second after load, which can abort the final
    ``.data.gz`` request before uvicorn writes its access-log line.  This probe
    has no budget and no capture: it just loads the page, polls the access log
    until the data bundle is fetched, records how long that took, then kills
    Chrome.  It performs no input injection.
    """
    args = [
        str(CHROME),
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--no-first-run",
        f"--user-data-dir={profile_dir}",
        f"--window-size={WINDOW_SIZE}",
        "--enable-logging=stderr",
        "--v=0",
        BASE_URL,
    ]
    out_log = EVIDENCE / "chrome_probe_stdout.log"
    err_log = EVIDENCE / "chrome_probe_stderr.log"
    started = time.monotonic()
    data_seen = False
    timed_out = True
    killed = False
    with open(out_log, "wb") as out_f, open(err_log, "wb") as err_f:
        proc = subprocess.Popen(
            args,
            cwd=str(EVIDENCE),
            env=os.environ.copy(),
            stdout=out_f,
            stderr=err_f,
            creationflags=CREATIONFLAGS,
        )
        try:
            while time.monotonic() - started < timeout_s:
                access = parse_access_log(read_text_capped(server_log))
                fresh = access["requests"][baseline:]
                if any(
                    r["path"] == DATA_PATH and r["status"] == 200 for r in fresh
                ):
                    data_seen = True
                    timed_out = False
                    break
                if proc.poll() is not None:
                    timed_out = False
                    break
                time.sleep(0.25)
            if data_seen and settle_s > 0:
                # Let the engine boot so its console lines land in stderr
                # before the harness kills Chrome.
                time.sleep(settle_s)
        finally:
            if proc.poll() is None:
                killed = True
                kill_tree(proc.pid)
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        pass
    stderr_text = read_text_capped(err_log)
    unsupported = sorted(
        {
            m.group(1).strip()
            for m in re.finditer(
                r"([^\n\"]+) shader is not supported on this GPU", stderr_text
            )
        }
    )
    unity = {
        "engine_version": _first_group(
            r"Initialize engine version: ([0-9A-Za-z.]+)", stderr_text
        ),
        "webgl_context_created": "Creating WebGL 2.0 context" in stderr_text,
        "webgl_renderer": _first_group(r"Renderer: ([^\n\"]+)", stderr_text),
        "player_data_loading": "Loading player data from data.unity3d" in stderr_text,
        "gpu_process_crashed": "GPU process exited unexpectedly" in stderr_text,
        "console_line_count": stderr_text.count("INFO:CONSOLE"),
        "shaders_not_supported": unsupported,
        "audio_context_blocked_count": stderr_text.count(
            "The AudioContext was not allowed to start"
        ),
        "scene_load_log_seen": "UnloadTime:" in stderr_text,
        "game_code_log_seen": "M4A font" in stderr_text,
    }
    error_count, error_samples = count_error_lines(stderr_text)
    return {
        "args": args,
        "exit_code": proc.returncode,
        "terminated_by_harness": killed,
        "elapsed_s": round(time.monotonic() - started, 3),
        "data_bundle_seen": data_seen,
        "timeout_s": timeout_s,
        "settle_s": settle_s,
        "timed_out": timed_out,
        "stdout_log": str(out_log),
        "stderr_log": str(err_log),
        "stdout_bytes": out_log.stat().st_size if out_log.exists() else 0,
        "stderr_bytes": err_log.stat().st_size if err_log.exists() else 0,
        "error_line_count": error_count,
        "error_line_samples": error_samples,
        "unity": unity,
    }


def _first_group(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text)
    return match.group(1).strip() if match else None


def count_error_lines(text: str) -> tuple[int, list[str]]:
    samples: list[str] = []
    count = 0
    for line in text.splitlines():
        if ERROR_LINE_RE.search(line):
            count += 1
            if len(samples) < 25:
                samples.append(line[:400])
    return count, samples


# --------------------------------------------------------------------------- #
# access log
# --------------------------------------------------------------------------- #
def parse_access_log(text: str) -> dict:
    requests: list[dict] = []
    for line in text.splitlines():
        match = ACCESS_RE.search(line)
        if match:
            requests.append(
                {
                    "method": match.group("method"),
                    "path": match.group("path"),
                    "status": int(match.group("status")),
                }
            )
            if len(requests) >= 500:
                break
    requested_paths: list[str] = []
    seen: set[str] = set()
    statuses: dict[str, list[int]] = {}
    for item in requests:
        statuses.setdefault(item["path"], []).append(item["status"])
        if item["path"] not in seen:
            seen.add(item["path"])
            requested_paths.append(item["path"])
    asset_paths = [
        path
        for path in requested_paths
        if path.startswith("/Build/") or path.startswith("/TemplateData/")
    ]
    return {
        "request_count": len(requests),
        "requests": requests,
        "requested_paths": requested_paths,
        "statuses": {path: codes for path, codes in statuses.items()},
        "requested_asset_paths": asset_paths,
    }


def fetched_ok(access: dict, path: str) -> bool:
    return any(code == 200 for code in access["statuses"].get(path, []))


def summarize_requests(requests: list[dict]) -> dict:
    """Per-invocation view of the access log, so each check can be attributed."""
    paths: list[str] = []
    statuses: dict[str, list[int]] = {}
    for item in requests:
        statuses.setdefault(item["path"], []).append(item["status"])
        if item["path"] not in paths:
            paths.append(item["path"])
    return {
        "request_count": len(requests),
        "paths": paths,
        "statuses": statuses,
        "asset_paths": [
            path
            for path in paths
            if path.startswith("/Build/") or path.startswith("/TemplateData/")
        ],
    }


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def build_report() -> dict:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "generated_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "harness": str(Path(__file__).resolve()),
        "url": BASE_URL,
        "web_root": str(WEB_ROOT),
        "notes": [],
        "http_checks": [],
        "access_log": {"requests": [], "requested_paths": [], "requested_asset_paths": []},
        "verified": {
            "page_served": False,
            "loader_fetched": False,
            "unity_data_fetched": False,
            "unity_wasm_fetched": False,
            "canvas_present_in_dom": False,
            "screenshot_non_blank": None,
        },
    }

    server_proc = None
    server_handle = None
    report["server"] = {"started": False}

    try:
        report["server"]["port_in_use_before_start"] = port_is_open(HOST, PORT)
        if report["server"]["port_in_use_before_start"]:
            report["notes"].append(
                f"port {PORT} was already accepting connections before start; "
                "results may come from a pre-existing listener"
            )

        server_log = EVIDENCE / "uvicorn.log"
        server_proc, server_handle, server_meta = start_server(server_log)
        report["server"].update(server_meta)
        report["server"]["started"] = True
        report["server"]["pid"] = server_proc.pid

        with httpx.Client(trust_env=False) as client:
            health = wait_for_health(client, server_proc, server_log)
            report["server"]["health"] = health

            report["http_checks"].append(
                check_http(client, "root_html", "/", expected_file=WEB_ROOT / "index.html")
            )
            report["http_checks"].append(
                check_http(
                    client,
                    "loader_js",
                    LOADER_PATH,
                    expected_file=WEB_ROOT / LOADER_PATH.lstrip("/"),
                )
            )

        if not health["ok"]:
            report["notes"].append(
                "health endpoint never returned 200; Chrome was not launched"
            )
            report["server"]["stop"] = stop_server(server_proc, server_handle)
            server_proc = None
            report["verified_note"] = "server did not become healthy"
            return report

        # -- warm the OS page cache -----------------------------------------
        # Chrome's virtual-time budget expires ~1 s after load, so the 10 MB
        # .data.gz request can be cut off by process exit before uvicorn logs
        # it.  Reading the payload once here makes the server's file read fast
        # and removes cold-cache variance.  Direct file reads deliberately, not
        # HTTP: the access log must contain only real browser traffic.
        warm_files = [
            WEB_ROOT / "index.html",
            WEB_ROOT / "Build" / "M4C-Closeout-Player.loader.js",
            WEB_ROOT / "Build" / "M4C-Closeout-Player.data.gz",
            WEB_ROOT / "Build" / "M4C-Closeout-Player.wasm.gz",
            WEB_ROOT / "Build" / "M4C-Closeout-Player.framework.js.gz",
        ]
        warm_bytes = 0
        for path in warm_files:
            try:
                warm_bytes += len(path.read_bytes())
            except OSError:
                pass
        report["warmup"] = {
            "files_read": [str(p) for p in warm_files],
            "bytes_read": warm_bytes,
            "note": "direct file reads to warm the OS page cache; not HTTP",
        }

        # -- Chrome #1: screenshot -------------------------------------------
        shot = EVIDENCE / "screenshot.png"
        if shot.exists():
            shot.unlink()
        shot_before = len(parse_access_log(read_text_capped(server_log))["requests"])
        shot_profile = chrome_profile()
        try:
            report["chrome_screenshot"] = run_chrome_screenshot(shot_profile, shot)
        finally:
            shutil.rmtree(shot_profile, ignore_errors=True)
        time.sleep(0.5)
        report["chrome_screenshot"]["server_requests"] = summarize_requests(
            parse_access_log(read_text_capped(server_log))["requests"][shot_before:]
        )

        if shot.is_file():
            report["screenshot_path"] = str(shot)
            report["screenshot_bytes"] = shot.stat().st_size
            report["screenshot_sha256"] = sha256_file(shot)
        else:
            report["screenshot_path"] = None
            report["screenshot_bytes"] = 0
            report["screenshot_sha256"] = None
            report["notes"].append(
                "Chrome wrote no screenshot; this is expected when the browser "
                "refuses to capture a failed page"
            )

        chrome_log = read_text_capped(EVIDENCE / "chrome_screenshot_stderr.log")
        error_count, error_samples = count_error_lines(chrome_log)
        report["chrome_screenshot"]["error_line_count"] = error_count
        report["chrome_screenshot"]["error_line_samples"] = error_samples

        # -- Chrome #2: --dump-dom -------------------------------------------
        dom_path = EVIDENCE / "dom.html"
        if dom_path.exists():
            dom_path.unlink()
        dom_before = len(parse_access_log(read_text_capped(server_log))["requests"])
        dom_profile = chrome_profile()
        try:
            report["chrome_dump_dom"] = run_chrome_dump_dom(dom_profile, dom_path)
        finally:
            shutil.rmtree(dom_profile, ignore_errors=True)
        time.sleep(0.5)
        report["chrome_dump_dom"]["server_requests"] = summarize_requests(
            parse_access_log(read_text_capped(server_log))["requests"][dom_before:]
        )

        dom_text = read_text_capped(dom_path)
        dom_path.write_text(dom_text, encoding="utf-8", newline="\n")
        report["dom_path"] = str(dom_path)
        report["dom_bytes"] = len(dom_text.encode("utf-8"))
        report["dom_contains_unity_canvas"] = bool(CANVAS_RE.search(dom_text))
        dom_log = read_text_capped(EVIDENCE / "chrome_dumpdom_stderr.log")
        dom_error_count, dom_samples = count_error_lines(dom_log)
        report["chrome_dump_dom"]["error_line_count"] = dom_error_count
        report["chrome_dump_dom"]["error_line_samples"] = dom_samples

        # -- Chrome #3: asset probe (deterministic data-bundle fetch) ---------
        # The two capture invocations can exit mid-request; this one lives
        # until the .data.gz request is actually logged, then is killed.
        probe_before = len(parse_access_log(read_text_capped(server_log))["requests"])
        probe_profile = chrome_profile()
        try:
            report["chrome_asset_probe"] = run_chrome_asset_probe(
                probe_profile, server_log, baseline=probe_before
            )
        finally:
            shutil.rmtree(probe_profile, ignore_errors=True)
        time.sleep(0.5)
        report["chrome_asset_probe"]["server_requests"] = summarize_requests(
            parse_access_log(read_text_capped(server_log))["requests"][probe_before:]
        )

        # -- access log -------------------------------------------------------
        # Chrome may exit with a response still in flight; give uvicorn a
        # moment to finish/flush any access-log line before parsing.
        time.sleep(1.5)
        access = parse_access_log(read_text_capped(server_log))
        report["access_log"] = access

        # -- verified ---------------------------------------------------------
        root = next(
            (c for c in report["http_checks"] if c["name"] == "root_html"), {}
        )
        loader = next(
            (c for c in report["http_checks"] if c["name"] == "loader_js"), {}
        )
        root_ok = (
            root.get("status") == 200
            and "text/html" in (root.get("content_type") or "").lower()
        )
        report["verified"]["page_served"] = bool(root_ok)
        report["verified"]["loader_fetched"] = bool(
            loader.get("status") == 200 and fetched_ok(access, LOADER_PATH)
        )
        report["verified"]["served_matches_local_copy"] = bool(
            root.get("matches_local_file") and loader.get("matches_local_file")
        )
        if not report["verified"]["served_matches_local_copy"]:
            report["notes"].append(
                "served bytes did not match WEB_ROOT files; the response may not "
                "come from the copied build"
            )
        report["verified"]["unity_data_fetched"] = fetched_ok(access, DATA_PATH)
        report["verified"]["unity_wasm_fetched"] = fetched_ok(access, WASM_PATH)
        report["verified"]["canvas_present_in_dom"] = report["dom_contains_unity_canvas"]
        report["verified"]["screenshot_non_blank"] = None

        report["evidence_by_run"] = {
            run: report[run].get("server_requests", {}).get("paths", [])
            for run in ("chrome_screenshot", "chrome_dump_dom", "chrome_asset_probe")
        }
        capture_runs = ("chrome_screenshot", "chrome_dump_dom")
        data_in_capture_runs = any(
            DATA_PATH in report[run].get("server_requests", {}).get("paths", [])
            for run in capture_runs
        )
        if report["verified"]["unity_data_fetched"] and not data_in_capture_runs:
            report["notes"].append(
                ".data.gz was requested only during the asset probe: the capture "
                "invocations exit when --virtual-time-budget expires (~1 s) and "
                "can abort the in-flight data request"
            )
        if not report["verified"]["unity_data_fetched"]:
            report["notes"].append(
                ".data.gz was never fetched with 200; Unity cannot finish loading"
            )
        if report["chrome_asset_probe"].get("terminated_by_harness"):
            report["notes"].append(
                "chrome_asset_probe exit_code 1 is the harness killing Chrome "
                "right after the .data.gz request was observed, not a crash"
            )
        unity = report["chrome_asset_probe"].get("unity", {})
        if unity.get("engine_version"):
            report["notes"].append(
                "Unity engine booted in headless Chrome: "
                f"version {unity['engine_version']}, "
                f"webgl2_context={unity.get('webgl_context_created')}, "
                f"player_data={unity.get('player_data_loading')}"
            )
        if unity.get("gpu_process_crashed"):
            report["notes"].append(
                "Chrome's GPU process exited unexpectedly right after Unity "
                "created its WebGL2 context; rendering was not verified and the "
                "screenshot stays on the Unity loading screen"
            )
        if unity.get("shaders_not_supported"):
            report["notes"].append(
                "Unity reported "
                f"{len(unity['shaders_not_supported'])} shader(s) unsupported on "
                "this GPU (headless SwiftShader): "
                + "; ".join(unity["shaders_not_supported"][:5])
                + "; the build's rendering path cannot be validated here"
            )
        if unity.get("scene_load_log_seen"):
            report["notes"].append(
                "Unity logged scene load (UnloadTime) in headless Chrome, so the "
                "runtime and game bootstrap ran; gameplay and rendering are still "
                "unverified"
            )
        report["notes"].append(
            "screenshot_non_blank is null: not analysed (Pillow unavailable); "
            "only screenshot_bytes and screenshot_sha256 were recorded"
        )
        report["notes"].append(
            "canvas_present_in_dom only proves the <canvas id=\"unity-canvas\"> "
            "element exists in the dumped DOM, not that Unity initialised"
        )
        if not fetched_ok(access, FRAMEWORK_PATH):
            report["notes"].append(
                f"{FRAMEWORK_PATH} was not requested successfully; Unity cannot "
                "start without its framework bundle"
            )
        if report["chrome_screenshot"].get("timed_out"):
            report["notes"].append(
                f"Chrome screenshot run hit the {CHROME_TIMEOUT_S:.0f}s timeout "
                "and was killed"
            )
        if report["chrome_dump_dom"].get("timed_out"):
            report["notes"].append(
                f"Chrome --dump-dom run hit the {CHROME_TIMEOUT_S:.0f}s timeout "
                "and was killed"
            )

        return report
    finally:
        if server_proc is not None and server_handle is not None:
            try:
                report["server"]["stop"] = stop_server(server_proc, server_handle)
            except Exception:
                report["server"]["stop"] = {"error": traceback.format_exc()}


def main() -> int:
    out = EVIDENCE / "browser_smoke.json"
    try:
        report = build_report()
    except Exception:
        report = {
            "generated_at": _dt.datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
            "fatal_error": traceback.format_exc(),
        }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print("=" * 72)
    print("browser smoke summary")
    print("=" * 72)
    print(f"url                : {report.get('url', BASE_URL)}")
    print(f"evidence json      : {out}")
    if "fatal_error" in report:
        print("FATAL ERROR:")
        print(report["fatal_error"])
        return 0
    server = report.get("server", {})
    health = server.get("health", {})
    print(f"server health      : {health.get('ok')} ({health.get('elapsed_s')}s)")
    for check in report.get("http_checks", []):
        print(
            f"http {check.get('name'):<10}: status={check.get('status')} "
            f"type={check.get('content_type')} bytes={check.get('bytes')}"
        )
    access = report.get("access_log", {})
    print(f"asset requests     : {len(access.get('requested_asset_paths', []))}")
    for path in access.get("requested_asset_paths", []):
        codes = access.get("statuses", {}).get(path, [])
        print(f"  {path} -> {codes}")
    shot = report.get("chrome_screenshot", {})
    print(
        f"chrome screenshot  : exit={shot.get('exit_code')} "
        f"timed_out={shot.get('timed_out')} "
        f"error_lines={shot.get('error_line_count')}"
    )
    print(
        f"screenshot         : {report.get('screenshot_path')} "
        f"({report.get('screenshot_bytes')} bytes)"
    )
    dom = report.get("chrome_dump_dom", {})
    print(
        f"chrome --dump-dom  : exit={dom.get('exit_code')} "
        f"timed_out={dom.get('timed_out')} "
        f"unity-canvas={report.get('dom_contains_unity_canvas')}"
    )
    print(f"dom                : {report.get('dom_path')}")
    probe = report.get("chrome_asset_probe", {})
    print(
        f"chrome asset probe : data_bundle_seen={probe.get('data_bundle_seen')} "
        f"elapsed={probe.get('elapsed_s')}s timed_out={probe.get('timed_out')}"
    )
    print("-" * 72)
    for key, value in report.get("verified", {}).items():
        print(f"verified.{key:<26} = {value}")
    for note in report.get("notes", []):
        print(f"note: {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
