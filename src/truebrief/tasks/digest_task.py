"""
Digest Task — tasks/digest_task.py

Celery Beat task: sends daily (or weekly) email digests to all users
who have digest_enabled = true in their digest_settings row.

Schedule:
  - Registered in celery_app.py beat_schedule as a daily crontab at 08:00 UTC.
  - Weekly users are filtered in-task by their `frequency` field.

Logic per invocation:
  1. Load all digest_settings rows where enabled = true.
  2. For each user_id:
     a. Resolve user email from the `users` table.
     b. Determine lookback window (25h for daily, 169h for weekly).
     c. Fetch the most recent brief per topic (within the window).
     d. Skip if no briefs found (no empty emails).
     e. Render HTML via renderer.render_digest().
     f. Send via mailer.send_digest_email().
  3. Return summary dict: {sent, skipped, errors}.

Never raises — all per-user exceptions are caught and counted.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from truebrief.tasks.celery_app import celery_app
from truebrief.ledger.delta_engine import get_delta_feed, advance_digest

logger = logging.getLogger(__name__)

# A weekly subscriber is only "due" once ~7 days have passed since their last digest.
_WEEKLY_MIN_DAYS = 6.5


def _age_label(first_seen_at) -> str:
    """Compact 'how long ago we first saw it' label, e.g. '2h' / '3d'."""
    if not first_seen_at:
        return ""
    try:
        s = str(first_seen_at).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
    except Exception:
        return ""
    mins = max(int((datetime.now(timezone.utc) - dt).total_seconds() // 60), 0)
    if mins < 60:
        return f"{mins}m"
    hrs = mins // 60
    if hrs < 24:
        return f"{hrs}h"
    return f"{hrs // 24}d"


def _weekly_due(db, user_id: str) -> bool:
    """True if a weekly user's most recent last_digest_at is ~7+ days old.
    Missing state (pre-019) → treat as due so they still get a digest."""
    try:
        res = (
            db.table("user_topic_state")
            .select("last_digest_at")
            .eq("user_id", user_id)
            .order("last_digest_at", desc=True)
            .limit(1)
            .execute()
        )
        if not res.data:
            return True
        last = res.data[0].get("last_digest_at")
        if not last:
            return True
        dt = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt) >= timedelta(days=_WEEKLY_MIN_DAYS)
    except Exception:
        return True  # table missing / error → don't block delivery


@celery_app.task(
    name="truebrief.tasks.digest_task.send_digest_task",
    bind=False,
    ignore_result=False,
    max_retries=0,
)
def send_digest_task() -> dict:
    """
    Main digest dispatch task.

    Returns:
        {"sent": int, "skipped": int, "errors": int}
    """
    from truebrief.ledger.database import get_supabase
    from truebrief.digest.mailer import send_digest_email
    from truebrief.digest.renderer import render_digest

    db = get_supabase()
    sent = skipped = errors = 0

    try:
        settings_res = (
            db.table("digest_settings")
            .select("user_id, frequency")
            .eq("enabled", True)
            .execute()
        )
        settings_rows = settings_res.data or []
    except Exception as exc:
        logger.error("Failed to load digest_settings: %s", exc)
        return {"sent": 0, "skipped": 0, "errors": 1}

    logger.info("Digest task: processing %d eligible users.", len(settings_rows))

    for row in settings_rows:
        user_id: str = row["user_id"]
        frequency: str = row.get("frequency", "daily")

        try:
            result = _process_user(db, user_id, frequency, send_digest_email, render_digest)
            if result == "sent":
                sent += 1
            else:
                skipped += 1
        except Exception as exc:
            logger.error("Unexpected error processing user %s: %s", user_id, exc, exc_info=True)
            errors += 1

    logger.info(
        "Digest task complete. sent=%d skipped=%d errors=%d", sent, skipped, errors
    )
    return {"sent": sent, "skipped": skipped, "errors": errors}


def _process_user(db, user_id: str, frequency: str, send_fn, render_fn) -> str:
    """
    Handle one user's V3 fact-delta digest (§13 — same feed, digest envelope).
    Returns 'sent' or 'skipped'.

    The digest is the per-user delta feed (§8) anchored on last_digest_at: everything
    new since the last digest, grouped by topic. After a successful send we advance
    last_digest_at so the next digest starts where this one ended ("two markers, one feed").

    Args:
        db:        Supabase client.
        user_id:   The user's UUID.
        frequency: 'daily' | 'weekly'.
        send_fn:   Injected send function (allows mocking in tests).
        render_fn: Injected render function (allows mocking in tests).
    """
    # 1. Resolve user email and display name.
    user_res = db.table("users").select("email").eq("id", user_id).execute()
    if not user_res.data:
        logger.warning("User %s not found in users table, skipping.", user_id)
        return "skipped"
    user_email: str = user_res.data[0]["email"]
    user_name: str = user_email.split("@")[0]

    # 2. Weekly cadence gate (daily always proceeds).
    if frequency == "weekly" and not _weekly_due(db, user_id):
        logger.debug("Weekly user %s not due yet, skipping.", user_id)
        return "skipped"

    # 3. Assemble the delta feed since the user's last digest.
    feed = get_delta_feed(user_id, anchor="digest", db=db)
    if feed.get("all_quiet") or not feed.get("topics"):
        logger.debug("Nothing new for user %s since last digest, skipping.", user_id)
        return "skipped"

    # 4. Shape topics for the template (add compact age labels).
    render_topics = [
        {
            "topic_name": t["topic_name"],
            "facts": [
                {
                    "text":          f["text"],
                    "source_domain": f.get("source_domain"),
                    "event_class":   f.get("event_class"),
                    "age_label":     _age_label(f.get("first_seen_at")),
                }
                for f in t["facts"]
            ],
        }
        for t in feed["topics"]
    ]
    total = feed.get("total", sum(len(t["facts"]) for t in render_topics))
    date_label = datetime.now(timezone.utc).strftime("%a %b %d")

    # 5. Render + send.
    html = render_fn(user_name=user_name, date_label=date_label, total=total, topics=render_topics)
    subject = f"Your brief · {date_label} — {total} new"
    ok = send_fn(to_email=user_email, subject=subject, html_body=html)
    if not ok:
        return "skipped"

    # 6. Advance the digest anchor so tomorrow's digest starts here.
    advance_digest(user_id, db=db)
    return "sent"
