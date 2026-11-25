"""M5-C-A production entry point.

``uvicorn app.entry:app`` is the only supported process entry.  It re-exports
the application built from ``Settings.from_env()`` in :mod:`app.main`.

Failure behaviour is deliberately boring: if ``APP_ENTRY_MODE=live`` is set
without valid provider credentials or without a usable durable ledger, import
fails, uvicorn exits non-zero, and the container never starts accepting
requests.  There is no "start degraded and hope" path for live mode.  Mock
mode always starts and never constructs an external model client.
"""

from __future__ import annotations

from .main import app

__all__ = ["app"]
