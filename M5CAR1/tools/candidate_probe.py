"""Local WebGL candidate probe.

Finding that shapes this probe: the copied M4C build bakes an API base of
``http://127.0.0.1:8787`` (visible in ``M4C-Closeout-Player.data.gz`` next to
``/api/v1/meta``, ``/api/v1/sessions`` and ``/api/v1/sessions//cancel``).  So
the candidate is served *by the backend itself* on port 8787, which makes the
page and its API calls same-origin.

The probe records what actually happened: served assets, whether the Unity
client called the business API, and a screenshot.  It never claims gameplay.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "Server"
PY = SERVER / ".venv" / "Scripts" / "python.exe"
WEB_ROOT = ROOT / "M5CAR1" / "local_candidate" / "webgl"
OUT = ROOT / "M5CAR1" / "evidence" / "browser" / "candidate_probe"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
PORT = 8787


def _wait_ready(url: str, timeout_s: float = 40.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.25)
    return False


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("LLM_"):
            env.pop(key)
    env.update(
        {
            "APP_ENTRY_MODE": "mock",
            "MODEL_PROVIDER": "mock",
            "WEB_ROOT": str(WEB_ROOT),
            "CORS_ALLOWED_ORIGINS": f"http://127.0.0.1:{PORT},http://localhost:{PORT}",
            "PYTHONUNBUFFERED": "1",
        }
    )
    log_path = OUT / "uvicorn.log"
    log = open(log_path, "w", encoding="utf-8")
    server = subprocess.Popen(
        [
            str(PY),
            "-m",
            "uvicorn",
            "app.entry:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
            "--no-proxy-headers",
            "--log-level",
            "info",
        ],
        cwd=str(SERVER),
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    result: dict[str, object] = {"port": PORT, "web_root": str(WEB_ROOT)}
    try:
        result["server_ready"] = _wait_ready(f"http://127.0.0.1:{PORT}/api/v1/health")
        if not result["server_ready"]:
            return 1
        health = json.loads(
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/v1/health", timeout=5).read().decode("utf-8")
        )
        result["health_model_status"] = health["data"].get("model_status")
        runs = {"virtual_60s": 60, "virtual_120s": 120}
        for name, budget in runs.items():
            png = OUT / f"{name}.png"
            stderr_path = OUT / f"{name}.stderr.log"
            command = [
                str(CHROME),
                "--headless=new",
                "--use-angle=d3d11",
                "--enable-gpu",
                "--ignore-gpu-blocklist",
                "--no-sandbox",
                "--no-first-run",
                "--disable-extensions",
                f"--user-data-dir={OUT / ('profile-' + name)}",
                "--window-size=1280,800",
                f"--virtual-time-budget={budget * 1000}",
                f"--screenshot={png}",
                f"http://127.0.0.1:{PORT}/",
            ]
            started = time.time()
            with open(stderr_path, "w", encoding="utf-8") as err:
                completed = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=err, timeout=300)
            entry: dict[str, object] = {
                "virtual_budget_ms": budget * 1000,
                "wall_clock_s": round(time.time() - started, 1),
                "exit_code": completed.returncode,
                "png_bytes": png.stat().st_size if png.exists() else 0,
            }
            try:
                from PIL import Image  # type: ignore

                if png.exists():
                    image = Image.open(png).convert("RGB")
                    colours = image.getcolors(maxcolors=1 << 20) or []
                    entry["unique_colors"] = len(colours)
                    entry["size"] = list(image.size)
            except Exception as exc:  # pragma: no cover
                entry["pixel_error"] = type(exc).__name__
            result[name] = entry
            print(name, json.dumps(entry, ensure_ascii=False))
    finally:
        server.terminate()
        try:
            server.wait(timeout=20)
        except subprocess.TimeoutExpired:
            server.kill()
        log.close()

    text = log_path.read_text(encoding="utf-8", errors="replace")
    api_lines = [line.strip() for line in text.splitlines() if "/api/v1/" in line]
    result["api_requests"] = api_lines
    result["business_api_calls"] = sorted({line.split('"')[1] for line in api_lines if '"/api/v1/' in line})
    result["asset_requests"] = sorted(
        {
            line.split('"')[1]
            for line in text.splitlines()
            if '"/Build/' in line or '"/TemplateData/' in line
        }
    )
    (OUT / "candidate_probe.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("business_api_calls", "asset_requests")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
