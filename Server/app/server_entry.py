"""The single, explicit server entrypoint for this service.

Why this module exists
----------------------
Uvicorn can rewrite ``scope["client"]`` from ``X-Forwarded-For`` when
``--proxy-headers`` is enabled, which is **the default** (``forwarded_allow_ips``
defaults to ``127.0.0.1``).  If Uvicorn rewrote the client address *and*
``app.network.resolve_client_ip`` parsed the same header again, there would be
two owners of one security decision, and any client able to reach the container
through loopback could pick its own rate-limit bucket.

M5-C-A-R1 therefore makes a single, documented choice:

* the **application** (``app.network.resolve_client_ip``) is the only layer that
  derives the client address, and it only honours ``X-Forwarded-For`` for hops
  inside ``TRUSTED_PROXY_CIDRS``;
* Uvicorn's own header rewriting is disabled here (``proxy_headers=False``), so
  a forged ``X-Forwarded-For`` can never reach the app as a trusted peer.

Deploy with ``python -m app.server_entry`` instead of ``uvicorn app.main:app``.
Passing ``--proxy-headers`` on the command line would re-enable the second
owner and must not be done.

The ModelScope proxy topology is still unconfirmed, so ``TRUSTED_PROXY_CIDRS``
stays empty by default and every forwarded header is ignored.
"""

from __future__ import annotations

import os

import uvicorn

HOST = "0.0.0.0"
DEFAULT_PORT = 7860
# Security-relevant: see the module docstring.  Exported for tests.
PROXY_HEADERS = False
FORWARDED_ALLOW_IPS = ""
WORKERS = 1


def _port() -> int:
    raw = os.environ.get("PORT") or os.environ.get("UVICORN_PORT") or ""
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_PORT
    return value if 1 <= value <= 65535 else DEFAULT_PORT


def build_config() -> uvicorn.Config:
    """Return the exact Uvicorn configuration used in every deployment."""

    return uvicorn.Config(
        "app.entry:app",
        host=HOST,
        port=_port(),
        workers=WORKERS,
        # Single owner of client-address resolution: the application.
        proxy_headers=PROXY_HEADERS,
        forwarded_allow_ips=FORWARDED_ALLOW_IPS,
        server_header=False,
    )


def main() -> None:
    uvicorn.Server(build_config()).run()


if __name__ == "__main__":  # pragma: no cover - process entrypoint
    main()
