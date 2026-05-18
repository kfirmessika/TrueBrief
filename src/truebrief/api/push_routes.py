"""
Push Notification API Routes — api/push_routes.py

Endpoints for managing browser push subscriptions and sending test pushes.

Routes:
  GET  /push/vapid-public-key  → return VAPID public key (no auth required)
  POST /push/subscribe          → upsert a push subscription for the current user
  DELETE /push/subscribe        → disable subscription by endpoint
  POST /push/test               → send a test push to the current user (dev tool)
"""

from __future__ import annotations

import logging
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from truebrief.api.rate_limit import limiter
from truebrief.auth.dependencies import User, get_current_user
from truebrief.ledger.database import get_supabase

router = APIRouter(prefix="/push", tags=["push"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class PushSubscribeRequest(BaseModel):
    endpoint: str
    p256dh: str
    auth: str


class PushSubscribeResponse(BaseModel):
    status: Literal["subscribed", "updated"]


class PushUnsubscribeRequest(BaseModel):
    endpoint: str


class PushTestResponse(BaseModel):
    status: Literal["sent", "skipped", "error"]
    detail: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/vapid-public-key")
def get_vapid_public_key():
    """Return the VAPID public key for the frontend to create push subscriptions."""
    public_key = os.getenv("VAPID_PUBLIC_KEY", "")
    if not public_key:
        raise HTTPException(
            status_code=503,
            detail="Web Push is not configured on this server.",
        )
    return {"public_key": public_key}


@router.post("/subscribe", response_model=PushSubscribeResponse)
@limiter.limit("10/hour")
def subscribe(
    request: Request,
    body: PushSubscribeRequest,
    user: User = Depends(get_current_user),
):
    """
    Upsert a browser push subscription for the current user.
    If the same endpoint already exists, mark it enabled and update keys.
    """
    db = get_supabase()

    upsert_data = {
        "user_id": user.id,
        "endpoint": body.endpoint,
        "p256dh": body.p256dh,
        "auth": body.auth,
        "enabled": True,
    }

    try:
        res = (
            db.table("push_subscriptions")
            .upsert(upsert_data, on_conflict="user_id,endpoint")
            .execute()
        )
        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to save push subscription.")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error upserting push subscription for user %s: %s", user.id, exc)
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    return PushSubscribeResponse(status="subscribed")


@router.delete("/subscribe")
def unsubscribe(
    body: PushUnsubscribeRequest,
    user: User = Depends(get_current_user),
):
    """Disable a push subscription by endpoint for the current user."""
    db = get_supabase()

    try:
        db.table("push_subscriptions").update({"enabled": False}).eq(
            "user_id", user.id
        ).eq("endpoint", body.endpoint).execute()
    except Exception as exc:
        logger.error("Error disabling push subscription for user %s: %s", user.id, exc)
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    return {"status": "unsubscribed"}


@router.post("/test", response_model=PushTestResponse)
@limiter.limit("5/hour")
def test_push(request: Request, user: User = Depends(get_current_user)):
    """
    Send a test push notification to all active subscriptions for the current user.
    Useful for developer testing without waiting for a real brief.
    """
    from truebrief.push.client import send_push

    db = get_supabase()

    try:
        res = (
            db.table("push_subscriptions")
            .select("id, endpoint, p256dh, auth")
            .eq("user_id", user.id)
            .eq("enabled", True)
            .execute()
        )
        subscriptions = res.data or []
    except Exception as exc:
        logger.error("Failed to fetch subscriptions for test push, user %s: %s", user.id, exc)
        return PushTestResponse(status="error", detail=str(exc))

    if not subscriptions:
        return PushTestResponse(status="skipped", detail="No active subscriptions found.")

    any_sent = False
    for row in subscriptions:
        ok = send_push(
            subscription_info={
                "endpoint": row["endpoint"],
                "keys": {"p256dh": row["p256dh"], "auth": row["auth"]},
            },
            title="TrueBrief Test",
            body="Push notifications are working correctly.",
            url="/dashboard",
        )
        if ok:
            any_sent = True

    if any_sent:
        return PushTestResponse(status="sent")
    return PushTestResponse(status="error", detail="All push attempts failed.")
