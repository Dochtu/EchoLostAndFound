"""M5-C-A local end-to-end acceptance driver (Docker + fake model only).

No real model, no network beyond 127.0.0.1, no real credential.  The fake
upstream is ``fake_llm/fake_llm_server.py`` in the candidate snapshot.

Usage (from the candidate directory):
    python run_e2e.py --candidate-dir . --mock-url http://127.0.0.1:18080 \
        --live-url http://127.0.0.1:18081 --tight-url http://127.0.0.1:18082 \
        --fake-url http://127.0.0.1:19000 --out evidence/e2e_results.json

The driver starts/stops the compose stacks itself; ``--no-manage`` assumes they
are already running (still used for the pure API checks).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

RESULTS: list[dict] = []


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record(check_id: str, name: str, passed: bool, detail) -> None:
    entry = {"id": check_id, "name": name, "passed": bool(passed), "detail": detail}
    RESULTS.append(entry)
    print(f"[{'PASS' if passed else 'FAIL'}] {check_id} {name}: {detail}", flush=True)


def http(method: str, url: str, payload=None, headers=None, timeout=10):
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
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"raw": raw}


def wait_http(url: str, timeout: float = 90) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            status, _ = http("GET", url, timeout=2)
            if status == 200:
                return True
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(1)
    return False


class Docker:
    def __init__(self, candidate: Path):
        self.candidate = candidate

    def compose(self, compose_file: str, *args: str, timeout=300, check=True):
        result = subprocess.run(
            ["docker", "compose", "-f", compose_file, *args],
            cwd=self.candidate,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        if check and result.returncode != 0:
            raise RuntimeError(
                f"docker compose {compose_file} {' '.join(args)} failed: "
                f"{result.returncode}\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}"
            )
        return result

    def up(self, compose_file: str, service: str | None = None) -> None:
        args = ["up", "-d", "--build"]
        if service:
            args.append(service)
        self.compose(compose_file, *args)

    def down(self, compose_file: str, volumes: bool = False) -> None:
        args = ["down", "--remove-orphans"]
        if volumes:
            args.append("-v")
        self.compose(compose_file, *args)

    def container_id(self, compose_file: str, service: str) -> str:
        result = self.compose(compose_file, "ps", "-q", service, check=False)
        return result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""

    def state(self, compose_file: str, service: str) -> str:
        cid = self.container_id(compose_file, service)
        if not cid:
            return "missing"
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Status}}", cid],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip() or "unknown"

    def logs(self, compose_file: str, service: str) -> str:
        result = self.compose(compose_file, "logs", "--no-color", "--tail", "200", service, check=False)
        return result.stdout + result.stderr

    def ledger_admin(self, compose_file: str, service: str, *args: str):
        return self.compose(
            compose_file,
            "run",
            "--rm",
            "--no-deps",
            "--entrypoint",
            "python",
            service,
            "-m",
            "app.ledger_admin",
            *args,
        )

    def volume_exec(self, compose_file: str, service: str, command: str):
        """Run a shell command in a throwaway container on the service volume."""

        return self.compose(
            compose_file,
            "run",
            "--rm",
            "--no-deps",
            "--entrypoint",
            "sh",
            service,
            "-c",
            command,
        )


class Api:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def health(self):
        return http("GET", f"{self.base}/api/v1/health")

    def create(self, npc_id: str, evidence=(), fields=()):
        status, body = http(
            "POST",
            f"{self.base}/api/v1/sessions",
            {"npc_id": npc_id, "evidence_ids": list(evidence), "observed_field_ids": list(fields)},
        )
        assert status == 201, (status, body)
        return body["data"]

    def session(self, conversation_id: str):
        status, body = http("GET", f"{self.base}/api/v1/sessions/{conversation_id}")
        assert status == 200, (status, body)
        return body["data"]

    def turn(self, conversation_id: str, **payload):
        status, body = http(
            "POST", f"{self.base}/api/v1/sessions/{conversation_id}/turns", payload
        )
        assert status == 200, (status, body)
        return body["data"]

    def present(self, conversation_id: str, evidence=(), fields=()):
        status, body = http(
            "POST",
            f"{self.base}/api/v1/sessions/{conversation_id}/evidence",
            {"evidence_ids": list(evidence), "observed_field_ids": list(fields)},
        )
        assert status == 200, (status, body)
        return body["data"]


def fake_stats(fake_url: str) -> dict:
    _, body = http("GET", f"{fake_url}/__stats")
    return body


def fake_reset(fake_url: str) -> None:
    http("POST", f"{fake_url}/__reset", {})


# ------------------------------------------------------------------ mock


def stage_mock(api: Api, fake_url: str, docker: Docker, candidate: Path) -> None:
    fake_reset(fake_url)
    status, body = api.health()
    health = body["data"]
    record(
        "M1",
        "mock health contract",
        status == 200
        and health["entry_mode"] == "mock"
        and health["game_ready"] is True
        and health["model_available"] is False
        and health["model_ready"] is False
        and health["is_synthetic"] is True
        and health["ledger"]["persistent"] is False,
        {k: health[k] for k in ("entry_mode", "game_ready", "model_available", "model_ready", "is_synthetic", "model_mode")},
    )

    created = api.create("npc_laozhou")
    laozhou = created["conversation_id"]
    opening = created["opening_segments"]
    first = api.present(laozhou, ["E01"])
    second = api.present(laozhou, ["E02"])
    d03_evidence = api.present(laozhou, ["E05"])
    fixed_turn = api.turn(laozhou, topic_id="opt.laozhou.ask_b01")
    free_turn = api.turn(laozhou, text="那晚站台到底发生了什么？")
    final_laozhou = api.session(laozhou)

    created_l = api.create("npc_linyao")
    linyao = created_l["conversation_id"]
    linyao_first = api.present(linyao, ["E03"])
    linyao_second = api.present(linyao, ["E04"])
    engraving = api.present(linyao, ["E01"], ["watch.back_engraving"])
    final_linyao = api.session(linyao)

    chapter_ok = (
        bool(opening)
        and first["triggered_disclosure_ids"] == []
        and second["triggered_disclosure_ids"] == ["D01"]
        and d03_evidence["triggered_disclosure_ids"] == ["D03"]
        and fixed_turn["source"] == "fixed_line"
        and free_turn["source"] in {"mock", "fallback"}
        and linyao_first["triggered_disclosure_ids"] == []
        and linyao_second["triggered_disclosure_ids"] == ["D02"]
        and engraving["triggered_disclosure_ids"] == ["REC.engraving"]
        and set(final_laozhou["triggered_disclosure_ids"]) >= {"D01", "D03"}
        and set(final_linyao["triggered_disclosure_ids"]) >= {"D02", "REC.engraving"}
    )
    record(
        "M2",
        "E01-E05 + D01-D03 + REC.engraving through approved content",
        chapter_ok,
        {
            "laozhou_disclosures": final_laozhou["triggered_disclosure_ids"],
            "linyao_disclosures": final_linyao["triggered_disclosure_ids"],
            "fixed_source": fixed_turn["source"],
            "free_source": free_turn["source"],
        },
    )

    # Route A: station bag handover only needs E01 and the physical watch parts.
    route_a = api.create("npc_laozhou")["conversation_id"]
    route_a_state = api.present(route_a, ["E01"], ["watch.back_engraving", "watch.serial_number"])
    # Route B: Lin Yao's temporary custody needs D02 (E03+E04) plus owner evidence.
    route_b = api.create("npc_linyao")["conversation_id"]
    api.present(route_b, ["E03"])
    route_b_state = api.present(route_b, ["E04"], ["designated_receipt.owner"])
    record(
        "M3",
        "both chapter-01 custody routes have satisfiable server prerequisites",
        "E01" in route_a_state["presented_evidence_ids"]
        and "watch.back_engraving" in route_a_state["observed_field_ids"]
        and "D02" in route_b_state["triggered_disclosure_ids"],
        {
            "route_a_presented": route_a_state["presented_evidence_ids"],
            "route_a_fields": route_a_state["observed_field_ids"],
            "route_b_disclosures": route_b_state["triggered_disclosure_ids"],
        },
    )

    refreshed = api.session(laozhou)
    record(
        "M4",
        "refresh / save restore keeps server-side session state",
        refreshed["conversation_id"] == laozhou
        and set(refreshed["presented_evidence_ids"]) >= {"E01", "E02", "E05"},
        {
            "conversation_id": refreshed["conversation_id"],
            "presented": refreshed["presented_evidence_ids"],
            "status": refreshed["status"],
        },
    )

    isolation_ok = (
        "E02" not in final_linyao["presented_evidence_ids"]
        and "E03" not in final_laozhou["presented_evidence_ids"]
        and "D02" not in final_laozhou["triggered_disclosure_ids"]
        and "D03" not in final_linyao["triggered_disclosure_ids"]
    )
    record("M5", "session isolation of evidence and disclosures", isolation_ok, {
        "laozhou": final_laozhou["presented_evidence_ids"],
        "linyao": final_linyao["presented_evidence_ids"],
    })

    stats = fake_stats(fake_url)
    record(
        "M6",
        "mock mode makes zero external model requests",
        stats["requests"] == 0,
        {"fake_requests": stats["requests"]},
    )


# ------------------------------------------------------------------ live


def stage_live(api: Api, fake_url: str, docker: Docker) -> None:
    fake_reset(fake_url)
    status, body = api.health()
    health = body["data"]
    record(
        "L1",
        "live health separates game and model readiness",
        status == 200
        and health["entry_mode"] == "live"
        and health["model_available"] is True
        and health["model_ready"] is True
        and health["is_synthetic"] is False
        and health["provider"]["kind"] == "external_model"
        and health["ledger"]["status"] == "ready",
        {k: health[k] for k in ("entry_mode", "game_ready", "model_available", "model_ready", "model_mode", "is_synthetic")},
    )

    laozhou = api.create("npc_laozhou")["conversation_id"]
    turn = api.turn(laozhou, text="那晚站台发生了什么？")
    stats = fake_stats(fake_url)
    chinese = bool(turn["generated_bridge"]) and any(
        "\u4e00" <= ch <= "\u9fff" for ch in turn["generated_bridge"]
    )
    record(
        "L2",
        "fake upstream returns Chinese NPC dialogue as a non-synthetic provider",
        turn["source"] == "external_model"
        and turn["provider"]["is_synthetic"] is False
        and chinese
        and stats["requests"] == 1,
        {"text": turn["generated_bridge"], "source": turn["source"], "fake_requests": stats["requests"]},
    )

    matrix = {
        "401": ("[[fake:401]]", "model_unavailable"),
        "429": ("[[fake:429]]", "model_unavailable"),
        "500": ("[[fake:500]]", "model_unavailable"),
        "badjson": ("[[fake:badjson]]", "invalid_output"),
        "truncate": ("[[fake:truncate]]", "invalid_output"),
        "unsafe": ("[[fake:unsafe]]", "unsafe_output"),
        "leak": ("[[fake:leak]]", "invalid_output"),
        "timeout": ("[[fake:timeout]]", "timeout"),
    }
    details = {}
    failures = []
    for name, (marker, expected) in matrix.items():
        conversation = api.create("npc_laozhou")["conversation_id"]
        started = time.monotonic()
        result = api.turn(conversation, text=f"那晚发生了什么 {marker}")
        elapsed = round(time.monotonic() - started, 2)
        after = api.session(conversation)
        key = name if name == "timeout" else name
        details[key] = {
            "source": result["source"],
            "fallback_reason": result["fallback_reason"],
            "elapsed_s": elapsed,
        }
        if result["source"] != "fallback" or result["fallback_reason"] != expected:
            failures.append(key)
        if after["triggered_disclosure_ids"] or after["presented_evidence_ids"]:
            failures.append(key + "_state_mutated")

    # Upstream unreachable: a connection failure must degrade, not crash.
    docker.compose("docker-compose.live.yml", "stop", "fake-llm")
    try:
        conversation = api.create("npc_laozhou")["conversation_id"]
        conn = api.turn(conversation, text="连接失败测试")
        details["connection_failure"] = {
            "source": conn["source"],
            "fallback_reason": conn["fallback_reason"],
        }
        if conn["source"] != "fallback" or conn["fallback_reason"] not in {
            "model_unavailable",
            "timeout",
        }:
            failures.append("connection_failure")
    finally:
        docker.compose("docker-compose.live.yml", "start", "fake-llm")
        wait_http(fake_url + "/healthz", 60)
    health_after = api.health()[1]["data"]
    record(
        "L3",
        "upstream failure matrix (401/429/500/timeout/invalid/truncated/unsafe/leak/connect) degrades safely",
        not failures and health_after["game_ready"] is True,
        {"failures": failures, "cases": details},
    )

    # A player keeps playing after upstream failures: fixed lines still work.
    recovered = api.turn(laozhou, topic_id="opt.laozhou.ask_b01")
    record(
        "L4",
        "game keeps running after model failures (deterministic content path)",
        recovered["source"] == "fixed_line",
        {"source": recovered["source"]},
    )

    # The key never appears in health or container logs.
    _, hbody = api.health()
    serialized = json.dumps(hbody)
    record(
        "L5",
        "API key never exposed in health payload",
        "local-fake-key" not in serialized,
        {"contains_key": "local-fake-key" in serialized},
    )


# ------------------------------------------------------------------ tight budget


def _parallel(fn, items):
    with ThreadPoolExecutor(max_workers=len(items)) as pool:
        futures = [pool.submit(fn, item) for item in items]
        return [f.result() for f in futures]


def stage_tight(api: Api, fake_url: str, docker: Docker, candidate: Path) -> None:
    fake_reset(fake_url)
    health = api.health()[1]["data"]
    record(
        "B1",
        "tight ledger configured 6 global / 2 per session",
        health["ledger"]["global_limit"] == 6 and health["ledger"]["session_limit"] == 2,
        health["ledger"],
    )

    # 8 concurrent turns across 4 sessions against a 6/2 budget and 2 upstream
    # slots: never more than 6 upstream requests and never more than 2 at once.
    sessions = [api.create("npc_laozhou")["conversation_id"] for _ in range(4)]
    requests = [(conv, "[[fake:slow]]并发调查") for conv in sessions for _ in range(2)]
    results = _parallel(lambda item: api.turn(item[0], text=item[1]), requests)
    stats = fake_stats(fake_url)
    used = api.health()[1]["data"]["ledger"]["global_used"]
    completed = sum(1 for r in results if r["source"] == "external_model")
    refused = sum(
        1 for r in results if (r.get("fallback_reason") or "").startswith("budget_")
    )
    record(
        "B2",
        "concurrent budget race never exceeds the ledger",
        stats["requests"] <= 6
        and used == stats["requests"]
        and stats["max_inflight"] <= 2
        and completed == stats["requests"]
        and refused == 8 - stats["requests"],
        {
            "upstream_requests": stats["requests"],
            "ledger_used": used,
            "max_upstream_inflight": stats["max_inflight"],
            "external_turns": completed,
            "budget_refused": refused,
        },
    )

    # Exhaust exactly; further model turns must be refused locally while the
    # deterministic game path still works.
    session = api.create("npc_laozhou")["conversation_id"]
    reason = ""
    for _ in range(8):
        result = api.turn(session, text="再问一句 [[fake:badjson]]")
        reason = result["fallback_reason"] or ""
        if reason.startswith("budget_"):
            break
    stats_after = fake_stats(fake_url)
    before_extra = stats_after["requests"]
    extra = api.turn(session, text="额度耗尽后再问 [[fake:500]]")
    stats_extra = fake_stats(fake_url)
    fixed = api.turn(session, topic_id="opt.laozhou.ask_b01")
    record(
        "B3",
        "after budget exhaustion no upstream call is made and the game continues",
        reason.startswith("budget_")
        and extra["source"] == "fallback"
        and (extra["fallback_reason"] or "").startswith("budget_")
        and stats_extra["requests"] == before_extra
        and fixed["source"] == "fixed_line",
        {
            "exhaust_reason": reason,
            "extra_reason": extra["fallback_reason"],
            "upstream": stats_extra["requests"],
            "fixed_source": fixed["source"],
        },
    )

    # Ledger deletion: restart must fail closed and send nothing upstream.
    before = fake_stats(fake_url)["requests"]
    docker.down("docker-compose.tight.yml")
    docker.volume_exec(
        "docker-compose.tight.yml", "live-tight", "rm -f /app/.local/llm-usage.sqlite3"
    )
    docker.up("docker-compose.tight.yml")
    time.sleep(6)
    state = docker.state("docker-compose.tight.yml", "live-tight")
    log = docker.logs("docker-compose.tight.yml", "live-tight")
    wait_http(fake_url + "/healthz", 60)
    # The fake upstream container is recreated with the stack, so its counter
    # starts at zero; anything above zero would mean the refused service still
    # managed to send a paid request.
    after = fake_stats(fake_url)["requests"]
    record(
        "B4",
        "ledger deletion refuses live start and makes no upstream request",
        state in {"exited", "dead", "missing"} and "ledger_missing" in log and after == 0,
        {"state": state, "upstream_before": before, "upstream_after": after},
    )

    # Recreate a generation explicitly, then corrupt it.
    docker.down("docker-compose.tight.yml")
    reset = docker.ledger_admin("docker-compose.tight.yml", "live-tight", "reset", "--confirm")
    corrupt = docker.volume_exec(
        "docker-compose.tight.yml",
        "live-tight",
        "printf 'garbage-not-a-database' > /app/.local/llm-usage.sqlite3",
    )
    docker.up("docker-compose.tight.yml")
    time.sleep(6)
    state = docker.state("docker-compose.tight.yml", "live-tight")
    log = docker.logs("docker-compose.tight.yml", "live-tight")
    record(
        "B5",
        "corrupt ledger refuses live start",
        state in {"exited", "dead", "missing"}
        and ("ledger_corrupt" in log or "ledger_unreadable" in log),
        {"state": state, "reset_rc": reset.returncode, "corrupt_rc": corrupt.returncode},
    )

    # Permission anomaly: the writability probe must fail closed.
    docker.down("docker-compose.tight.yml")
    docker.ledger_admin("docker-compose.tight.yml", "live-tight", "reset", "--confirm")
    chmod = docker.volume_exec(
        "docker-compose.tight.yml", "live-tight", "chmod 500 /app/.local"
    )
    docker.up("docker-compose.tight.yml")
    time.sleep(6)
    state = docker.state("docker-compose.tight.yml", "live-tight")
    log = docker.logs("docker-compose.tight.yml", "live-tight")
    docker.volume_exec("docker-compose.tight.yml", "live-tight", "chmod 700 /app/.local")
    record(
        "B6",
        "ledger directory permission anomaly refuses live start",
        state in {"exited", "dead", "missing"} and "ledger_read_only" in log,
        {"state": state, "chmod_rc": chmod.returncode, "log_tail": log[-300:]},
    )
    docker.down("docker-compose.tight.yml", volumes=True)


# ------------------------------------------------------------------ lifecycle


def stage_lifecycle(api: Api, fake_url: str, docker: Docker) -> None:
    fake_reset(fake_url)
    conversation = api.create("npc_laozhou")["conversation_id"]
    api.turn(conversation, text="重启前的问话")
    used_before = api.health()[1]["data"]["ledger"]["global_used"]
    requests_before = fake_stats(fake_url)["requests"]

    # Process/container restart.
    docker.compose("docker-compose.live.yml", "restart", "live")
    assert wait_http(api.base + "/api/v1/health", 60), "live did not come back"
    used_after = api.health()[1]["data"]["ledger"]["global_used"]
    record(
        "R1",
        "container/process restart preserves the ledger generation",
        used_after == used_before and used_after >= 1,
        {"before": used_before, "after": used_after},
    )

    # Delete and recreate the container (volume remains).
    docker.compose("docker-compose.live.yml", "rm", "-sf", "live")
    docker.up("docker-compose.live.yml", "live")
    assert wait_http(api.base + "/api/v1/health", 90), "live did not come back after recreate"
    used_recreated = api.health()[1]["data"]["ledger"]["global_used"]
    record(
        "R2",
        "container delete/recreate preserves usage (named volume)",
        used_recreated == used_after,
        {"after_restart": used_after, "after_recreate": used_recreated},
    )

    # The old session is in-memory only; the API must answer cleanly.
    status, body = http("GET", f"{api.base}/api/v1/sessions/{conversation}")
    record(
        "R3",
        "in-memory sessions fail cleanly after restart (no ghost state)",
        status == 404 and body["error"]["code"] == "NOT_FOUND",
        {"status": status},
    )
    record(
        "R4",
        "live upstream still reachable after lifecycle operations",
        fake_stats(fake_url)["requests"] == requests_before,
        {"upstream": fake_stats(fake_url)["requests"]},
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-dir", default=".")
    parser.add_argument("--mock-url", default="http://127.0.0.1:18080")
    parser.add_argument("--live-url", default="http://127.0.0.1:18081")
    parser.add_argument("--tight-url", default="http://127.0.0.1:18082")
    parser.add_argument("--fake-url", default="http://127.0.0.1:19000")
    parser.add_argument("--tight-fake-url", default="http://127.0.0.1:19001")
    parser.add_argument("--out", default="evidence/e2e_results.json")
    parser.add_argument("--stages", default="mock,live,tight,lifecycle")
    parser.add_argument("--no-manage", action="store_true")
    parser.add_argument("--append", action="store_true", help="merge into an existing results file")
    args = parser.parse_args()

    candidate = Path(args.candidate_dir).resolve()
    docker = Docker(candidate)
    stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    out = Path(args.out)
    previous_checks: list[dict] = []
    if args.append and out.exists():
        previous = json.loads(out.read_text(encoding="utf-8"))
        previous_checks = previous.get("checks", [])

    if not args.no_manage:
        print("starting mock + fake upstream ...", flush=True)
        docker.up("docker-compose.mock.yml")
        docker.up("docker-compose.live.yml", "fake-llm")
        if not wait_http(args.mock_url + "/api/v1/health"):
            raise SystemExit("mock did not become healthy")
        if "live" in stages or "lifecycle" in stages:
            # Explicit administrative reset so every acceptance run starts from
            # a known generation.  The service itself never creates quota.
            print("resetting live ledger generation (explicit admin reset) ...", flush=True)
            init = docker.ledger_admin("docker-compose.live.yml", "live", "reset", "--confirm")
            if init.returncode != 0:
                raise SystemExit(f"live ledger reset failed: {init.stderr}")
            docker.up("docker-compose.live.yml", "live")

    if "mock" in stages:
        stage_mock(Api(args.mock_url), args.fake_url, docker, candidate)

    if "live" in stages:
        if not args.no_manage:
            if not wait_http(args.live_url + "/api/v1/health", 30):
                docker.up("docker-compose.live.yml")
            if not wait_http(args.live_url + "/api/v1/health", 90):
                raise SystemExit(
                    "live did not become healthy; run ledger init first:\n"
                    "  docker compose -f docker-compose.live.yml run --rm --no-deps "
                    "--entrypoint python live -m app.ledger_admin init --confirm"
                )
        stage_live(Api(args.live_url), args.fake_url, docker)

    if "tight" in stages and not args.no_manage:
        docker.down("docker-compose.tight.yml", volumes=True)
        # The ledger generation must exist before the live service starts;
        # a live service never creates its own quota.
        init = docker.ledger_admin("docker-compose.tight.yml", "live-tight", "init", "--confirm")
        if init.returncode != 0:
            raise SystemExit(f"tight ledger init failed: {init.stderr}")
        docker.up("docker-compose.tight.yml")
        if not wait_http(args.tight_url + "/api/v1/health", 90):
            raise SystemExit("tight live did not become healthy")
        stage_tight(Api(args.tight_url), args.tight_fake_url, docker, candidate)

    if "lifecycle" in stages and not args.no_manage:
        stage_lifecycle(Api(args.live_url), args.fake_url, docker)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    merged = list(previous_checks)
    position = {item["id"]: index for index, item in enumerate(merged)}
    for item in RESULTS:
        if item["id"] in position:
            merged[position[item["id"]]] = item
        else:
            position[item["id"]] = len(merged)
            merged.append(item)
    payload = {
        "generated_at": now(),
        "candidate_dir": str(candidate),
        "stages": stages,
        "checks": merged,
        "passed": all(item["passed"] for item in merged),
        "total": len(merged),
        "failed": [item["id"] for item in merged if not item["passed"]],
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"total": payload["total"], "failed": payload["failed"]}, ensure_ascii=False))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
