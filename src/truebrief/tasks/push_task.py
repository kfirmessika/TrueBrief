"""
Push Notification Task — tasks/push_task.py

Celery task: sends a Web Push notification to all enabled browser subscriptions
for a given user when a new brief is ready for one of their topics.

Called by pipeline_task after brief delivery:
    send_push_notifications_task.delay(
        user_id="...",
        topic_name="TSMC chips",
        brief_id="...",
    )

Logic:
  1. Query push_subscriptions where user_id = user_id AND enabled = true.
  2. For each subscription: build subscription_info dict, call push client.
  3. If push returns False (expired/invalid endpoint) → set enabled=false in DB.
  4. Return summary dict: {"sent": N, "failed": M}.

Never raises — all per-subscription exceptions are caught and counted.
"""

from __future__ import annotations

import logging

from truebrief.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="truebrief.tasks.push_task.send_push_notifications_task",
    bind=False,
    max_retries=0,
)
def send_push_notifications_task(
    user_id: str,
    topic_name: str,
    brief_id: str,
) -> dict:
    """
    Send a push notification to all active browser subscriptions for user_id.

    Returns:
        {"sent": N, "failed": M}
    """
    from truebrief.push.client import send_push
    from truebrief.ledger.database import get_supabase

    db = get_supabase()
    sent = 0
    failed = 0

    try:
        res = (
            db.table("push_subscriptions")
            .select("id, endpoint, p256dh, auth")
            .eq("user_id", user_id)
            .eq("enabled", True)
            .execute()
        )
        subscriptions = res.data or []
    except Exception as exc:
        logger.error("[PUSH] Failed to fetch subscriptions for user %s: %s", user_id, exc)
        return {"sent": 0, "failed": 0}

    for row in subscriptions:
        subscription_info = {
            "endpoint": row["endpoint"],
            "keys": {
                "p256dh": row["p256dh"],
                "auth": row["auth"],
            },
        }
        ok = False
        try:
            ok = send_push(
                subscription_info=subscription_info,
                title="New Brief Ready",
                body=f"Your topic '{topic_name}' has a new brief.",
                url=f"/topics/{user_id}/briefs/{brief_id}",
            )
        except Exception as exc:
            logger.error("[PUSH] Unexpected error for subscription %s: %s", row["id"], exc)

        if ok:
            sent += 1
        else:
            failed += 1
            # Mark expired/invalid subscriptions so we don't keep retrying.
            try:
                db.table("push_subscriptions").update({"enabled": False}).eq("id", row["id"]).execute()
            except Exception as upd_exc:
                logger.warning("[PUSH] Could not disable stale subscription %s: %s", row["id"], upd_exc)

    logger.info("[PUSH] user=%s sent=%d failed=%d", user_id, sent, failed)
    return {"sent": sent, "failed": failed}
