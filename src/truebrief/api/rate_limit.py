"""
Rate Limiting — api/rate_limit.py

Shared slowapi Limiter instance used across all API routers.
Import `limiter` to apply @limiter.limit() decorators on route handlers.

Storage:
  Production (REDIS_URL set): Redis-backed distributed counter.
  Dev / CI  (no Redis):        In-memory counter (resets on process restart).
"""

import os
import logging

from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Storage setup
# ---------------------------------------------------------------------------
# slowapi accepts a storage_uri string directly; falls back to memory if empty.
_redis_url: str = os.getenv("REDIS_URL", "")

if _redis_url:
    _storage_uri = _redis_url
    logger.info("Rate limiter: using Redis storage (%s)", _redis_url[:30])
else:
    _storage_uri = "memory://"
    logger.info("Rate limiter: using in-memory storage (dev mode)")

# ---------------------------------------------------------------------------
# Limiter singleton
# ---------------------------------------------------------------------------
# key_func: identify clients by their IP address.
# X-Forwarded-For is read automatically by get_remote_address when present
# (needed for Railway / reverse-proxy deployments).
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_storage_uri,
    default_limits=["200/minute"],
)
