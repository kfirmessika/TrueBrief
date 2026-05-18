"""
Tests — test_push.py

Unit tests for the Web Push notification system (Step 3.16).

All tests are pure unit tests with no external network calls.
The push client, task, and route logic are tested in isolation via mocking.
"""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch
from starlette.requests import Request as StarletteRequest


# ---------------------------------------------------------------------------
# push/client.py tests
# ---------------------------------------------------------------------------

class TestSendPush:
    def test_send_push_no_key(self):
        """Returns False without raising when VAPID_PRIVATE_KEY is not set."""
        with patch.dict("os.environ", {"VAPID_PRIVATE_KEY": ""}, clear=False):
            # Re-import to pick up the patched env
            import truebrief.push.client as mod
            importlib.reload(mod)
            result = mod.send_push(
                subscription_info={"endpoint": "https://ex.com", "keys": {"p256dh": "a", "auth": "b"}},
                title="T",
                body="B",
            )
        assert result is False

    def test_send_push_webpush_exception(self):
        """Returns False when pywebpush raises WebPushException."""
        from truebrief.push import client as mod

        fake_exc = Exception("410 Gone")

        with patch.dict("os.environ", {"VAPID_PRIVATE_KEY": "fake-key"}, clear=False):
            importlib.reload(mod)
            with patch("truebrief.push.client.VAPID_PRIVATE_KEY", "fake-key"):
                with patch("pywebpush.webpush", side_effect=fake_exc):
                    result = mod.send_push(
                        subscription_info={
                            "endpoint": "https://ex.com",
                            "keys": {"p256dh": "a", "auth": "b"},
                        },
                        title="T",
                        body="B",
                    )
        assert result is False


# ---------------------------------------------------------------------------
# tasks/push_task.py tests
# ---------------------------------------------------------------------------

class TestPushTask:
    """Tests for send_push_notifications_task (called directly, not via Celery worker)."""

    def _run(self, subscriptions: list, send_ok: bool = True) -> dict:
        """Helper: mock DB + send_push, run task, return result."""
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = subscriptions

        with patch("truebrief.ledger.database.get_supabase", return_value=mock_db):
            with patch("truebrief.push.client.send_push", return_value=send_ok):
                from truebrief.tasks.push_task import send_push_notifications_task

                result = send_push_notifications_task(
                    user_id="user-1",
                    topic_name="TSMC chips",
                    brief_id="brief-1",
                )
        return result

    def test_push_task_no_subscriptions(self):
        result = self._run(subscriptions=[])
        assert result == {"sent": 0, "failed": 0}

    def test_push_task_sends(self):
        subs = [{"id": "sub-1", "endpoint": "https://e.com", "p256dh": "p", "auth": "a"}]
        result = self._run(subscriptions=subs, send_ok=True)
        assert result == {"sent": 1, "failed": 0}

    def test_push_task_failed(self):
        subs = [{"id": "sub-1", "endpoint": "https://e.com", "p256dh": "p", "auth": "a"}]
        result = self._run(subscriptions=subs, send_ok=False)
        assert result == {"sent": 0, "failed": 1}


# ---------------------------------------------------------------------------
# api/push_routes.py tests
# ---------------------------------------------------------------------------

class TestPushRoutes:
    def _make_user(self):
        user = MagicMock()
        user.id = "user-1"
        return user

    @staticmethod
    def _make_request():
        """Minimal Starlette Request required by @limiter.limit() decorated handlers."""
        scope = {"type": "http", "method": "POST", "path": "/", "headers": [], "query_string": b""}
        return StarletteRequest(scope)

    def test_vapid_public_key_endpoint(self):
        """GET /push/vapid-public-key returns public_key when set."""
        with patch.dict("os.environ", {"VAPID_PUBLIC_KEY": "test-public-key"}, clear=False):
            from truebrief.api.push_routes import get_vapid_public_key
            result = get_vapid_public_key()
        assert result == {"public_key": "test-public-key"}

    def test_subscribe_endpoint_upserts(self):
        """POST /push/subscribe upserts and returns 'subscribed'."""
        from truebrief.api.push_routes import subscribe, PushSubscribeRequest

        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.return_value.data = [
            {"id": "sub-1"}
        ]

        body = PushSubscribeRequest(
            endpoint="https://push.example.com/endpoint",
            p256dh="p256dh_value",
            auth="auth_value",
        )

        with patch("truebrief.api.push_routes.get_supabase", return_value=mock_db):
            result = subscribe(request=self._make_request(), body=body, user=self._make_user())

        assert result.status == "subscribed"

    def test_unsubscribe_disables_row(self):
        """DELETE /push/subscribe calls update(enabled=False) on the DB."""
        from truebrief.api.push_routes import unsubscribe, PushUnsubscribeRequest

        mock_db = MagicMock()

        body = PushUnsubscribeRequest(endpoint="https://push.example.com/endpoint")

        with patch("truebrief.api.push_routes.get_supabase", return_value=mock_db):
            result = unsubscribe(body=body, user=self._make_user())

        assert result["status"] == "unsubscribed"
        mock_db.table.return_value.update.assert_called_once_with({"enabled": False})

    def test_test_push_no_subscriptions(self):
        """POST /push/test returns 'skipped' when user has no active subscriptions."""
        from truebrief.api.push_routes import test_push

        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

        with patch("truebrief.api.push_routes.get_supabase", return_value=mock_db):
            result = test_push(request=self._make_request(), user=self._make_user())

        assert result.status == "skipped"
