"""
Integration tests for GET/PUT /topics/{id}/schedule (docs/core/architecture_v5.md §7).
Follows the same TestClient + mocked-Supabase pattern as test_tier_enforcement_intg.py.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from truebrief.api.server import app
from truebrief.auth.dependencies import get_current_user, get_optional_user
from truebrief.auth.models import User

TOPIC_ID = "11111111-1111-1111-1111-111111111111"


def _exec_result(data=None):
    return MagicMock(data=data if data is not None else [])


def _make_db(*, tier: str, subscribed: bool = True, existing_times: list | None = None):
    db = MagicMock()

    sub_chain = MagicMock()
    sub_chain.select.return_value.eq.return_value.eq.return_value.execute.return_value = _exec_result(
        data=[{"topic_id": TOPIC_ID}] if subscribed else []
    )

    user_sub_chain = MagicMock()
    user_sub_chain.select.return_value.eq.return_value.execute.return_value = _exec_result(
        data=[{"tier": tier}]
    )

    schedule_chain = MagicMock()
    ordered = schedule_chain.select.return_value.eq.return_value.order.return_value.order.return_value
    ordered.execute.return_value = _exec_result(
        data=[{"hour": h, "minute": m} for h, m in (existing_times or [])]
    )
    schedule_chain.delete.return_value.eq.return_value.execute.return_value = _exec_result()
    schedule_chain.insert.return_value.execute.return_value = _exec_result()

    topics_chain = MagicMock()
    topics_chain.update.return_value.eq.return_value.execute.return_value = _exec_result()

    def _table(name: str):
        if name == "topic_subscriptions":
            return sub_chain
        if name == "user_subscriptions":
            return user_sub_chain
        if name == "topic_schedule_times":
            return schedule_chain
        if name == "topics":
            return topics_chain
        return MagicMock()

    db.table.side_effect = _table
    return db


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _override_user():
    fake = User(id="user-1", auth_uid="auth-user-1", email="test@example.com")
    app.dependency_overrides[get_current_user] = lambda: fake
    app.dependency_overrides[get_optional_user] = lambda: fake


class TestGetSchedule:
    def test_no_times_configured_returns_default(self, client):
        _override_user()
        db = _make_db(tier="free", existing_times=[])
        with patch("truebrief.api.routes.get_supabase", return_value=db):
            r = client.get(f"/api/v1/topics/{TOPIC_ID}/schedule")
        assert r.status_code == 200
        body = r.json()
        assert body["is_default"] is True
        assert body["times"] == [{"hour": 9, "minute": 0}]

    def test_configured_times_returned_as_is(self, client):
        _override_user()
        db = _make_db(tier="pro", existing_times=[(9, 0), (20, 30)])
        with patch("truebrief.api.routes.get_supabase", return_value=db):
            r = client.get(f"/api/v1/topics/{TOPIC_ID}/schedule")
        assert r.status_code == 200
        body = r.json()
        assert body["is_default"] is False
        assert body["times"] == [{"hour": 9, "minute": 0}, {"hour": 20, "minute": 30}]

    def test_unsubscribed_user_gets_403(self, client):
        _override_user()
        db = _make_db(tier="free", subscribed=False)
        with patch("truebrief.api.routes.get_supabase", return_value=db):
            r = client.get(f"/api/v1/topics/{TOPIC_ID}/schedule")
        assert r.status_code == 403


class TestPutSchedule:
    def test_free_tier_two_times_rejected_402(self, client):
        """Free tier's 24h floor can never fit two times in one day."""
        _override_user()
        db = _make_db(tier="free")
        with patch("truebrief.api.routes.get_supabase", return_value=db):
            r = client.put(
                f"/api/v1/topics/{TOPIC_ID}/schedule",
                json={"times": [{"hour": 9, "minute": 0}, {"hour": 20, "minute": 0}]},
            )
        assert r.status_code == 402

    def test_pro_tier_hourly_spaced_times_accepted(self, client):
        _override_user()
        db = _make_db(tier="pro")
        with patch("truebrief.api.routes.get_supabase", return_value=db), \
             patch("truebrief.tasks.scheduler.set_next_run", return_value=None):
            r = client.put(
                f"/api/v1/topics/{TOPIC_ID}/schedule",
                json={"times": [{"hour": 9, "minute": 0}, {"hour": 12, "minute": 0}]},
            )
        assert r.status_code == 200
        assert r.json()["times"] == [{"hour": 9, "minute": 0}, {"hour": 12, "minute": 0}]

    def test_invalid_hour_returns_422(self, client):
        _override_user()
        db = _make_db(tier="power")
        with patch("truebrief.api.routes.get_supabase", return_value=db):
            r = client.put(
                f"/api/v1/topics/{TOPIC_ID}/schedule",
                json={"times": [{"hour": 25, "minute": 0}]},
            )
        assert r.status_code == 422

    def test_empty_list_resets_to_default(self, client):
        _override_user()
        db = _make_db(tier="free")
        with patch("truebrief.api.routes.get_supabase", return_value=db), \
             patch("truebrief.tasks.scheduler.set_next_run", return_value=None):
            r = client.put(f"/api/v1/topics/{TOPIC_ID}/schedule", json={"times": []})
        assert r.status_code == 200
        assert r.json()["times"] == []
