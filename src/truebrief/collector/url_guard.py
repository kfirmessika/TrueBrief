"""
url_guard.py — SSRF protection for the article fetcher.

Article URLs come from third-party search results (Tavily/Brave/RSS/Google News)
and are fetched server-side. Without a guard, a result URL — or a redirect from
one — pointing at a private/loopback/link-local host (e.g. the cloud metadata
endpoint 169.254.169.254, or an internal RFC-1918 service) would be fetched by
our server and its body pulled into the pipeline.

Usage:
  - is_public_url(url): reject non-http(s) schemes and hosts that resolve to
    private/loopback/link-local/reserved IPs before the FIRST request.
  - A safe httpx event hook re-validates each redirect hop's host, closing the
    "public URL 302-redirects to 169.254.169.254" bypass.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


def _ip_is_blocked(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # unpar. can't verify → block
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _host_is_blocked(host: str) -> bool:
    """True if the host resolves to (or is) a private/loopback/link-local IP."""
    if not host:
        return True
    # Direct IP literal?
    try:
        ipaddress.ip_address(host)
        return _ip_is_blocked(host)
    except ValueError:
        pass
    # Hostname → resolve ALL addresses; block if ANY is internal (DNS-rebind guard).
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError):
        return True  # can't resolve → block
    for info in infos:
        ip_str = info[4][0]
        if _ip_is_blocked(ip_str):
            return True
    return False


def is_public_url(url: str) -> bool:
    """Return True only if url is http(s) and its host is not internal."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname or ""
    if _host_is_blocked(host):
        logger.warning("SSRF guard: blocked non-public host in URL: %s", url)
        return False
    return True


def _redirect_guard(response: httpx.Response) -> None:
    """httpx event hook: re-validate the host of every redirect target.

    A public URL that 3xx-redirects to an internal host would otherwise be
    followed. We inspect the Location header before httpx follows it.
    """
    if response.is_redirect:
        location = response.headers.get("location")
        if location:
            target = str(response.url.join(location))
            if not is_public_url(target):
                raise httpx.RequestError(
                    f"SSRF guard: blocked redirect to non-public host: {target}"
                )


def safe_client(**kwargs) -> httpx.Client:
    """httpx.Client with the redirect SSRF guard installed.

    Callers must still call is_public_url() on the INITIAL url before .get().
    """
    hooks = kwargs.pop("event_hooks", {})
    resp_hooks = list(hooks.get("response", []))
    resp_hooks.append(_redirect_guard)
    hooks["response"] = resp_hooks
    return httpx.Client(event_hooks=hooks, **kwargs)
