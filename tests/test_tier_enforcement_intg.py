"""
Integration Tests — Tier Enforcement (Step 3.5 INTG, post-3.7 migration)

Drives the FastAPI app via TestClient with a mocked Supabase backend so that
the full request → auth → route → enforcement → response path is exercised.

After Step 3.7 (Auth), the legacy `user_id` query/body convention is gone.
These tests now use `app.dependency_overrides` to inject a fixed `User` for
the authenticated path, and exercise tier enforcement on top of that.

The bypass-via-no-user-id tests from the pre-3.7 era have been removed since
that bypass path no longer exists.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from truebrief.api.server import app
from truebrief.auth.dependencies import get_current_user, get_optional_user
from truebrief.auth.models import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _exec_result(data=None, count=None):
    return MagicMock(data=data if data is not None else [], count=count)


def _make_db(*, tier: str, topic_count: int, last_scan_at=None,
             topic_id="11111111-1111-1111-1111-111111111111",
             topic_exists: bool = True):
    db = MagicMock()

    sub_chain = MagicMock()
    sub_chain.select.return_value.eq.return_value.execute.return_value = _exec_result(
        data=[{"tier": tier}] if tier else []
    )

    sub_count_chain = MagicMock()
    sub_count_chain.select.return_value.eq.return_value.execute.return_value = _exec_result(
        count=topic_count
    )
    sub_count_chain.insert.return_value.execute.return_value = _exec_result(data=[{}])

    last_scan_iso = last_scan_at.isoformat() + "Z" if last_scan_at else None
    _topic_row = {
        "id": topic_id,
        "raw_query": "test query",
        "frequency": "daily",
        "is_active": True,
        "last_scan_at": last_scan_iso,
    }
    topics_chain = MagicMock()
    # Existing-topic lookup: return row if topic_exists, else empty (triggers insert)
    topics_chain.select.return_value.eq.return_value.execute.return_value = _exec_result(
        data=[_topic_row] if topic_exists else []
    )
    topics_chain.insert.return_value.execute.return_value = _exec_result(
        data=[{**_topic_row, "frequency": "hourly"}]
    )

    def _table(name: str):
        if name == "user_subscriptions":
            return sub_chain
        if name == "topic_subscriptions":
            return sub_count_chain
        if name == "topics":
            return topics_chain
        return MagicMock()

    db.table.side_effect = _table
    return db


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def _override_user(user_id: str | None = None) -> User:
    """Inject a fixed authenticated user for both required + optional deps."""
    fake = User(
        id=user_id or str(uuid4()),
        clerk_id="clerk_tier_test",
        email="tier@test.com",
    )
    app.dependency_overrides[get_current_user] = lambda: fake
    app.dependency_overrides[get_optional_user] = lambda: fake
    return fake


# ---------------------------------------------------------------------------
# POST /api/v1/topics — topic cap enforcement
# ---------------------------------------------------------------------------

class TestTopicCreationCap:

    def test_free_user_at_cap_returns_402(self, client):
        _override_user()
        db = _make_db(tier="free", topic_count=2)
        with patch("truebrief.api.routes.get_supabase", return_value=db):
            r = client.post("/api/v1/topics", json={"raw_query": "AI regulation"})
        assert r.status_code == 402
        assert "upgrade" in r.json()["detail"].lower()

    def test_free_user_below_cap_succeeds(self, client):
        _override_user()
        db = _make_db(tier="free", topic_count=1)
        with patch("truebrief.api.routes.get_supabase", return_value=db), \
             patch("truebrief.tasks.scheduler.set_next_run", return_value=None):
            r = client.post("/api/v1/topics", json={"raw_query": "AI regulation"})
        assert r.status_code == 200

    def test_pro_user_at_cap_returns_402(self, client):
        _override_user()
        db = _make_db(tier="pro", topic_count=15)
        with patch("truebrief.api.routes.get_supabase", return_value=db):
            r = client.post("/api/v1/topics", json={"raw_query": "Markets"})
        assert r.status_code == 402

    def test_pro_user_with_14_topics_succeeds(self, client):
        _override_user()
        db = _make_db(tier="pro", topic_count=14)
        with patch("truebrief.api.routes.get_supabase", return_value=db), \
             patch("truebrief.tasks.scheduler.set_next_run", return_value=None):
            r = client.post("/api/v1/topics", json={"raw_query": "Markets"})
        assert r.status_code == 200

    def test_power_user_unlimited(self, client):
        _override_user()
        db = _make_db(tier="power", topic_count=5000)
        with patch("truebrief.api.routes.get_supabase", return_value=db), \
             patch("truebrief.tasks.scheduler.set_next_run", return_value=None):
            r = client.post("/api/v1/topics", json={"raw_query": "Anything"})
        assert r.status_code == 200

    def test_unauthenticated_post_returns_401(self, client):
        """Post-3.7: unauthenticated topic creation is no longer allowed."""
        r = client.post("/api/v1/topics", json={"raw_query": "Any"})
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/topics/{id}/scan — speed limit enforcement
# ---------------------------------------------------------------------------

class TestScanSpeedLimit:

    def test_free_user_scan_too_soon_returns_429(self, client):
        _override_user()
        topic_id = str(uuid4())
        last = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
        db = _make_db(tier="free", topic_count=1, last_scan_at=last, topic_id=topic_id)

        with patch("truebrief.api.routes.get_supabase", return_value=db):
            r = client.post(f"/api/v1/topics/{topic_id}/scan")
        assert r.status_code == 429
        assert "upgrade" in r.json()["detail"].lower()

    def test_free_user_scan_after_25h_succeeds(self, client):
        _override_user()
        topic_id = str(uuid4())
        last = datetime.datetime.utcnow() - datetime.timedelta(hours=25)
        db = _make_db(tier="free", topic_count=1, last_scan_at=last, topic_id=topic_id)

        fake_task = MagicMock(id="task-abc")
        with patch("truebrief.api.routes.get_supabase", return_value=db), \
             patch("truebrief.tasks.pipeline_task.run_pipeline_task.delay", return_value=fake_task):
            r = client.post(f"/api/v1/topics/{topic_id}/scan")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "queued"
        assert body["task_id"] == "task-abc"

    def test_pro_user_scan_within_1h_returns_429(self, client):
        _override_user()
        topic_id = str(uuid4())
        last = datetime.datetime.utcnow() - datetime.timedelta(minutes=30)
        db = _make_db(tier="pro", topic_count=1, last_scan_at=last, topic_id=topic_id)

        with patch("truebrief.api.routes.get_supabase", return_value=db):
            r = client.post(f"/api/v1/topics/{topic_id}/scan")
        assert r.status_code == 429

    def test_unauthenticated_scan_returns_401(self, client):
        """Post-3.7: scan triggers require an authenticated user."""
        topic_id = str(uuid4())
        r = client.post(f"/api/v1/topics/{topic_id}/scan")
        assert r.status_code == 401

    def test_first_scan_passes(self, client):
        """If last_scan_at is None, scan is allowed even on Free tier."""
        _override_user()
        topic_id = str(uuid4())
        db = _make_db(tier="free", topic_count=1, last_scan_at=None, topic_id=topic_id)

        fake_task = MagicMock(id="task-first")
        with patch("truebrief.api.routes.get_supabase", return_value=db), \
             patch("truebrief.tasks.pipeline_task.run_pipeline_task.delay", return_value=fake_task):
            r = client.post(f"/api/v1/topics/{topic_id}/scan")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/v1/billing/tiers — public, no auth required
# ---------------------------------------------------------------------------

class TestBillingTiersEndpoint:

    def test_tiers_endpoint_returns_reconciled_limits(self, client):
        r = client.get("/api/v1/billing/tiers")
        assert r.status_code == 200
        body = r.json()

        assert body["free"]["max_topics"] == 2
        assert body["free"]["min_interval_hours"] == 24.0
        assert body["free"]["sources"] == ["rss", "tavily"]
        assert body["free"]["private_topics"] is False

        assert body["pro"]["max_topics"] == 15
        assert body["pro"]["min_interval_hours"] == 1.0
        assert "google_news" in body["pro"]["sources"]
        assert body["pro"]["private_topics"] is True

        assert body["power"]["max_topics"] == -1
        assert body["power"]["min_interval_hours"] == 0.25
        assert body["power"]["sources"] == ["__all__"]
        assert body["power"]["private_topics"] is True
