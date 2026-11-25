# Browser smoke harness — report (2026-11-25)

Local-only. Venv Python + Chrome headless against `127.0.0.1:18240`. Nothing outside
`M5CAR1\` was written by this work.

## 1. Commands run

```powershell
# copy the build (never move/edit the original)
Copy-Item -LiteralPath G:\projects\EchoLostAndFound\Builds\M4C-Closeout-Player `
          -Destination G:\projects\EchoLostAndFound\M5CAR1\local_candidate\webgl -Recurse

# build manifest (sha256 of index.html + every Build\ file, and copy-vs-source check)
& G:\projects\EchoLostAndFound\Server\.venv\Scripts\python.exe `
  G:\projects\EchoLostAndFound\M5CAR1\tools\make_build_manifest.py

# harness (starts uvicorn, HTTP checks, Chrome screenshot, --dump-dom, asset probe)
& G:\projects\EchoLostAndFound\Server\.venv\Scripts\python.exe `
  G:\projects\EchoLostAndFound\M5CAR1\tools\browser_smoke.py

# race diagnosis (optionally, already run)
& G:\projects\EchoLostAndFound\Server\.venv\Scripts\python.exe `
  G:\projects\EchoLostAndFound\M5CAR1\tools\diagnose_chrome_wait.py
```

The harness spawns exactly:

```
Server\.venv\Scripts\python.exe -m uvicorn app.entry:app --host 127.0.0.1 --port 18240 --no-proxy-headers
cwd=G:\projects\EchoLostAndFound\Server
APP_ENTRY_MODE=mock MODEL_PROVIDER=mock LOG_LEVEL=INFO
WEB_ROOT=G:\projects\EchoLostAndFound\M5CAR1\local_candidate\webgl
```

Chrome invocations (all `--headless=new --disable-gpu --no-sandbox --no-first-run
--user-data-dir=<temp> --window-size=1280,800 --enable-logging=stderr --v=0`):

1. `--virtual-time-budget=30000 --screenshot=<png> http://127.0.0.1:18240/` (timeout 120 s)
2. `--dump-dom http://127.0.0.1:18240/` → `dom.html`
3. no budget, no capture: poll the access log until `/Build/M4C-Closeout-Player.data.gz`
   gets a 200, then kill (supplementary; not a required invocation)

## 2. Artifacts

| Path | What |
| --- | --- |
| `G:\projects\EchoLostAndFound\M5CAR1\local_candidate\webgl\` | 17-file copy, byte-identical to `Builds\M4C-Closeout-Player` |
| `G:\projects\EchoLostAndFound\M5CAR1\evidence\browser\build_manifest.sha256` | 5 hashes (`index.html`, `Build\*.data.gz`, `*.framework.js.gz`, `*.loader.js`, `*.wasm.gz`) |
| `G:\projects\EchoLostAndFound\M5CAR1\evidence\browser\browser_smoke.json` | full evidence (HTTP checks, access log, Chrome runs, verified flags) |
| `G:\projects\EchoLostAndFound\M5CAR1\evidence\browser\screenshot.png` | 1280x800, 15559 B, sha256 `8315ab90…eb39` |
| `G:\projects\EchoLostAndFound\M5CAR1\evidence\browser\dom.html` | DOM dump containing `<canvas id="unity-canvas">` |
| `G:\projects\EchoLostAndFound\M5CAR1\evidence\browser\uvicorn.log` | access log for the whole run |
| `G:\projects\EchoLostAndFound\M5CAR1\evidence\browser\chrome_*.log` | Chrome stdout/stderr per invocation |
| `G:\projects\EchoLostAndFound\M5CAR1\evidence\browser\diagnostics\chrome_wait_diagnostic.json` | race diagnosis (3 capture variants) |
| `G:\projects\EchoLostAndFound\M5CAR1\tools\browser_smoke.py` | harness (stdlib + httpx) |
| `G:\projects\EchoLostAndFound\M5CAR1\tools\make_build_manifest.py` | manifest writer |
| `G:\projects\EchoLostAndFound\M5CAR1\tools\diagnose_chrome_wait.py` | race diagnosis |
| `G:\projects\EchoLostAndFound\M5CAR1\reports\browser_smoke_report.md` | this report |

## 3. `verified` booleans (final run, 12:29:08 +08:00)

| flag | value | evidence |
| --- | --- | --- |
| `page_served` | true | `GET /` → 200 `text/html; charset=utf-8`, 5689 B, body sha256 `ea25b168…82fb` == `WEB_ROOT\index.html` |
| `loader_fetched` | true | HTTP check 200 (26983 B, sha256 `7383dbd3…cc2b`) and Chrome's access-log 200s |
| `unity_data_fetched` | true | `/Build/M4C-Closeout-Player.data.gz` 200 in the access log (probe run) |
| `unity_wasm_fetched` | true | `/Build/M4C-Closeout-Player.wasm.gz` 200 |
| `canvas_present_in_dom` | true | `dom.html` contains `<canvas id="unity-canvas">` |
| `screenshot_non_blank` | null | not analysed by design (Pillow unavailable); only bytes + sha256 recorded |
| `served_matches_local_copy` | true | served `/` and loader bodies byte-identical to `WEB_ROOT` files |

Additional engine evidence parsed from the Chrome log (`browser_smoke.json` →
`chrome_asset_probe.unity`):

- `engine_version` = `6000.3.29f1`, `webgl_renderer` = `WebKit WebGL`
- `webgl_context_created` = true ("Creating WebGL 2.0 context.")
- `player_data_loading` = true, `scene_load_log_seen` = true (`UnloadTime: …`)
- 3 shaders unsupported on this GPU: `Hidden/CoreSRP/CoreCopy`,
  `Hidden/Universal Render Pipeline/StencilDitherMaskSeed`, `Hidden/Universal/HDRDebugView`
- Unity's own `ERROR: Shader …` console lines (3) are those shader fallbacks, not Chrome crashes
- AudioContext blocked (3x) because there is no user gesture

## 4. What failed / is not verified

- **Rendering not verified.** Headless Chrome uses SwiftShader; Unity reports three URP
  shaders unsupported there. The screenshot (taken ~1.2 s in) shows the Unity loading
  screen at 0 %, so no frame is proven.
- **Gameplay not verified.** No mouse/keyboard injection, no OCR, by instruction.
- **`screenshot_non_blank` is null**, not true: pixel analysis was deliberately skipped.
- **Chrome capture runs are racy**: `--virtual-time-budget=30000` exits at ~1 s wall clock
  and can abort the `.data.gz` request before uvicorn logs it. The dedicated probe removes
  that race (observed 1.3–1.5 s to data fetch, 4.4–4.7 s total). `--timeout` is ignored by
  new headless.
- **Probe `exit_code` 1** is the harness killing Chrome after the data request; recorded as
  `terminated_by_harness: true`.
- Chrome's GPU process exited unexpectedly (`exit_code=1`) in one probe run; Chrome logged
  the crash and continued. Not reproducible in every run.

## 5. Scope

Only `M5CAR1\` files were created/modified. `Builds\` was read only; the copy is a copy.
Note: other agents were editing `Server\app\ledger_admin.py`, `Server\app\policy.py`,
`Server\tests\test_sessions.py` and `Server\tools\fake_llm_server.py` concurrently during
this work (mtimes 12:20–12:23); those changes are not ours. Starting uvicorn imported the
app and regenerated `Server\app\__pycache__` bytecode as a side effect of running the
server; no source under `Server\` was edited here.
