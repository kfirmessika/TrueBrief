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
