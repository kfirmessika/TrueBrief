"""
Tests — test_effective_tier.py

billing.tiers.resolve_effective_tier: the single source of truth for the tier
that gets *enforced*, given a user_subscriptions row. A failed payment used to
leave `tier` untouched, so a lapsed/refunded customer kept paid access.
"""

import datetime

import pytest

from config.settings import settings
from truebrief.billing.tiers import resolve_effective_tier


def _iso(dt: datetime.datetime) -> str:
    return dt.isoformat()


def _ago(days: float) -> str:
    return _iso(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days))


def test_none_row_is_free():
    assert resolve_effective_tier(None) == "free"


def test_active_paid_row_keeps_tier():
    assert resolve_effective_tier({"tier": "pro", "status": "active"}) == "pro"
    assert resolve_effective_tier({"tier": "power", "status": "trialing"}) == "power"


def test_canceled_is_free_even_with_paid_tier():
    assert resolve_effective_tier({"tier": "pro", "status": "canceled"}) == "free"
    assert resolve_effective_tier({"tier": "pro", "status": "cancelled"}) == "free"


def test_past_due_within_grace_keeps_tier(monkeypatch):
    monkeypatch.setattr(settings, "PADDLE_PAST_DUE_GRACE_DAYS", 3)
    row = {"tier": "pro", "status": "past_due", "past_due_since": _ago(1)}
    assert resolve_effective_tier(row) == "pro"


def test_past_due_beyond_grace_is_free(monkeypatch):
    monkeypatch.setattr(settings, "PADDLE_PAST_DUE_GRACE_DAYS", 3)
    row = {"tier": "pro", "status": "past_due", "past_due_since": _ago(5)}
    assert resolve_effective_tier(row) == "free"


def test_past_due_without_timestamp_is_free():
    row = {"tier": "pro", "status": "past_due", "past_due_since": None}
    assert resolve_effective_tier(row) == "free"


def test_past_due_with_garbage_timestamp_is_free():
    row = {"tier": "pro", "status": "past_due", "past_due_since": "not-a-date"}
    assert resolve_effective_tier(row) == "free"


def test_free_tier_stays_free_regardless_of_status():
    assert resolve_effective_tier({"tier": "free", "status": "past_due"}) == "free"


def test_grace_boundary_is_inclusive(monkeypatch):
    monkeypatch.setattr(settings, "PADDLE_PAST_DUE_GRACE_DAYS", 3)
    # just inside 3 days -> still paid
    row = {"tier": "pro", "status": "past_due", "past_due_since": _ago(2.99)}
    assert resolve_effective_tier(row) == "pro"
