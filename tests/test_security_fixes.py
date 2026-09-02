"""
Security regression tests (2026-07-07 audit).

Covers the fixes for:
  - fail-open admin gates (_is_admin, _require_founder)
  - SSRF guard on the article fetcher (url_guard)
  - raw_query length/control-char bound
  - billing redirect open-redirect guard
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest


# ── Admin gates fail CLOSED ───────────────────────────────────────────────────

class _U:
    def __init__(self, uid="u1", email="x@y.com"):
        self.id = uid
        self.email = email


def test_is_admin_fails_closed_when_unset(monkeypatch):
    from truebrief.api import routes
    monkeypatch.delenv("ADMIN_USER_IDS", raising=False)
    monkeypatch.setattr(routes.settings, "ADMIN_EMAILS", "")
    monkeypatch.setattr(routes.settings, "FOUNDER_EMAIL", "")
    assert routes._is_admin(_U()) is False


def test_is_admin_allows_listed_email(monkeypatch):
    from truebrief.api import routes
    monkeypatch.delenv("ADMIN_USER_IDS", raising=False)
    monkeypatch.setattr(routes.settings, "ADMIN_EMAILS", "boss@co.com")
    monkeypatch.setattr(routes.settings, "FOUNDER_EMAIL", "")
    assert routes._is_admin(_U(email="boss@co.com")) is True
    assert routes._is_admin(_U(email="rando@co.com")) is False


def test_require_founder_fails_closed_when_unset(monkeypatch):
    from truebrief.api import routes
    from fastapi import HTTPException
    monkeypatch.setattr(routes.settings, "FOUNDER_EMAIL", "")
    with pytest.raises(HTTPException) as ei:
        routes._require_founder(_U())
    assert ei.value.status_code == 403


# ── SSRF guard ────────────────────────────────────────────────────────────────

class TestUrlGuard:
    def test_blocks_non_http_scheme(self):
        from truebrief.collector.url_guard import is_public_url
        assert is_public_url("file:///etc/passwd") is False
        assert is_public_url("gopher://x") is False

    def test_blocks_loopback_and_metadata(self):
        from truebrief.collector.url_guard import is_public_url
        assert is_public_url("http://127.0.0.1/") is False
        assert is_public_url("http://localhost/") is False
        assert is_public_url("http://169.254.169.254/latest/meta-data/") is False

    def test_blocks_private_ranges(self):
        from truebrief.collector.url_guard import is_public_url
        assert is_public_url("http://10.0.0.5/") is False
        assert is_public_url("http://192.168.1.1/") is False
        assert is_public_url("http://172.16.0.1/") is False

    def test_allows_public_host(self):
        from truebrief.collector.url_guard import is_public_url
        # reuters.com resolves to public IPs
        assert is_public_url("https://www.reuters.com/world/") is True


# ── raw_query bound ───────────────────────────────────────────────────────────

class TestRawQueryBound:
    def test_rejects_too_long(self):
        from truebrief.api.routes import TopicCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            TopicCreate(raw_query="x" * 201)

    def test_rejects_empty_after_strip(self):
        from truebrief.api.routes import TopicCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            TopicCreate(raw_query="   ")

    def test_strips_control_chars(self):
        from truebrief.api.routes import TopicCreate
        t = TopicCreate(raw_query="Iran\x00 war\x07")
        assert t.raw_query == "Iran war"


# ── Billing open-redirect guard ───────────────────────────────────────────────

class TestBillingRedirectGuard:
    def test_rejects_foreign_origin(self, monkeypatch):
        from truebrief.billing import billing_routes
        from fastapi import HTTPException
        monkeypatch.setenv("FRONTEND_URL", "https://app.truebrief.com")
        with pytest.raises(HTTPException):
            billing_routes._require_same_origin("https://evil.com/steal", "success_url")

    def test_allows_own_origin(self, monkeypatch):
        from truebrief.billing import billing_routes
        monkeypatch.setenv("FRONTEND_URL", "https://app.truebrief.com")
        # should not raise
        billing_routes._require_same_origin("https://app.truebrief.com/settings", "success_url")


# ── Interactive API docs are closed unless explicitly enabled ─────────────────

class TestApiDocsGating:
    """`/docs`, `/redoc`, `/openapi.json` must be OFF unless ENABLE_API_DOCS is
    explicitly truthy — not tied to ENV (prod ran ENV=development and leaked them)."""

    def test_closed_when_unset(self):
        from truebrief.api.server import _docs_flag_enabled
        assert _docs_flag_enabled(None) is False
        assert _docs_flag_enabled("") is False

    def test_closed_on_dev_ish_or_garbage_values(self):
        from truebrief.api.server import _docs_flag_enabled
        for v in ("development", "dev", "maybe", "0", "false", "off"):
            assert _docs_flag_enabled(v) is False

    def test_open_only_on_explicit_true(self):
        from truebrief.api.server import _docs_flag_enabled
        for v in ("1", "true", "YES", " on "):
            assert _docs_flag_enabled(v) is True
