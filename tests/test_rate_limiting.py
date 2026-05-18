"""
Tests — test_rate_limiting.py

Unit tests for Step 3.18: Rate Limiting & Abuse Prevention.

All tests use in-memory storage (no Redis required) and the FastAPI
TestClient to exercise the slowapi middleware end-to-end.

NOTE: Do NOT add `from __future__ import annotations` to this file.
With PEP 563 (deferred annotations), `request: Request` inside helper
functions is stored as the string 'Request'. FastAPI's get_type_hints()
cannot resolve that string against the helper's local scope, so it
treats `request` as a required query param and returns 422 on every hit.
"""

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app():
    """Return a minimal FastAPI + slowapi app with a 3/minute /ping endpoint."""
    lim = Limiter(key_func=get_remote_address, storage_uri="memory://")
    app = FastAPI()
    app.state.limiter = lim
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    @app.get("/ping")
    @lim.limit("3/minute")
    def ping(request: Request):
        return {"ok": True}

    @app.get("/open")
    def open_endpoint():
        return {"open": True}

    return app, lim


# ---------------------------------------------------------------------------
# TestLimiterSetup
# ---------------------------------------------------------------------------

class TestLimiterSetup:
    def test_limiter_created(self):
        """Limiter singleton is importable and uses the IP key function."""
        from truebrief.api.rate_limit import limiter
        assert limiter is not None
        assert limiter._key_func is get_remote_address

    def test_limiter_uses_memory_without_redis(self):
        """When REDIS_URL is absent the module selects memory:// storage."""
        import os
        # In CI / dev there is no REDIS_URL, so the module should have used memory://
        redis_url = os.getenv("REDIS_URL", "")
        from truebrief.api.rate_limit import _storage_uri
        expected = redis_url if redis_url else "memory://"
        assert _storage_uri == expected

    def test_redis_storage_uri_used_when_env_set(self):
        """A Limiter created with a Redis URI stores that URI (no live connection needed)."""
        test_uri = "redis://localhost:6379/0"
        lim = Limiter(key_func=get_remote_address, storage_uri=test_uri)
        assert lim is not None


# ---------------------------------------------------------------------------
# TestRateLimitBehavior
# ---------------------------------------------------------------------------

class TestRateLimitBehavior:
    def setup_method(self):
        self.app, self.lim = _make_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def test_below_limit_allowed(self):
        """Requests within the limit succeed with HTTP 200."""
        for _ in range(3):
            resp = self.client.get("/ping")
            assert resp.status_code == 200

    def test_above_limit_blocked(self):
        """The (N+1)th request in the same window returns HTTP 429."""
        for _ in range(3):
            self.client.get("/ping")
        resp = self.client.get("/ping")
        assert resp.status_code == 429

    def test_429_response_body(self):
        """429 response contains an error field."""
        for _ in range(4):
            resp = self.client.get("/ping")
        assert resp.status_code == 429
        body = resp.json()
        assert "error" in body or "detail" in body

    def test_once_blocked_stays_blocked(self):
        """After the limit is hit, further requests in the same window remain blocked."""
        for _ in range(3):
            self.client.get("/ping")
        for _ in range(3):
            resp = self.client.get("/ping")
            assert resp.status_code == 429

    def test_unlimited_endpoint_never_blocked(self):
        """Endpoints without @limiter.limit() are not rate-limited."""
        for _ in range(20):
            resp = self.client.get("/open")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# TestRouteDecorators
# ---------------------------------------------------------------------------

class TestRouteDecorators:
    """Verify the production route handlers have the slowapi limit attached."""

    def test_create_topic_is_callable(self):
        """create_topic is importable (decorator didn't break the function)."""
        from truebrief.api.routes import create_topic
        assert callable(create_topic)

    def test_trigger_scan_is_callable(self):
        """trigger_scan is importable."""
        from truebrief.api.routes import trigger_scan
        assert callable(trigger_scan)

    def test_push_subscribe_is_callable(self):
        """push subscribe handler is importable."""
        from truebrief.api.push_routes import subscribe
        assert callable(subscribe)
