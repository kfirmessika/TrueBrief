"""
Web Push Client — push/client.py

Wraps pywebpush to send browser push notifications via the Web Push Protocol (VAPID).
Reads VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY, and VAPID_SUBJECT from environment.

Returns True on success, False on any error (never raises — callers handle retries).
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

VAPID_PRIVATE_KEY: str = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY: str = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_SUBJECT: str = os.getenv("VAPID_SUBJECT", "mailto:admin@truebrief.ai")


def send_push(
    subscription_info: dict,
    title: str,
    body: str,
    url: str = "/dashboard",
) -> bool:
    """
    Send a single Web Push notification.

    Args:
        subscription_info: {"endpoint": ..., "keys": {"p256dh": ..., "auth": ...}}
        title: Notification title shown to the user.
        body:  Notification body text.
        url:   URL to open when the user clicks the notification.

    Returns:
        True on success, False if the endpoint rejected the push or keys are missing.
    """
    if not VAPID_PRIVATE_KEY:
        logger.warning("VAPID_PRIVATE_KEY not set — skipping push notification.")
        return False

    try:
        from pywebpush import webpush, WebPushException  # lazy import

        webpush(
            subscription_info=subscription_info,
            data=json.dumps({"title": title, "body": body, "url": url}),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_SUBJECT},
        )
        return True

    except Exception as exc:  # noqa: BLE001
        # WebPushException wraps 404/410 (expired endpoint) and other HTTP errors.
        logger.warning("Push notification failed: %s", exc)
        return False
