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

logger = logging.getLogger(__name__)

# Lookback windows with a 1-hour buffer to handle scheduler drift
_LOOKBACK_HOURS: dict[str, int] = {
    "daily": 25,
    "weekly": 169,
}


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
    Handle one user's digest. Returns 'sent' or 'skipped'.

    Args:
        db:        Supabase client.
        user_id:   The user's UUID.
        frequency: 'daily' | 'weekly'.
        send_fn:   Injected send function (allows mocking in tests).
        render_fn: Injected render function (allows mocking in tests).

    Returns:
        'sent' or 'skipped'
    """
    # 1. Resolve user email and display name
    user_res = db.table("users").select("email").eq("id", user_id).execute()
    if not user_res.data:
        logger.warning("User %s not found in users table, skipping.", user_id)
        return "skipped"

    user_email: str = user_res.data[0]["email"]
    user_name: str = user_email.split("@")[0]  # friendly fallback name

    # 2. Determine lookback window
    lookback_hours = _LOOKBACK_HOURS.get(frequency, 25)
    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    since_iso = since.isoformat()

    # 3. Get all topic_ids the user is subscribed to
    subs_res = (
        db.table("topic_subscriptions")
        .select("topic_id")
        .eq("user_id", user_id)
        .execute()
    )
    topic_ids = [s["topic_id"] for s in (subs_res.data or [])]

    if not topic_ids:
        logger.debug("User %s has no subscriptions, skipping.", user_id)
        return "skipped"

    # 4. Fetch topics for name lookup
    topics_res = (
        db.table("topics")
        .select("id, raw_query")
        .in_("id", topic_ids)
        .execute()
    )
    topic_map: dict[str, str] = {
        t["id"]: t["raw_query"] for t in (topics_res.data or [])
    }

    # 5. Fetch recent briefs (most recent per topic within the window)
    briefs_res = (
        db.table("briefs")
        .select("id, topic_id, content, delivered_at")
        .in_("topic_id", topic_ids)
        .gte("delivered_at", since_iso)
        .order("delivered_at", desc=True)
        .execute()
    )
    all_briefs = briefs_res.data or []

    # One brief per topic (the most recent, since results are ordered desc)
    seen_topics: set[str] = set()
    digest_briefs: list[dict] = []
    for brief in all_briefs:
        tid = brief["topic_id"]
        if tid in seen_topics:
            continue
        seen_topics.add(tid)

        # Build a clean preview (strip markdown)
        preview = (
            brief["content"]
            .replace("#", "")
            .replace("*", "")
            .replace("`", "")
            .replace("_", "")
            .replace("\n", " ")
            .strip()
        )[:200]

        # Format the date for display
        raw_date = brief.get("delivered_at", "")
        try:
            dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            friendly_date = dt.strftime("%B %d, %Y at %H:%M UTC")
        except Exception:
            friendly_date = raw_date

        digest_briefs.append(
            {
                "topic_name": topic_map.get(tid, "Intelligence Brief"),
                "brief_id": brief["id"],
                "summary_preview": preview,
                "delivered_at": friendly_date,
            }
        )

    if not digest_briefs:
        logger.debug("No new briefs for user %s in last %dh, skipping.", user_id, lookback_hours)
        return "skipped"

    # 6. Render HTML
    html = render_fn(user_name=user_name, briefs=digest_briefs)

    # 7. Build subject line
    topic_count = len(digest_briefs)
    subject = (
        f"Your TrueBrief Digest — {topic_count} new brief{'s' if topic_count != 1 else ''}"
    )

    # 8. Send
    ok = send_fn(to_email=user_email, subject=subject, html_body=html)
    return "sent" if ok else "skipped"
