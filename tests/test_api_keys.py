"""
Developer API product tests (2026-07-10).

Covers key generation/hashing, API-key verification, per-user quota
enforcement, and the public-API auth dependency — all against a fake DB
(no Supabase calls).
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from truebrief.apikeys import service
from truebrief.apikeys.service import (
    ApiKeyIdentity,
    daily_limit_for_tier,
    generate_key,
    hash_key,
    meter_and_enforce,
    verify_api_key,
)


# ── Key material ──────────────────────────────────────────────────────────────

class TestKeyGeneration:
    def test_key_format(self):
        full, key_hash, prefix = generate_key()
        assert full.startswith("tb_live_")
        assert len(full) > 40                      # 256 bits of entropy
        assert key_hash == hash_key(full)
        assert len(key_hash) == 64                 # sha256 hex
        assert full.startswith(prefix)
        assert len(prefix) == service.PREFIX_DISPLAY_LEN

    def test_keys_are_unique(self):
        keys = {generate_key()[0] for _ in range(50)}
        assert len(keys) == 50

    def test_hash_is_deterministic(self):
        assert hash_key("tb_live_abc") == hash_key("tb_live_abc")
        assert hash_key("tb_live_abc") != hash_key("tb_live_abd")


# ── Fake supabase client ──────────────────────────────────────────────────────

class _FakeQuery:
    """Chainable stub: .table(x).select().eq()...execute() → canned response."""

    def __init__(self, data):
        self._data = data

    def __getattr__(self, name):
        # Any chained method returns self; execute() returns the response.
        if name == "execute":
            return lambda: SimpleNamespace(data=self._data)
        return lambda *a, **k: self


class _FakeDB:
    def __init__(self, tables: dict, rpc_result=None):
        self.tables = tables
        self.rpc_result = rpc_result
        self.rpc_calls = []

    def table(self, name):
        return _FakeQuery(self.tables.get(name, []))

    def rpc(self, fn, params):
        self.rpc_calls.append((fn, params))
        return _FakeQuery(self.rpc_result)


# ── verify_api_key ────────────────────────────────────────────────────────────

class TestVerifyApiKey:
    def _db_with_key(self, full_key, revoked_at=None, tier="pro"):
        return _FakeDB({
            "api_keys": [{"id": "k1", "user_id": "u1", "revoked_at": revoked_at}],
            "users": [{"id": "u1", "email": "dev@x.com"}],
            "user_subscriptions": [{"tier": tier}],
        })

    def test_valid_key_resolves_identity(self):
        full, _, _ = generate_key()
        ident = verify_api_key(self._db_with_key(full), full)
        assert ident.user_id == "u1"
        assert ident.tier == "pro"

    def test_rejects_wrong_prefix(self):
        with pytest.raises(HTTPException) as ei:
            verify_api_key(_FakeDB({}), "sk_not_ours_123")
        assert ei.value.status_code == 401

    def test_rejects_unknown_key(self):
        db = _FakeDB({"api_keys": []})
        with pytest.raises(HTTPException) as ei:
            verify_api_key(db, "tb_live_unknownunknownunknown")
        assert ei.value.status_code == 401

    def test_rejects_revoked_key(self):
        full, _, _ = generate_key()
        db = self._db_with_key(full, revoked_at="2026-07-01T00:00:00Z")
        with pytest.raises(HTTPException) as ei:
            verify_api_key(db, full)
        assert ei.value.status_code == 401
        assert "revoked" in ei.value.detail.lower()

    def test_missing_subscription_defaults_to_free(self):
        full, _, _ = generate_key()
        db = _FakeDB({
            "api_keys": [{"id": "k1", "user_id": "u1", "revoked_at": None}],
            "users": [{"id": "u1", "email": "dev@x.com"}],
            "user_subscriptions": [],
        })
        assert verify_api_key(db, full).tier == "free"


# ── Quota enforcement ─────────────────────────────────────────────────────────

class TestQuota:
    def _ident(self, tier):
        return ApiKeyIdentity(key_id="k1", user_id="u1", user_email="e", tier=tier)

    def test_free_tier_has_no_api_access(self):
        db = _FakeDB({}, rpc_result=1)
        with pytest.raises(HTTPException) as ei:
            meter_and_enforce(db, self._ident("free"))
        assert ei.value.status_code == 402
        assert db.rpc_calls == []          # denied before any metering

    def test_pro_within_quota_passes(self):
        db = _FakeDB({}, rpc_result=100)
        meter_and_enforce(db, self._ident("pro"))  # should not raise
        assert len(db.rpc_calls) == 1

    def test_pro_over_quota_raises_429(self):
        db = _FakeDB({}, rpc_result=daily_limit_for_tier("pro") + 1)
        with pytest.raises(HTTPException) as ei:
            meter_and_enforce(db, self._ident("pro"))
        assert ei.value.status_code == 429

    def test_metering_failure_fails_open(self):
        db = _FakeDB({}, rpc_result=None)
        db.rpc = MagicMock(side_effect=RuntimeError("db down"))
        meter_and_enforce(db, self._ident("pro"))  # must NOT raise

    def test_tier_limits_sane(self):
        assert daily_limit_for_tier("free") == 0
        assert daily_limit_for_tier("pro") > 0
        assert daily_limit_for_tier("power") > daily_limit_for_tier("pro")
        assert daily_limit_for_tier("garbage") == 0   # unknown → free


# ── Public API auth dependency ────────────────────────────────────────────────

class TestAuthDependency:
    @pytest.mark.anyio
    async def test_missing_key_401(self):
        from truebrief.api.public_routes import get_api_identity
        with pytest.raises(HTTPException) as ei:
            await get_api_identity(authorization=None, x_api_key=None)
        assert ei.value.status_code == 401

    @pytest.mark.anyio
    async def test_bearer_and_header_forms_accepted(self, monkeypatch):
        from truebrief.api import public_routes
        seen = {}

        def fake_verify(db, key):
            seen["key"] = key
            return ApiKeyIdentity(key_id="k", user_id="u", user_email="e", tier="pro")

        monkeypatch.setattr(public_routes, "verify_api_key", fake_verify)
        monkeypatch.setattr(public_routes, "get_supabase", lambda: None)

        await public_routes.get_api_identity(authorization="Bearer tb_live_X", x_api_key=None)
        assert seen["key"] == "tb_live_X"
        await public_routes.get_api_identity(authorization=None, x_api_key="tb_live_Y")
        assert seen["key"] == "tb_live_Y"
