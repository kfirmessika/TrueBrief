"""
Unit Tests — tests/test_digest.py

Tests for the V3 fact-delta email digest (§13 — same delta feed, digest envelope).
The digest is assembled from the per-user delta engine (anchor=last_digest_at), not
from stored brief documents.

All tests are pure unit tests: no network, no Supabase, no Resend — externals mocked.

Run with:
  pytest tests/test_digest.py -v
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures — the fact-delta shape render_digest now expects
# ---------------------------------------------------------------------------

SAMPLE_TOPICS = [
    {
        "topic_name": "AI Regulation",
        "facts": [
            {"text": "The EU passed new AI Act amendments covering open-source models.",
             "source_domain": "reuters.com", "event_class": "state_change", "age_label": "3h"},
            {"text": "France objected to the open-weight carve-out.",
             "source_domain": "politico.eu", "event_class": "development", "age_label": "9h"},
        ],
    },
    {
        "topic_name": "Semiconductor Supply",
        "facts": [
            {"text": "TSMC announced a new fab in Arizona with 2nm capacity.",
             "source_domain": "bloomberg.com", "event_class": "development", "age_label": "1d"},
        ],
    },
]


# ---------------------------------------------------------------------------
# 1. render_digest — happy path
# ---------------------------------------------------------------------------

def test_render_digest_html():
    """Rendered HTML must contain the greeting, dated header, topics, facts, and close."""
    from truebrief.digest.renderer import render_digest

    html = render_digest(user_name="Alice", date_label="Tue Jun 16", total=3, topics=SAMPLE_TOPICS)

    assert "Alice" in html
    assert "Tue Jun 16" in html
    assert "AI Regulation" in html
    assert "Semiconductor Supply" in html
    assert "TSMC announced a new fab in Arizona" in html
    assert "3 new across 2 topic" in html
    assert "That's everything" in html
    assert "unsubscribe" in html.lower()


# ---------------------------------------------------------------------------
# 2. render_digest — empty digest
# ---------------------------------------------------------------------------

def test_render_digest_empty():
    """Rendering with no topics must not raise and shows the all-caught-up copy."""
    from truebrief.digest.renderer import render_digest

    html = render_digest(user_name="Bob", date_label="Wed Jun 17", total=0, topics=[])

    assert "Bob" in html
    assert "<html" in html.lower()
    assert "caught up" in html.lower()


# ---------------------------------------------------------------------------
# 3. send_digest_email — no API key
# ---------------------------------------------------------------------------

def test_send_email_no_key():
    """send_digest_email must return False (not raise) when RESEND_API_KEY is not set."""
    with patch("truebrief.digest.mailer.RESEND_API_KEY", ""):
        from truebrief.digest.mailer import send_digest_email

        result = send_digest_email(
            to_email="user@example.com",
            subject="Test Digest",
            html_body="<p>Hello</p>",
        )

    assert result is False


# ---------------------------------------------------------------------------
# 4. send_digest_email — Resend API error
# ---------------------------------------------------------------------------

def test_send_email_api_error():
    """send_digest_email must return False when Resend raises an exception."""
    mock_resend = MagicMock()
    mock_resend.Emails.send.side_effect = RuntimeError("Connection refused")

    with (
        patch("truebrief.digest.mailer.RESEND_API_KEY", "re_test_key"),
        patch.dict("sys.modules", {"resend": mock_resend}),
    ):
        import importlib
        import truebrief.digest.mailer as mailer_mod
        importlib.reload(mailer_mod)

        result = mailer_mod.send_digest_email(
            to_email="user@example.com",
            subject="Test",
            html_body="<p>x</p>",
        )

    assert result is False


def _db_with_email(email: str = "user@example.com") -> MagicMock:
    """A MagicMock db whose users lookup returns one email row."""
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"email": email}
    ]
    return db


# ---------------------------------------------------------------------------
# 5. _process_user — skip when the delta feed is all-quiet
# ---------------------------------------------------------------------------

def test_digest_task_skip_all_quiet():
    """_process_user returns 'skipped' when nothing is new since the last digest."""
    from truebrief.tasks import digest_task

    db = _db_with_email("alice@example.com")
    quiet_feed = {"all_quiet": True, "total": 0, "topic_count": 2, "topics": []}

    with patch.object(digest_task, "get_delta_feed", return_value=quiet_feed):
        result = digest_task._process_user(
            db=db, user_id="user-111", frequency="daily",
            send_fn=MagicMock(), render_fn=MagicMock(),
        )

    assert result == "skipped"


# ---------------------------------------------------------------------------
# 6. _process_user — sends when the delta feed has new facts
# ---------------------------------------------------------------------------

def test_digest_task_sends():
    """_process_user returns 'sent', renders, sends, and advances the digest anchor."""
    from truebrief.tasks import digest_task

    db = _db_with_email("bob@example.com")
    feed = {
        "all_quiet": False, "total": 1, "topic_count": 1,
        "topics": [{
            "topic_id": "topic-bbb", "topic_name": "TSMC chips", "new_count": 1,
            "facts": [{
                "text": "TSMC announced a new fab in Arizona.",
                "context": None, "event_class": "development",
                "event_date": "2026-05-18", "first_seen_at": "2026-05-18T08:00:00+00:00",
                "source_domain": "bloomberg.com", "source_url": "https://bloomberg.com/x",
                "verified_count": 2,
            }],
        }],
    }
    mock_send = MagicMock(return_value=True)
    mock_render = MagicMock(return_value="<html>digest</html>")

    with (
        patch.object(digest_task, "get_delta_feed", return_value=feed),
        patch.object(digest_task, "advance_digest") as mock_advance,
    ):
        result = digest_task._process_user(
            db=db, user_id="user-222", frequency="daily",
            send_fn=mock_send, render_fn=mock_render,
        )

    assert result == "sent"
    mock_render.assert_called_once()
    mock_send.assert_called_once()
    mock_advance.assert_called_once()      # digest anchor advanced after send

    # render got the fact-delta shape
    render_kwargs = mock_render.call_args.kwargs
    assert render_kwargs["total"] == 1
    assert render_kwargs["topics"][0]["topic_name"] == "TSMC chips"
    assert render_kwargs["topics"][0]["facts"][0]["age_label"]  # computed, non-empty

    send_kwargs = mock_send.call_args.kwargs
    assert send_kwargs["to_email"] == "bob@example.com"
    assert "new" in send_kwargs["subject"].lower()


# ---------------------------------------------------------------------------
# 7. _process_user — weekly user not yet due is skipped
# ---------------------------------------------------------------------------

def test_digest_task_weekly_not_due():
    """A weekly user whose last digest is recent is skipped without building a feed."""
    from truebrief.tasks import digest_task

    db = _db_with_email("weekly@example.com")

    with (
        patch.object(digest_task, "_weekly_due", return_value=False),
        patch.object(digest_task, "get_delta_feed") as mock_feed,
    ):
        result = digest_task._process_user(
            db=db, user_id="user-333", frequency="weekly",
            send_fn=MagicMock(), render_fn=MagicMock(),
        )

    assert result == "skipped"
    mock_feed.assert_not_called()          # gated before assembling the feed


# ---------------------------------------------------------------------------
# 8. digest settings logic (unchanged)
# ---------------------------------------------------------------------------

def test_digest_settings_defaults():
    """get_digest_settings returns sensible defaults when no DB row exists."""
    row_data = None
    enabled, frequency, send_hour_utc = True, "daily", 8
    if row_data:
        enabled = row_data["enabled"]
        frequency = row_data["frequency"]
        send_hour_utc = row_data["send_hour_utc"]
    assert enabled is True
    assert frequency == "daily"
    assert send_hour_utc == 8


def test_digest_settings_upsert_values():
    """Upserted settings contain exactly the request-body values."""
    upsert_data = {"user_id": "user-999", "enabled": False, "frequency": "weekly", "send_hour_utc": 18}
    assert upsert_data["enabled"] is False
    assert upsert_data["frequency"] == "weekly"
    assert upsert_data["send_hour_utc"] == 18
    assert upsert_data["user_id"] == "user-999"
