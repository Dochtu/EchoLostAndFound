"""One-off GPU render probe for the local WebGL candidate.

The headless smoke run proved the page, loader, data and wasm are served and
that the Unity engine boots, but SwiftShader cannot compile three of this
build's URP shaders, so the screenshot only shows the loading screen.  This
probe re-runs Chrome with the ANGLE/D3D11 backend to see whether a real GPU
renders the scene.  It is evidence only; a failure here is recorded, not
hidden.
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
OUT = ROOT / "M5CAR1" / "evidence" / "browser" / "gpu_probe"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
PORT = 18241


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
            "PYTHONUNBUFFERED": "1",
        }
    )
    log = open(OUT / "uvicorn.log", "w", encoding="utf-8")
    server = subprocess.Popen(
        [str(PY), "-m", "uvicorn", "app.entry:app", "--host", "127.0.0.1", "--port", str(PORT), "--no-proxy-headers"],
        cwd=str(SERVER),
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    result: dict[str, object] = {"url": f"http://127.0.0.1:{PORT}/"}
    try:
        ready = False
        for _ in range(80):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/v1/health", timeout=2) as response:
                    ready = response.status == 200
                if ready:
                    break
            except Exception:
                time.sleep(0.25)
        result["server_ready"] = ready
        if not ready:
            return 1
        profile = OUT / "chrome-profile"
        runs = {
            "angle_d3d11": [
                "--headless=new",
                "--use-angle=d3d11",
                "--enable-unsafe-swiftshader",
            ],
            "angle_d3d11_gpu": [
                "--headless=new",
                "--use-angle=d3d11",
                "--enable-gpu",
                "--ignore-gpu-blocklist",
                "--enable-unsafe-swiftshader",
            ],
        }
        for name, flags in runs.items():
            png = OUT / f"{name}.png"
            stderr_path = OUT / f"{name}.stderr.log"
            command = [
                str(CHROME),
                *flags,
                "--no-sandbox",
                "--no-first-run",
                "--disable-extensions",
                f"--user-data-dir={profile}",
                "--window-size=1280,800",
                "--virtual-time-budget=45000",
                f"--screenshot={png}",
                f"http://127.0.0.1:{PORT}/",
            ]
            with open(stderr_path, "w", encoding="utf-8") as err:
                completed = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=err, timeout=180)
            entry: dict[str, object] = {
                "exit_code": completed.returncode,
                "png": str(png.relative_to(ROOT)) if png.exists() else None,
                "png_bytes": png.stat().st_size if png.exists() else 0,
            }
            try:
                from PIL import Image  # type: ignore

                if png.exists():
                    image = Image.open(png).convert("RGB")
                    entry["unique_colors"] = len(set(image.getdata()))
                    entry["size"] = image.size
            except Exception as exc:  # pragma: no cover - diagnostics only
                entry["pixel_error"] = type(exc).__name__
            result[name] = entry
            print(name, json.dumps(entry, ensure_ascii=False))
    finally:
        server.terminate()
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            server.kill()
        log.close()
    (OUT / "gpu_probe.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
