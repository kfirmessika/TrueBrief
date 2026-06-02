"""
Integration Tests — Auth (Step 3.7 INTG)

Drives the FastAPI app with TestClient end-to-end. Two strategies:

  1. For the *successful* auth path, override `get_current_user` /
     `get_optional_user` via `app.dependency_overrides`. This is the canonical
     FastAPI integration-test pattern and avoids fragile patches against the
     lazy `verify_clerk_jwt` import.

  2. For the *failure* paths (missing/invalid bearer), patch
     `truebrief.auth.dependencies.verify_clerk_jwt` directly so the real
     dependency runs and we exercise the actual 401 logic.

Mirrors the integration smoke checklist in
docs/steps/phase_3/STEP_3.7_SPEC.md § Integration Tests.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from truebrief.api.server import app
from truebrief.auth.dependencies import User, get_current_user, get_optional_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _exec_result(data=None, count=None):
    return MagicMock(data=data if data is not None else [], count=count)


def _make_db(*, tier: str = "free", topic_count: int = 0,
             last_scan_at=None, topic_id="11111111-1111-1111-1111-111111111111",
             users_existing: bool = True,
             user_uuid: str = "22222222-2222-2222-2222-222222222222",
             clerk_id: str = "clerk_test_1",
             topic_exists: bool = True):
    """Mirror of the helper in test_tier_enforcement_intg.py, plus users table."""
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
    # Existing-topic lookup (eq on raw_query): return data if topic_exists, else empty
    topics_chain.select.return_value.eq.return_value.execute.return_value = _exec_result(
        data=[_topic_row] if topic_exists else []
    )
    topics_chain.insert.return_value.execute.return_value = _exec_result(
        data=[{**_topic_row, "frequency": "hourly"}]
    )

    users_chain = MagicMock()
    if users_existing:
        users_chain.select.return_value.eq.return_value.execute.return_value = _exec_result(
            data=[{"id": user_uuid, "clerk_id": clerk_id, "email": "a@b.com"}]
        )
    else:
        users_chain.select.return_value.eq.return_value.execute.return_value = _exec_result(data=[])
    users_chain.insert.return_value.execute.return_value = _exec_result(data=[{}])
    users_chain.update.return_value.eq.return_value.execute.return_value = _exec_result(data=[{}])

    user_subs_chain = MagicMock()
    user_subs_chain.select.return_value.eq.return_value.execute.return_value = _exec_result(
        data=[{"tier": tier}] if tier else []
    )
    user_subs_chain.insert.return_value.execute.return_value = _exec_result(data=[{}])

    def _table(name: str):
        if name == "user_subscriptions":
            return user_subs_chain
        if name == "topic_subscriptions":
            return sub_count_chain
        if name == "topics":
            return topics_chain
        if name == "users":
            return users_chain
        return MagicMock()

    db.table.side_effect = _table
    return db


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def _override_user(user_id: str = "22222222-2222-2222-2222-222222222222",
                   clerk_id: str = "clerk_test_1",
                   email: str = "a@b.com") -> User:
    """Replace get_current_user / get_optional_user with a fixed User."""
    fake = User(id=user_id, clerk_id=clerk_id, email=email)
    app.dependency_overrides[get_current_user] = lambda: fake
    app.dependency_overrides[get_optional_user] = lambda: fake
    return fake


# ---------------------------------------------------------------------------
# Failure paths — exercise the real dependency
# ---------------------------------------------------------------------------

class TestUnauthenticated:

    def test_post_topics_without_token_returns_401(self, client):
        r = client.post("/api/v1/topics", json={"raw_query": "AI"})
        assert r.status_code == 401
        assert "Missing Bearer token" in r.json()["detail"]

    @patch("truebrief.auth.dependencies.verify_clerk_jwt")
    def test_post_topics_with_invalid_token_returns_401(self, mock_verify, client):
        mock_verify.side_effect = jwt.JWTError("Invalid signature")
        r = client.post(
            "/api/v1/topics",
            json={"raw_query": "AI"},
            headers={"Authorization": "Bearer badtoken"},
        )
        assert r.status_code == 401
        assert "Invalid token" in r.json()["detail"]

    def test_post_topics_with_malformed_header_returns_401(self, client):
        r = client.post(
            "/api/v1/topics",
            json={"raw_query": "AI"},
            headers={"Authorization": "NotBearer xyz"},
        )
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Success path — dependency override + Supabase mocked
# ---------------------------------------------------------------------------

class TestAuthenticatedTopicCreation:

    def test_post_topics_with_valid_token_uses_resolved_user_id(self, client):
        user = _override_user()
        # topic_exists=False forces the insert path so we can assert on it
        db = _make_db(tier="free", topic_count=0, topic_exists=False)

        with patch("truebrief.api.routes.get_supabase", return_value=db), \
             patch("truebrief.tasks.scheduler.set_next_run", return_value=None):
            r = client.post("/api/v1/topics", json={"raw_query": "AI"})

        assert r.status_code == 200
        # The topics.insert payload must be keyed off the resolved internal UUID,
        # NOT off any client-supplied identifier or the Clerk sub claim.
        topics_insert_call = db.table("topics").insert.call_args
        assert topics_insert_call.args[0]["user_id"] == user.id
        assert "clerk_test_1" not in str(topics_insert_call)

    def test_tier_enforcement_still_fires_on_authenticated_path(self, client):
        """3.5 enforcement must still fire after migration to Depends-based auth."""
        _override_user()
        db = _make_db(tier="free", topic_count=2)

        with patch("truebrief.api.routes.get_supabase", return_value=db):
            r = client.post("/api/v1/topics", json={"raw_query": "AI"})
        assert r.status_code == 402

    def test_scan_endpoint_speed_limit_with_authenticated_user(self, client):
        _override_user()
        topic_id = str(uuid4())
        last = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
        db = _make_db(tier="free", topic_count=1, last_scan_at=last, topic_id=topic_id)

        with patch("truebrief.api.routes.get_supabase", return_value=db):
            r = client.post(f"/api/v1/topics/{topic_id}/scan")
        assert r.status_code == 429


# ---------------------------------------------------------------------------
# get_or_create_user behavior — assert against the real repo via TestClient
# ---------------------------------------------------------------------------

class TestUserBootstrap:
    """
    These tests do NOT use dependency_overrides. They patch verify_clerk_jwt and
    user_repo's Supabase getter so the real get_current_user → get_or_create_user
    path runs end-to-end. Asserts the side-effects in the DB mock.
    """

    @patch("truebrief.auth.dependencies.verify_clerk_jwt")
    @patch("truebrief.auth.user_repo.get_supabase")
    def test_first_login_creates_users_row_and_user_subscriptions_row(
        self, mock_user_db, mock_verify, client
    ):
        mock_verify.return_value = {"sub": "clerk_new", "email": "new@b.com"}
        repo_db = _make_db(users_existing=False)
        mock_user_db.return_value = repo_db

        # Patch routes' supabase too so the downstream tier check has data
        routes_db = _make_db(tier="free", topic_count=0)
        with patch("truebrief.api.routes.get_supabase", return_value=routes_db):
            r = client.get("/api/v1/topics", headers={"Authorization": "Bearer t"})

        assert r.status_code == 200
        # users.insert called once
        repo_db.table("users").insert.assert_called_once()
        users_insert_payload = repo_db.table("users").insert.call_args.args[0]
        assert users_insert_payload["clerk_id"] == "clerk_new"
        assert users_insert_payload["email"] == "new@b.com"
        # user_subscriptions.insert called with tier='free'
        repo_db.table("user_subscriptions").insert.assert_called_once()
        sub_payload = repo_db.table("user_subscriptions").insert.call_args.args[0]
        assert sub_payload["tier"] == "free"
        assert sub_payload["status"] == "active"

    @patch("truebrief.auth.dependencies.verify_clerk_jwt")
    @patch("truebrief.auth.user_repo.get_supabase")
    def test_returning_user_skips_inserts(self, mock_user_db, mock_verify, client):
        mock_verify.return_value = {"sub": "clerk_existing", "email": "old@b.com"}
        repo_db = _make_db(users_existing=True, clerk_id="clerk_existing")
        mock_user_db.return_value = repo_db

        routes_db = _make_db(tier="free", topic_count=0)
        with patch("truebrief.api.routes.get_supabase", return_value=routes_db):
            r = client.get("/api/v1/topics", headers={"Authorization": "Bearer t"})

        assert r.status_code == 200
        repo_db.table("users").insert.assert_not_called()
        # last_seen_at update fires
        repo_db.table("users").update.assert_called_with({"last_seen_at": "now()"})


# ---------------------------------------------------------------------------
# Billing status uses authenticated user
# ---------------------------------------------------------------------------

class TestBillingStatus:

    def test_billing_status_uses_current_user_not_path_param(self, client):
        user = _override_user(user_id="33333333-3333-3333-3333-333333333333")

        with patch(
            "truebrief.billing.billing_routes._paddle.get_subscription",
            return_value={"tier": "pro", "status": "active"},
        ):
            r = client.get("/api/v1/billing/status")

        assert r.status_code == 200
        body = r.json()
        assert body["user_id"] == user.id
        assert body["tier"] == "pro"
        assert body["limits"]["max_topics"] == 15