"""Client-address resolution that never trusts a client-supplied header.

``X-Forwarded-For`` is only honoured when the *socket peer* is inside one of
the configured, verified proxy networks.  The chain is then walked from right
to left, skipping trusted proxies; the first untrusted hop is the client.
Anything unparseable collapses to ``unknown`` instead of being used as a key.
"""

from __future__ import annotations

import ipaddress
from functools import lru_cache


@lru_cache(maxsize=32)
def _networks(cidrs: tuple[str, ...]) -> tuple[ipaddress._BaseNetwork, ...]:
    return tuple(ipaddress.ip_network(cidr, strict=False) for cidr in cidrs)


def _in_networks(address: ipaddress._BaseAddress, cidrs: tuple[str, ...]) -> bool:
    return any(address in network for network in _networks(cidrs))


def resolve_client_ip(
    peer: str | None,
    forwarded_for: str | None,
    trusted_proxy_cidrs: tuple[str, ...],
) -> str:
    peer_text = (peer or "").strip()
    try:
        peer_ip = ipaddress.ip_address(peer_text)
    except ValueError:
        return "unknown"

    if not trusted_proxy_cidrs or not _in_networks(peer_ip, trusted_proxy_cidrs):
        # Safe default: the socket peer is the client, header is ignored.
        return str(peer_ip)

    hops = [hop.strip() for hop in (forwarded_for or "").split(",") if hop.strip()]
    for hop in reversed(hops):
        try:
            hop_ip = ipaddress.ip_address(hop)
        except ValueError:
            return "unknown"
        if _in_networks(hop_ip, trusted_proxy_cidrs):
            continue
        return str(hop_ip)
    # Every hop is a trusted proxy (or the header is empty): fall back to the
    # peer, which is itself trusted, and never to a client-controlled value.
    return str(peer_ip)
