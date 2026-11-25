"""Explicit administration of the durable model-request ledger.

There is deliberately no automatic creation or reset at service startup: a
restart, a lost volume or a truncated file must never hand out fresh quota.

Usage (inside the container or in a local shell)::

    python -m app.ledger_admin init  --confirm
    python -m app.ledger_admin reset --confirm
    python -m app.ledger_admin verify

``init`` creates the first ledger generation.  ``reset`` rotates the epoch and
starts a new generation with fresh quota -- an auditable administrative act.
``verify`` only reads and reports; it never repairs or recreates anything.

Exit codes: 0 success, 2 refused/exists, 3 ledger unusable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .budget import LedgerUnavailable, RequestBudget
from .config import DEFAULT_LEDGER_EPOCH_PATH, DEFAULT_USAGE_PATH


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name, "").strip()
    return Path(raw).expanduser() if raw else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return int(raw)


def _paths(args: argparse.Namespace) -> tuple[Path, Path]:
    path = Path(args.path).expanduser() if args.path else _env_path("LLM_USAGE_PATH", DEFAULT_USAGE_PATH)
    epoch = (
        Path(args.epoch_path).expanduser()
        if args.epoch_path
        else _env_path("LLM_LEDGER_EPOCH_PATH", DEFAULT_LEDGER_EPOCH_PATH)
    )
    return path, epoch


def _limits(args: argparse.Namespace) -> tuple[int, int, int]:
    limit = args.limit or _env_int("LLM_REQUEST_LIMIT", 30)
    per_session = args.per_session or _env_int("LLM_REQUEST_LIMIT_PER_SESSION", 8)
    token_limit = args.token_limit or _env_int("LLM_TOKEN_LIMIT", 60000)
    if per_session >= limit:
        raise SystemExit(
            "refused: LLM_REQUEST_LIMIT_PER_SESSION must be smaller than "
            "LLM_REQUEST_LIMIT"
        )
    if token_limit < 1000:
        raise SystemExit("refused: LLM_TOKEN_LIMIT must be at least 1000")
    return limit, per_session, token_limit


def _print(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _status(path: Path, epoch: Path) -> dict:
    return {
        "ledger_path": str(path),
        "epoch_path": str(epoch),
        "ledger_exists": path.exists(),
        "epoch_exists": epoch.exists(),
    }


def command_init(args: argparse.Namespace) -> int:
    path, epoch = _paths(args)
    limit, per_session, token_limit = _limits(args)
    try:
        budget = RequestBudget.initialize(
            path,
            epoch,
            limit=limit,
            per_session_limit=per_session,
            token_limit=token_limit,
        )
    except FileExistsError:
        print(
            "refused: a ledger or epoch file already exists; "
            "use `reset --confirm` to start a new quota generation",
            file=sys.stderr,
        )
        return 2
    except OSError as exc:
        print(f"refused: cannot initialize ledger ({type(exc).__name__})", file=sys.stderr)
        return 3
    result = {
        "action": "init",
        "status": "created",
        **_status(path, epoch),
        "epoch_fingerprint": budget.epoch[:12],
        "global_limit": limit,
        "session_limit": per_session,
        "token_limit": token_limit,
        "global_used": 0,
    }
    budget.close()
    _print(result)
    return 0


def command_reset(args: argparse.Namespace) -> int:
    path, epoch = _paths(args)
    limit, per_session, token_limit = _limits(args)
    try:
        budget = RequestBudget.initialize(
            path,
            epoch,
            limit=limit,
            per_session_limit=per_session,
            token_limit=token_limit,
            reset=True,
        )
    except OSError as exc:
        print(f"refused: cannot reset ledger ({type(exc).__name__})", file=sys.stderr)
        return 3
    result = {
        "action": "reset",
        "status": "rotated",
        **_status(path, epoch),
        "epoch_fingerprint": budget.epoch[:12],
        "global_limit": limit,
        "session_limit": per_session,
        "global_used": 0,
    }
    budget.close()
    _print(result)
    return 0


def command_verify(args: argparse.Namespace) -> int:
    path, epoch = _paths(args)
    limit, per_session, token_limit = _limits(args)
    try:
        budget = RequestBudget.load(
            path,
            epoch,
            limit=limit,
            per_session_limit=per_session,
            token_limit=token_limit,
        )
    except LedgerUnavailable as exc:
        _print(
            {
                "action": "verify",
                "status": "unusable",
                "reason": exc.reason,
                "detail": exc.detail,
                **_status(path, epoch),
            }
        )
        return 3
    usage = budget.usage()
    budget.close()
    _print({"action": "verify", "status": usage["status"], **usage, **_status(path, epoch)})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.ledger_admin",
        description="Explicit model-budget ledger administration (M5-C-A).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def common(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--path", help="SQLite ledger path (default LLM_USAGE_PATH)")
        sub.add_argument("--epoch-path", help="independent epoch sentinel path")
        sub.add_argument("--limit", type=int, help="global lifetime request limit")
        sub.add_argument("--per-session", type=int, help="per-session request limit")
        sub.add_argument(
            "--token-limit",
            type=int,
            help="lifetime token budget (default LLM_TOKEN_LIMIT)",
        )
        sub.add_argument(
            "--confirm",
            action="store_true",
            help="required for init/reset: acknowledges an explicit quota operation",
        )

    init = subparsers.add_parser("init", help="create the first ledger generation")
    common(init)
    init.set_defaults(func=command_init)

    reset = subparsers.add_parser("reset", help="rotate epoch and grant fresh quota")
    common(reset)
    reset.set_defaults(func=command_reset)

    verify = subparsers.add_parser("verify", help="read-only ledger verification")
    common(verify)
    verify.set_defaults(func=command_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command in {"init", "reset"} and not args.confirm:
        print(
            "refused: init/reset change the paid-model quota and require --confirm",
            file=sys.stderr,
        )
        return 2
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover - CLI
    raise SystemExit(main())
