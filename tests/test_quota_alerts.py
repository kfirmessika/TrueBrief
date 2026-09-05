"""
Tests for the generalized provider-failure alert pipeline — ledger/quota_alerts.py.

No direct coverage existed before this file: flag_quota_event()/_persist()/
_notify_founder()/recent_alerts() were only ever exercised incidentally through
llm/client.py's own tests, none of which asserted on persistence or notification
content. Covers the migration-038 generalization specifically:
  1. flag_quota_event persists a provider-tagged row and never raises on DB/push failure
  2. _persist inserts the `provider` column, defaulting to "gemini" for old call sites
  3. _notify_founder's body keeps the specific "primary/backup key" wording for Gemini's
     own dual-key rotation, and just names the provider otherwise (Linkup/Brave/Groq/
     OpenAI have no primary/backup concept)
  4. recent_alerts selects the `provider` column
  5. Unknown severity is a no-op (unchanged pre-existing behavior)

conftest.py's autouse `_no_real_quota_alerts` fixture patches _get_db to return None
for every other test in the suite; these tests override that locally (patch.object)
wherever they need to exercise the real persist/notify path against a fake db.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from truebrief.ledger import quota_alerts


def _fake_db_with_subscription():
    """A mock Supabase client: one resolvable founder user_id, one active push sub."""
    db = MagicMock()

    def table(name):
        t = MagicMock()
        if name == "users":
            t.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[{"id": "founder-uid"}]
            )
        elif name == "push_subscriptions":
            t.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"id": "sub-1", "endpoint": "https://push.example/ep", "p256dh": "p", "auth": "a"}]
            )
        return t

    db.table.side_effect = table
    return db


class TestNotifyFounder:
    def test_gemini_primary_key_wording_preserved(self):
        db = _fake_db_with_subscription()
        with patch("config.settings.settings") as settings, \
             patch("truebrief.push.client.send_push", return_value=True) as push:
            settings.FOUNDER_EMAIL = "founder@example.com"
            settings.ADMIN_EMAILS = ""
            ok = quota_alerts._notify_founder(
                db, "yellow", "gemini_search", "gemini-3.5-flash-lite", "429 quota",
                provider="gemini", key_type="primary",
            )
        assert ok is True
        _, kwargs = push.call_args
        assert "gemini primary key" in kwargs["body"]

    def test_non_gemini_provider_named_without_key_type(self):
        db = _fake_db_with_subscription()
        with patch("config.settings.settings") as settings, \
             patch("truebrief.push.client.send_push", return_value=True) as push:
            settings.FOUNDER_EMAIL = "founder@example.com"
            settings.ADMIN_EMAILS = ""
            ok = quota_alerts._notify_founder(
                db, "red", "gemini_search", "linkup/sourcedAnswer", "Linkup 500",
                provider="linkup", key_type="single",
            )
        assert ok is True
        _, kwargs = push.call_args
        assert kwargs["title"] == quota_alerts._RED_TITLE
        assert "linkup" in kwargs["body"]
        assert "single key" not in kwargs["body"]

    def test_no_subscription_returns_false_without_raising(self):
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"id": "founder-uid"}]
        )
        db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )
        with patch("config.settings.settings") as settings:
            settings.FOUNDER_EMAIL = "founder@example.com"
            settings.ADMIN_EMAILS = ""
            ok = quota_alerts._notify_founder(
                db, "red", "embedding", "text-embedding-3-small", "boom", provider="openai",
            )
        assert ok is False


class TestPersist:
    def test_insert_includes_provider_column(self):
        db = MagicMock()
        quota_alerts._persist(
            db, "red", "embedding", "text-embedding-3-small", "single", "boom",
            notified=False, provider="openai",
        )
        db.table.assert_called_with("quota_alerts")
        inserted = db.table.return_value.insert.call_args[0][0]
        assert inserted["provider"] == "openai"
        assert inserted["key_type"] == "single"
        assert inserted["notified"] is False

    def test_defaults_to_gemini_for_backward_compatible_callers(self):
        db = MagicMock()
        quota_alerts._persist(db, "yellow", "gemini_search", "m", "primary", "e", notified=True)
        inserted = db.table.return_value.insert.call_args[0][0]
        assert inserted["provider"] == "gemini"


class TestFlagQuotaEvent:
    def test_never_raises_when_db_unreachable(self):
        with patch.object(quota_alerts, "_get_db", side_effect=RuntimeError("no creds")):
            quota_alerts.flag_quota_event("red", "gemini_search", "m", "primary", Exception("x"))

    def test_unknown_severity_is_a_no_op(self):
        with patch.object(quota_alerts, "_get_db") as get_db:
            quota_alerts.flag_quota_event("purple", "gemini_search", "m", "primary", Exception("x"))
        get_db.assert_not_called()

    def test_persists_with_provider_threaded_through(self):
        db = _fake_db_with_subscription()
        with patch.object(quota_alerts, "_get_db", return_value=db), \
             patch("config.settings.settings") as settings, \
             patch("truebrief.push.client.send_push", return_value=True):
            settings.FOUNDER_EMAIL = "founder@example.com"
            settings.ADMIN_EMAILS = ""
            quota_alerts.flag_quota_event(
                "red", "gemini_search", "linkup/sourcedAnswer", "single",
                Exception("Linkup 500"), provider="linkup",
            )
        table_names = [c.args[0] for c in db.table.call_args_list]
        assert "quota_alerts" in table_names


class TestRecentAlerts:
    def test_select_includes_provider(self):
        db = MagicMock()
        (db.table.return_value.select.return_value.gte.return_value
         .order.return_value.limit.return_value.execute.return_value) = MagicMock(
            data=[{"id": "1", "provider": "linkup"}]
        )
        with patch.object(quota_alerts, "_get_db", return_value=db):
            rows = quota_alerts.recent_alerts(hours=48)
        assert rows == [{"id": "1", "provider": "linkup"}]
        select_args = db.table.return_value.select.call_args[0][0]
        assert "provider" in select_args

    def test_returns_empty_list_on_db_error(self):
        with patch.object(quota_alerts, "_get_db", side_effect=RuntimeError("down")):
            assert quota_alerts.recent_alerts() == []
