"""
Tests — test_spend_guard.py

Unit tests for billing/spend_guard.py: the per-account daily scan cap (Redis
counter) and the global daily spend circuit-breaker (llm_cost_by_day RPC).

Both guardrails must FAIL OPEN — a broken Redis or a missing RPC never blocks a
scan.
"""

import datetime

import pytest
from fastapi import HTTPException

from truebrief.billing import spend_guard


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _FakeRedis:
    def __init__(self):
        self.store: dict[str, int] = {}
        self.expires: dict[str, int] = {}

    def incr(self, key: str) -> int:
        self.store[key] = self.store.get(key, 0) + 1
        return self.store[key]

    def expire(self, key: str, ttl: int) -> None:
        self.expires[key] = ttl


class _BrokenRedis:
    def incr(self, key):
        raise RuntimeError("redis down")

    def expire(self, key, ttl):
        raise RuntimeError("redis down")


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def execute(self):
        return type("R", (), {"data": self._rows})()


class _FakeDB:
    def __init__(self, rows=None, raise_exc=None):
        self._rows = rows or []
        self._raise = raise_exc

    def rpc(self, name, params):
        assert name == "llm_cost_by_day"
        if self._raise:
            raise self._raise
        return _FakeQuery(self._rows)


@pytest.fixture
def fake_redis(monkeypatch):
    r = _FakeRedis()
    monkeypatch.setattr("truebrief.api.cache._get_redis", lambda: r)
    return r


def _today():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Daily scan cap
# ---------------------------------------------------------------------------

def test_scan_cap_allows_under_limit(fake_redis):
    for _ in range(25):  # free cap is 25
        spend_guard.enforce_and_record_scan_cap("user-1", "free", "u@example.com")


def test_scan_cap_blocks_over_limit(fake_redis):
    for _ in range(25):
        spend_guard.enforce_and_record_scan_cap("user-1", "free", "u@example.com")
    with pytest.raises(HTTPException) as exc:
        spend_guard.enforce_and_record_scan_cap("user-1", "free", "u@example.com")
    assert exc.value.status_code == 429


def test_scan_cap_is_per_user(fake_redis):
    for _ in range(25):
        spend_guard.enforce_and_record_scan_cap("user-1", "free", "u1@example.com")
    # A different user is unaffected.
    spend_guard.enforce_and_record_scan_cap("user-2", "free", "u2@example.com")


def test_scan_cap_sets_ttl_once(fake_redis):
    spend_guard.enforce_and_record_scan_cap("user-1", "free", "u@example.com")
    key = f"scans:user-1:{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d')}"
    assert fake_redis.expires[key] == spend_guard._SCAN_COUNTER_TTL_SECONDS


def test_scan_cap_admin_bypass(fake_redis, monkeypatch):
    monkeypatch.setattr(spend_guard, "is_admin", lambda email: True)
    for _ in range(100):
        spend_guard.enforce_and_record_scan_cap("admin-1", "free", "admin@example.com")
    assert fake_redis.store == {}


def test_scan_cap_power_tier_unlimited(fake_redis):
    for _ in range(500):
        spend_guard.enforce_and_record_scan_cap("user-1", "power", "u@example.com")
    assert fake_redis.store == {}


def test_scan_cap_fails_open_without_redis(monkeypatch):
    monkeypatch.setattr("truebrief.api.cache._get_redis", lambda: None)
    for _ in range(1000):
        spend_guard.enforce_and_record_scan_cap("user-1", "free", "u@example.com")


def test_scan_cap_fails_open_on_redis_error(monkeypatch):
    monkeypatch.setattr("truebrief.api.cache._get_redis", lambda: _BrokenRedis())
    spend_guard.enforce_and_record_scan_cap("user-1", "free", "u@example.com")


# ---------------------------------------------------------------------------
# Global spend ceiling
# ---------------------------------------------------------------------------

def test_global_ceiling_allows_under_budget(monkeypatch):
    monkeypatch.setattr(spend_guard.settings, "GLOBAL_DAILY_SPEND_CEILING_USD", 25.0)
    db = _FakeDB(rows=[{"day": _today(), "total_cost_usd": 3.10}])
    spend_guard.enforce_global_spend_ceiling(db, "u@example.com")


def test_global_ceiling_blocks_at_budget(monkeypatch):
    monkeypatch.setattr(spend_guard.settings, "GLOBAL_DAILY_SPEND_CEILING_USD", 25.0)
    db = _FakeDB(rows=[{"day": _today(), "total_cost_usd": 25.0}])
    with pytest.raises(HTTPException) as exc:
        spend_guard.enforce_global_spend_ceiling(db, "u@example.com")
    assert exc.value.status_code == 503


def test_global_ceiling_ignores_other_days(monkeypatch):
    monkeypatch.setattr(spend_guard.settings, "GLOBAL_DAILY_SPEND_CEILING_USD", 25.0)
    db = _FakeDB(rows=[{"day": "2000-01-01", "total_cost_usd": 999.0}])
    spend_guard.enforce_global_spend_ceiling(db, "u@example.com")


def test_global_ceiling_disabled_when_zero(monkeypatch):
    monkeypatch.setattr(spend_guard.settings, "GLOBAL_DAILY_SPEND_CEILING_USD", 0.0)
    db = _FakeDB(rows=[{"day": _today(), "total_cost_usd": 999.0}])
    spend_guard.enforce_global_spend_ceiling(db, "u@example.com")


def test_global_ceiling_admin_bypass(monkeypatch):
    monkeypatch.setattr(spend_guard.settings, "GLOBAL_DAILY_SPEND_CEILING_USD", 1.0)
    monkeypatch.setattr(spend_guard, "is_admin", lambda email: True)
    db = _FakeDB(rows=[{"day": _today(), "total_cost_usd": 999.0}])
    spend_guard.enforce_global_spend_ceiling(db, "admin@example.com")


def test_global_ceiling_fails_open_on_rpc_error(monkeypatch):
    monkeypatch.setattr(spend_guard.settings, "GLOBAL_DAILY_SPEND_CEILING_USD", 1.0)
    db = _FakeDB(raise_exc=RuntimeError("PGRST202 function not found"))
    spend_guard.enforce_global_spend_ceiling(db, "u@example.com")
