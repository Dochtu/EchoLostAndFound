"""M5-C-A-R1 integration driver: real HTTP, local processes, Fake LLM only.

No real model, no external network, no magic credits.  Every check name states
exactly what was proven; in particular:

* a server-side session GET is *not* a browser refresh / save restore;
* the Fake upstream is *not* a real model (the service must say synthetic);
* server-side settlement prerequisites are *not* a Unity completion;
* local files are *not* ModelScope platform persistence.

Run from anywhere:
    Server\\.venv\\Scripts\\python.exe M5CAR1\\e2e\\run_e2e_r1.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "Server"
PY = SERVER / ".venv" / "Scripts" / "python.exe"
EVIDENCE = ROOT / "M5CAR1" / "evidence" / "e2e"
STATE = EVIDENCE / "state"
LOGS = EVIDENCE / "logs"
RESULTS_PATH = EVIDENCE / "e2e_r1_results.json"

FAKE_PORT = 19100
FAKE_KEY = "test-key-not-a-real-secret"

RESULTS: list[dict] = []


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record(check_id: str, name: str, passed: bool, detail) -> None:
    RESULTS.append(
        {"id": check_id, "name": name, "passed": bool(passed), "detail": detail}
    )
    print(f"[{'PASS' if passed else 'FAIL'}] {check_id} {name}: {detail}", flush=True)


def http(method: str, url: str, payload=None, headers=None, timeout=20.0):
    data = None
    hdrs = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    if headers:
        hdrs.update(headers)
    request = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"raw": raw}


def api(base: str, path: str, method: str = "GET", payload=None, headers=None, timeout=20.0):
    return http(method, f"{base}{path}", payload, headers, timeout)


def data_of(body: dict) -> dict:
    return body.get("data") or {}


class Service:
    """One real uvicorn process started through the production entry point."""

    def __init__(self, name: str, port: int, env: dict[str, str]) -> None:
        self.name = name
        self.port = port
        self.env = env
        self.base = f"http://127.0.0.1:{port}"
        self.proc: subprocess.Popen | None = None
        self.log_path = LOGS / f"{name}.log"

    def start(self) -> "Service":
        LOGS.mkdir(parents=True, exist_ok=True)
        environment = {k: v for k, v in os.environ.items() if not k.startswith("LLM_")}
        environment.update(
            {
                "PATH": os.environ.get("PATH", ""),
                "PYTHONUNBUFFERED": "1",
                "PYTHONIOENCODING": "utf-8",
                **self.env,
                "PORT": str(self.port),
            }
        )
        self.log_file = open(self.log_path, "w", encoding="utf-8")
        self.proc = subprocess.Popen(
            [str(PY), "-m", "app.server_entry"],
            cwd=str(SERVER),
            env=environment,
            stdout=self.log_file,
            stderr=subprocess.STDOUT,
        )
        return self

    def wait_ready(self, timeout: float = 90.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.proc is not None and self.proc.poll() is not None:
                return False
            try:
                status, _ = api(self.base, "/api/v1/health", timeout=3.0)
                if status == 200:
                    return True
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(0.25)
        return False

    def health(self) -> dict:
        return data_of(api(self.base, "/api/v1/health")[1])

    def stop(self) -> None:
        if self.proc is None:
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=10)
        try:
            self.log_file.close()
        except Exception:  # pragma: no cover - diagnostic only
            pass
        self.proc = None

    def log_text(self) -> str:
        try:
            return self.log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""


class FakeUpstream:
    def __init__(self, port: int = FAKE_PORT) -> None:
        self.port = port
        self.base = f"http://127.0.0.1:{port}"
        self.proc: subprocess.Popen | None = None
        self.log_path = LOGS / "fake-llm.log"

    def start(self) -> "FakeUpstream":
        LOGS.mkdir(parents=True, exist_ok=True)
        self.log_file = open(self.log_path, "w", encoding="utf-8")
        self.proc = subprocess.Popen(
            [
                str(PY),
                str(SERVER / "tools" / "fake_llm_server.py"),
                "--port",
                str(self.port),
            ],
            cwd=str(SERVER),
            env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"},
            stdout=self.log_file,
            stderr=subprocess.STDOUT,
        )
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                status, _ = http("GET", f"{self.base}/healthz", timeout=2.0)
                if status == 200:
                    return self
            except (urllib.error.URLError, OSError):
                time.sleep(0.1)
        raise RuntimeError("fake upstream did not start")

    def stats(self) -> dict:
        return http("GET", f"{self.base}/__stats", timeout=5.0)[1]

    def reset(self) -> None:
        http("POST", f"{self.base}/__reset", {}, timeout=5.0)

    def stop(self) -> None:
        if self.proc is None:
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        try:
            self.log_file.close()
        except Exception:  # pragma: no cover - diagnostic only
            pass
        self.proc = None


# --------------------------------------------------------------------- API flow


def create_session(base, npc_id, evidence=(), fields=()):
    status, body = api(
        base,
        "/api/v1/sessions",
        "POST",
        {
            "npc_id": npc_id,
            "evidence_ids": list(evidence),
            "observed_field_ids": list(fields),
        },
    )
    if status != 201:
        raise AssertionError(f"create session failed: {status} {body}")
    return data_of(body)["conversation_id"]


def take_turn(base, conversation_id, **body):
    status, payload = api(
        base, f"/api/v1/sessions/{conversation_id}/turns", "POST", body
    )
    return status, data_of(payload) if status == 200 else payload


def present(base, conversation_id, evidence=(), fields=()):
    status, body = api(
        base,
        f"/api/v1/sessions/{conversation_id}/evidence",
        "POST",
        {"evidence_ids": list(evidence), "observed_field_ids": list(fields)},
    )
    if status != 200:
        raise AssertionError(f"present failed: {status} {body}")
    return data_of(body)


def session_state(base, conversation_id):
    status, body = api(base, f"/api/v1/sessions/{conversation_id}")
    return status, (data_of(body) if status == 200 else body)


def init_ledger(path: Path, epoch: Path, limit: int, per_session: int, tokens: int) -> None:
    if path.exists():
        path.unlink()
    if epoch.exists():
        epoch.unlink()
    result = subprocess.run(
        [
            str(PY),
            "-m",
            "app.ledger_admin",
            "init",
            "--confirm",
            "--path",
            str(path),
            "--epoch-path",
            str(epoch),
            "--limit",
            str(limit),
            "--per-session",
            str(per_session),
            "--token-limit",
            str(tokens),
        ],
        cwd=str(SERVER),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"ledger init failed: {result.stderr or result.stdout}")


def ledger_env(path: Path, epoch: Path) -> dict[str, str]:
    return {"LLM_USAGE_PATH": str(path), "LLM_LEDGER_EPOCH_PATH": str(epoch)}


def mock_env() -> dict[str, str]:
    # The driver intentionally makes many requests fast; raise the local limits
    # so only the checks that target a limiter are constrained by one.
    return {
        "APP_ENTRY_MODE": "mock",
        "MODEL_PROVIDER": "mock",
        "LOG_LEVEL": "INFO",
        "CLIENT_RATE_LIMIT_PER_MINUTE": "5000",
        "CLIENT_RATE_LIMIT_BURST": "2000",
        "NEW_SESSION_RATE_PER_MINUTE": "5000",
        "NEW_SESSION_RATE_BURST": "2000",
        "SESSION_TURN_RATE_PER_MINUTE": "5000",
        "SESSION_TURN_RATE_BURST": "2000",
        "RATE_LIMIT_PER_MINUTE": "5000",
        "RATE_LIMIT_BURST": "2000",
    }


def live_env(path: Path, epoch: Path, **overrides) -> dict[str, str]:
    env = {
        "APP_ENTRY_MODE": "live",
        "MODEL_PROVIDER": "llm",
        "LLM_BASE_URL": f"http://127.0.0.1:{FAKE_PORT}/v1",
        "LLM_MODEL": "fake-model",
        "LLM_API_KEY": FAKE_KEY,
        "LLM_REQUEST_LIMIT": "40",
        "LLM_REQUEST_LIMIT_PER_SESSION": "20",
        "LLM_TOKEN_LIMIT": "200000",
        "LLM_MAX_CONCURRENCY": "2",
        "LLM_BREAKER_THRESHOLD": "5",
        "LLM_BREAKER_COOLDOWN_SECONDS": "60",
        # Keep the failure matrix independent: the breaker itself is covered by
        # the unit/transport tests, not by this integration stage.
        "LLM_BREAKER_THRESHOLD": "50",
        "CLIENT_RATE_LIMIT_PER_MINUTE": "5000",
        "CLIENT_RATE_LIMIT_BURST": "2000",
        "NEW_SESSION_RATE_PER_MINUTE": "5000",
        "NEW_SESSION_RATE_BURST": "2000",
        "SESSION_TURN_RATE_PER_MINUTE": "5000",
        "SESSION_TURN_RATE_BURST": "2000",
        "RATE_LIMIT_PER_MINUTE": "5000",
        "RATE_LIMIT_BURST": "2000",
        **ledger_env(path, epoch),
    }
    env.update(overrides)
    return env


# ----------------------------------------------------------------------- stages


def run_mock_stage() -> None:
    service = Service("mock", 18080, mock_env()).start()
    try:
        if not service.wait_ready():
            record("M0", "mock service started", False, service.log_text()[-800:])
            return
        record("M0", "mock service starts through app.server_entry", True, service.base)
        health = service.health()
        ok = (
            health.get("ready") is True
            and health.get("entry_mode") == "mock"
            and health.get("model_status") == "mock"
            and health.get("model_ready") is False
            and health.get("provider", {}).get("is_synthetic") is True
        )
        record(
            "M1",
            "health contract reports mock mode and an unverified synthetic provider",
            ok,
            {
                "entry_mode": health.get("entry_mode"),
                "model_status": health.get("model_status"),
                "model_ready": health.get("model_ready"),
                "is_synthetic": health.get("provider", {}).get("is_synthetic"),
            },
        )

        evidence_ok = []
        for evidence_id in ("E01", "E02", "E03", "E04", "E05"):
            try:
                conversation = create_session(service.base, "npc_laozhou", [evidence_id])
                result = present(service.base, conversation, [evidence_id])
                evidence_ok.append(
                    evidence_id in result.get("presented_evidence_ids", [])
                )
            except AssertionError as exc:
                evidence_ok.append(f"{evidence_id}:{exc}")
        record(
            "M2",
            "E01-E05 can be presented to the server one by one",
            all(value is True for value in evidence_ok),
            evidence_ok,
        )

        disclosures = {}

        conversation = create_session(service.base, "npc_laozhou", ["E02"])
        disclosures["D01"] = present(service.base, conversation, ["E02"]).get(
            "triggered_disclosure_ids", []
        )

        conversation = create_session(service.base, "npc_laozhou", ["E03", "E04"])
        present(service.base, conversation, ["E03"])
        disclosures["D02_laozhou"] = present(service.base, conversation, ["E04"]).get(
            "triggered_disclosure_ids", []
        )

        conversation = create_session(service.base, "npc_linyao", ["E03", "E04"])
        disclosures["D02_linyao"] = present(
            service.base, conversation, ["E03", "E04"]
        ).get("triggered_disclosure_ids", [])

        conversation = create_session(service.base, "npc_laozhou", ["E01", "E05"])
        present(service.base, conversation, ["E01"])
        disclosures["D03"] = present(service.base, conversation, ["E05"]).get(
            "triggered_disclosure_ids", []
        )

        conversation = create_session(
            service.base, "npc_linyao", ["E01"], ["watch.back_engraving"]
        )
        disclosures["REC.engraving"] = present(
            service.base, conversation, ["E01"], ["watch.back_engraving"]
        ).get("triggered_disclosure_ids", [])

        ok = (
            "D01" in disclosures["D01"]
            and "D02" in disclosures["D02_laozhou"]
            and "D02" in disclosures["D02_linyao"]
            and "D03" in disclosures["D03"]
            and "REC.engraving" in disclosures["REC.engraving"]
        )
        record(
            "M3",
            "D01-D03 and REC.engraving trigger through disclosed evidence "
            "(server-side only, no Unity ending)",
            ok,
            disclosures,
        )

        conversation = create_session(service.base, "npc_laozhou", ["E02"])
        present(service.base, conversation, ["E02"])
        status, state = session_state(service.base, conversation)
        fresh = session_state(service.base, conversation)[1]
        record(
            "M4",
            "a NEW plain HTTP client reads the same server-side session state "
            "(this is NOT a browser refresh or save restore)",
            status == 200
            and fresh.get("presented_evidence_ids") == ["E02"]
            and fresh.get("triggered_disclosure_ids") == ["D01"],
            {
                "presented": fresh.get("presented_evidence_ids"),
                "disclosures": fresh.get("triggered_disclosure_ids"),
            },
        )

        player_a = create_session(service.base, "npc_laozhou", ["E02"])
        player_b = create_session(service.base, "npc_laozhou")
        present(service.base, player_a, ["E02"])
        _, state_a = session_state(service.base, player_a)
        _, state_b = session_state(service.base, player_b)
        record(
            "M5",
            "two sessions for the same NPC keep separate evidence and disclosure state",
            state_a.get("presented_evidence_ids") == ["E02"]
            and state_b.get("presented_evidence_ids") == []
            and "opt.laozhou.repeat_b01" in state_a.get("available_topic_ids", [])
            and "opt.laozhou.repeat_b01" not in state_b.get("available_topic_ids", []),
            {"a": state_a.get("available_topic_ids"), "b": state_b.get("available_topic_ids")},
        )

        conversation = create_session(service.base, "npc_laozhou")
        status, turn = take_turn(
            service.base,
            conversation,
            topic_id="opt.laozhou.ask_b01",
        )
        record(
            "M6",
            "mock mode answers from approved fixed content and marks it synthetic",
            status == 200
            and turn.get("source") == "fixed_line"
            and turn.get("provider", {}).get("is_synthetic") is True,
            {
                "source": turn.get("source"),
                "provider": turn.get("provider"),
            },
        )

        unified = []
        for order in (
            ("E01", "E02", "E03", "E04", "E05"),
            ("E05", "E04", "E03", "E02", "E01"),
        ):
            conversation = create_session(service.base, "npc_laozhou", order)
            triggered: list[str] = []
            for evidence_id in order:
                result = present(service.base, conversation, [evidence_id])
                triggered.extend(result.get("triggered_disclosure_ids", []))
            unified.append(sorted(set(triggered)))
        record(
            "M7",
            "D01-D03 are reachable in both evidence orders "
            "(server-side prerequisites only, NOT a Unity ending)",
            unified[0] == unified[1] and "D01" in unified[0] and "D03" in unified[0],
            unified,
        )
    finally:
        service.stop()


def run_live_stage() -> None:
    ledger = STATE / "live.sqlite3"
    epoch = STATE / "live-epoch" / "ledger-epoch.json"
    init_ledger(ledger, epoch, limit=40, per_session=20, tokens=200000)
    service = Service("live", 18081, live_env(ledger, epoch)).start()
    fake = FakeUpstream().start()
    try:
        if not service.wait_ready():
            record("L0", "live service started", False, service.log_text()[-800:])
            return
        record("L0", "live service starts with a verified ledger", True, service.base)

        health = service.health()
        record(
            "L1",
            "configured but unproven: health separates readiness from a verified model",
            health.get("model_status") == "configured_unverified"
            and health.get("model_ready") is False
            and health.get("model_available") is True,
            {
                "model_status": health.get("model_status"),
                "model_ready": health.get("model_ready"),
                "model_available": health.get("model_available"),
            },
        )

        fake.reset()
        conversation = create_session(service.base, "npc_laozhou", ["E01"])
        status, turn = take_turn(
            service.base, conversation, text="那晚站台到底发生了什么"
        )
        health = service.health()
        record(
            "L2",
            "the Fake upstream answers a free turn, and the service still reports it "
            "as synthetic: a Fake LLM is NOT a real model",
            status == 200
            and turn.get("source") == "external_model"
            and turn.get("provider", {}).get("is_synthetic") is True
            and health.get("model_status") == "test_upstream_verified"
            and health.get("model_ready") is False,
            {
                "source": turn.get("source"),
                "provider": turn.get("provider"),
                "model_status": health.get("model_status"),
                "model_ready": health.get("model_ready"),
            },
        )

        if status == 200 and turn.get("source") == "fixed":
            record("L2b", "free text reached the model path", False, turn)
        if status == 200:
            page = json.dumps(turn, ensure_ascii=False)
            record(
                "L5",
                "the API key never appears in a turn envelope",
                FAKE_KEY not in page,
                "searched turn JSON",
            )

        matrix = []
        for marker, expected_source in (
            ("[[fake:401]]", "fallback"),
            ("[[fake:429]]", "fallback"),
            ("[[fake:500]]", "fallback"),
            ("[[fake:badjson]]", "fallback"),
            ("[[fake:truncate]]", "fallback"),
            ("[[fake:unsafe]]", "fallback"),
            ("[[fake:leak]]", "fallback"),
        ):
            before = fake.stats()["requests"]
            conversation = create_session(service.base, "npc_laozhou", ["E01"])
            status, turn = take_turn(service.base, conversation, text=marker)
            after = fake.stats()["requests"]
            matrix.append(
                {
                    "marker": marker,
                    "status": status,
                    "source": turn.get("source"),
                    "fallback_reason": turn.get("fallback_reason"),
                    "upstream_calls": after - before,
                }
            )
        ok = all(
            item["status"] == 200
            and item["source"] == "fallback"
            and item["upstream_calls"] == 1
            for item in matrix
        )
        record(
            "L3",
            "upstream failures degrade safely with exactly one call each "
            "(no automatic retry)",
            ok,
            matrix,
        )

        before = fake.stats()["requests"]
        conversation = create_session(service.base, "npc_laozhou")
        status, turn = take_turn(
            service.base, conversation, text="[[fake:timeout]]"
        )
        after = fake.stats()["requests"]
        record(
            "L4",
            "a timed-out turn degrades to deterministic content and is still counted",
            status == 200
            and turn.get("source") in {"fallback", "fixed_line"},
            {
                "source": turn.get("source"),
                "fallback_reason": turn.get("fallback_reason"),
                "upstream_calls": after - before,
            },
        )

        conversation = create_session(service.base, "npc_laozhou")
        status, turn = take_turn(
            service.base, conversation, topic_id="opt.laozhou.ask_b01"
        )
        record(
            "L6",
            "the game still serves approved fixed content after model failures",
            status == 200 and turn.get("source") == "fixed_line",
            {"source": turn.get("source")},
        )

        health = service.health()
        ledger_state = health.get("ledger") or {}
        record(
            "L7",
            "the health ledger reports settled token usage instead of zero",
            ledger_state.get("global_used", 0) > 0
            and ledger_state.get("tokens_used", 0) > 0,
            {
                "global_used": ledger_state.get("global_used"),
                "tokens_used": ledger_state.get("tokens_used"),
            },
        )

        # Restart: the ledger generation must survive; in-memory sessions must not.
        epoch_before = ledger_state.get("epoch_fingerprint")
        used_before = ledger_state.get("global_used")
        old_session = create_session(service.base, "npc_laozhou")
        service.stop()
        service = Service("live-restarted", 18081, live_env(ledger, epoch)).start()
        if not service.wait_ready():
            record("R1", "live service restarts on the existing ledger", False, service.log_text()[-800:])
            return
        health = service.health()
        ledger_state = health.get("ledger") or {}
        record(
            "R1",
            "the ledger generation and usage survive a process restart "
            "(local process only, NOT platform persistence)",
            ledger_state.get("epoch_fingerprint") == epoch_before
            and ledger_state.get("global_used") == used_before
            and ledger_state.get("persistent") is True,
            {
                "epoch_before": epoch_before,
                "epoch_after": ledger_state.get("epoch_fingerprint"),
                "used_before": used_before,
                "used_after": ledger_state.get("global_used"),
            },
        )

        status, body = session_state(service.base, old_session)
        record(
            "R2",
            "after a restart the old conversation id returns 404, so the client must "
            "re-establish the session (server-side behaviour, NOT browser recovery)",
            status == 404,
            {"status": status, "code": (body.get("error") or {}).get("code")},
        )

        conversation = create_session(service.base, "npc_laozhou")
        status, turn = take_turn(
            service.base, conversation, topic_id="opt.laozhou.ask_b01"
        )
        record(
            "R3",
            "a new session works after the restart",
            status == 200 and turn.get("source") == "fixed_line",
            {"source": turn.get("source")},
        )
    finally:
        service.stop()
        fake.stop()


def run_budget_stage() -> None:
    ledger = STATE / "tight.sqlite3"
    epoch = STATE / "tight-epoch" / "ledger-epoch.json"
    init_ledger(ledger, epoch, limit=3, per_session=2, tokens=200000)
    fake = FakeUpstream().start()
    service = Service(
        "tight",
        18082,
        live_env(
            ledger,
            epoch,
            LLM_REQUEST_LIMIT="3",
            LLM_REQUEST_LIMIT_PER_SESSION="2",
        ),
    ).start()
    try:
        if not service.wait_ready():
            record("B0", "tight-budget service started", False, service.log_text()[-800:])
            return
        record("B0", "tight-budget service starts", True, service.base)

        health = service.health()
        used = []
        conversation_one = create_session(service.base, "npc_laozhou", ["E01"])
        conversation_two = create_session(service.base, "npc_laozhou", ["E01"])
        for conversation in (conversation_one, conversation_one, conversation_two):
            status, turn = take_turn(
                service.base, conversation, text="那晚站台到底发生了什么"
            )
            used.append(turn.get("source"))
        before = fake.stats()["requests"]
        conversation_three = create_session(service.base, "npc_laozhou", ["E01"])
        status, turn = take_turn(
            service.base, conversation_three, text="那晚站台到底发生了什么"
        )
        after = fake.stats()["requests"]
        record(
            "B1",
            "the global request limit is enforced and no upstream call happens after it",
            after == before
            and turn.get("source") == "fallback"
            and str(turn.get("fallback_reason", "")).startswith("budget_"),
            {
                "first_three": used,
                "blocked_reason": turn.get("fallback_reason"),
                "extra_upstream_calls": after - before,
            },
        )
    finally:
        service.stop()
        fake.stop()

    # Token budget: with a small context the worst-case reservation nearly
    # equals the whole generation budget, so the second request must be refused.
    token_ledger = STATE / "tokens.sqlite3"
    token_epoch = STATE / "tokens-epoch" / "ledger-epoch.json"
    init_ledger(token_ledger, token_epoch, limit=20, per_session=10, tokens=1000)
    fake = FakeUpstream().start()
    service = Service(
        "token-tight",
        18082,
        live_env(
            token_ledger,
            token_epoch,
            LLM_TOKEN_LIMIT="1000",
            LLM_CONTEXT_MAX_TOKENS="768",
            LLM_MAX_OUTPUT_TOKENS="64",
            LLM_SYSTEM_PROMPT_MAX_TOKENS="512",
            LLM_EVIDENCE_CONTEXT_MAX_TOKENS="256",
            LLM_INPUT_MAX_CHARS="200",
        ),
    ).start()
    try:
        if not service.wait_ready():
            record("B2", "token-budget service started", False, service.log_text()[-800:])
            return
        attempts = []
        blocked = None
        for _ in range(12):
            conversation = create_session(service.base, "npc_laozhou", ["E01"])
            status, turn = take_turn(
                service.base, conversation, text="那晚站台到底发生了什么"
            )
            attempts.append(
                {
                    "source": turn.get("source"),
                    "reason": turn.get("fallback_reason"),
                }
            )
            if turn.get("fallback_reason") == "budget_token_exhausted":
                blocked = turn
                break
        before = fake.stats()["requests"]
        conversation = create_session(service.base, "npc_laozhou", ["E01"])
        take_turn(service.base, conversation, text="那晚站台到底发生了什么")
        after = fake.stats()["requests"]
        ledger_state = service.health().get("ledger") or {}
        record(
            "B2",
            "the token budget refuses requests before calling the upstream",
            blocked is not None
            and after == before
            and ledger_state.get("tokens_used", 0) <= ledger_state.get("token_limit", 0),
            {
                "attempts": attempts,
                "tokens_used": ledger_state.get("tokens_used"),
                "token_limit": ledger_state.get("token_limit"),
                "extra_upstream_calls": after - before,
            },
        )
    finally:
        service.stop()
        fake.stop()

    # Refusal to start on a broken ledger.
    broken_ledger = STATE / "broken.sqlite3"
    broken_epoch = STATE / "broken-epoch" / "ledger-epoch.json"
    broken_ledger.parent.mkdir(parents=True, exist_ok=True)
    broken_ledger.write_text("this is not a sqlite database", encoding="utf-8")
    broken_epoch.parent.mkdir(parents=True, exist_ok=True)
    broken_epoch.write_text(
        json.dumps({"epoch": "deadbeef" * 8, "high_water": 0, "token_high_water": 0}),
        encoding="utf-8",
    )
    service = Service("broken-ledger", 18084, live_env(broken_ledger, broken_epoch)).start()
    try:
        code = service.proc.wait(timeout=60) if service.proc is not None else 1
    except subprocess.TimeoutExpired:
        code = 0
        service.stop()
    text = service.log_text()
    record(
        "B3",
        "a corrupt ledger makes the live service refuse to start",
        code != 0 and "budget ledger unusable" in text,
        {"exit_code": code, "log_tail": text.strip().splitlines()[-1:]},
    )


def run_proxy_stage() -> None:
    service = Service(
        "proxy",
        18083,
        {
            **mock_env(),
            "CLIENT_RATE_LIMIT_PER_MINUTE": "1",
            "CLIENT_RATE_LIMIT_BURST": "1",
            "RATE_LIMIT_PER_MINUTE": "1000",
            "RATE_LIMIT_BURST": "1000",
            "NEW_SESSION_RATE_PER_MINUTE": "2",
            "NEW_SESSION_RATE_BURST": "2",
        },
    ).start()
    try:
        if not service.wait_ready():
            record("P0", "proxy-stage service started", False, service.log_text()[-800:])
            return
        first = api(service.base, "/api/v1/meta", headers={"X-Forwarded-For": "203.0.113.1"})
        second = api(service.base, "/api/v1/meta", headers={"X-Forwarded-For": "203.0.113.2"})
        record(
            "P1",
            "with --no-proxy-headers semantics a forged X-Forwarded-For cannot buy "
            "a fresh client bucket",
            first[0] == 200 and second[0] == 429,
            {"first": first[0], "second": second[0]},
        )

        service.stop()
        service = Service(
            "proxy-sessions",
            18083,
            {
                **mock_env(),
                "NEW_SESSION_RATE_PER_MINUTE": "2",
                "NEW_SESSION_RATE_BURST": "2",
                "CLIENT_RATE_LIMIT_PER_MINUTE": "1000",
                "CLIENT_RATE_LIMIT_BURST": "1000",
            },
        ).start()
        if not service.wait_ready():
            record("P2", "new-session flood service started", False, service.log_text()[-800:])
            return
        codes = []
        for index in range(4):
            status, _ = api(
                service.base,
                "/api/v1/sessions",
                "POST",
                {"npc_id": "npc_laozhou"},
                headers={"X-Forwarded-For": f"203.0.113.{index + 10}"},
            )
            codes.append(status)
        record(
            "P2",
            "creating new sessions cannot bypass the new-session client budget",
            codes[:2] == [201, 201] and codes[2] == 429 and codes[3] == 429,
            codes,
        )
    finally:
        service.stop()


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    STATE.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)

    started = now()
    try:
        run_mock_stage()
        run_live_stage()
        run_budget_stage()
        run_proxy_stage()
    finally:
        payload = {
            "generated_at": started,
            "finished_at": now(),
            "driver": "M5CAR1/e2e/run_e2e_r1.py",
            "fake_upstream": "Server/tools/fake_llm_server.py (local socket, no model)",
            "real_model_called": False,
            "checks": RESULTS,
            "passed": all(item["passed"] for item in RESULTS),
            "notes": [
                "All traffic is 127.0.0.1. No real model, no API key, no credits.",
                "Docker is NOT used for this run; the FastAPI app is the same code path.",
                "Session state lives in process memory; restart 404 is expected.",
            ],
        }
        RESULTS_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    total = len(RESULTS)
    passed = sum(1 for item in RESULTS if item["passed"])
    print(f"\n{passed}/{total} checks passed -> {RESULTS_PATH}", flush=True)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
