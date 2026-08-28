"""
Simple Redis response cache for read-heavy API endpoints.

Falls back to no-cache (pass-through) when Redis is unavailable, so the app
stays functional in dev without Redis and during Redis outages.
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_redis_client = None
_redis_unavailable = False


def _get_redis():
    global _redis_client, _redis_unavailable
    if _redis_unavailable:
        return None
    if _redis_client is not None:
        return _redis_client
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        _redis_unavailable = True
        return None
    try:
        import redis
        _redis_client = redis.from_url(url, decode_responses=True, socket_connect_timeout=1)
        _redis_client.ping()
        logger.info("API cache: Redis connected")
        return _redis_client
    except Exception as e:
        logger.warning("API cache: Redis unavailable (%s) — caching disabled", e)
        _redis_unavailable = True
        return None


def cache_get(key: str) -> Any | None:
    r = _get_redis()
    if r is None:
        return None
    try:
        raw = r.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


def cache_set(key: str, value: Any, ttl: int = 60) -> None:
    r = _get_redis()
    if r is None:
        return
    try:
        r.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        pass


def cache_delete(*keys: str) -> None:
    r = _get_redis()
    if r is None:
        return
    try:
        r.delete(*keys)
    except Exception:
        pass


def cache_delete_pattern(pattern: str) -> None:
    r = _get_redis()
    if r is None:
        return
    try:
        keys = r.keys(pattern)
        if keys:
            r.delete(*keys)
    except Exception:
        pass


# ── Automation freeze flag ─────────────────────────────────────────────────────
# Stored in Redis (key "automation:frozen", value "1") so it survives worker
# restarts and is visible across all processes (API + Beat + worker).
# Falls back to an in-process module variable when Redis is unavailable (dev
# without Redis — works fine, just doesn't survive a restart in that mode).

_local_frozen: bool = False
_FREEZE_KEY = "automation:frozen"


def automation_is_frozen() -> bool:
    r = _get_redis()
    if r is None:
        return _local_frozen
    try:
        return r.get(_FREEZE_KEY) == "1"
    except Exception:
        return _local_frozen


def automation_set_frozen(frozen: bool) -> None:
    global _local_frozen
    _local_frozen = frozen
    r = _get_redis()
    if r is None:
        return
    try:
        if frozen:
            r.set(_FREEZE_KEY, "1")
        else:
            r.delete(_FREEZE_KEY)
    except Exception:
        pass
