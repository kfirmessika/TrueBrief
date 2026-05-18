"""
Digest API Routes — api/digest_routes.py

Endpoints for managing a user's email digest preferences.

All endpoints require authentication via get_current_user.

Routes:
  GET  /digest/settings   → return the user's digest_settings (or defaults)
  PUT  /digest/settings   → upsert digest_settings
  POST /digest/preview    → trigger a digest send for the requesting user immediately
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from truebrief.auth.dependencies import User, get_current_user
from truebrief.ledger.database import get_supabase

router = APIRouter(prefix="/digest", tags=["digest"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class DigestSettingsResponse(BaseModel):
    user_id: str
    enabled: bool
    frequency: str
    send_hour_utc: int


class DigestSettingsUpdate(BaseModel):
    enabled: bool = True
    frequency: Literal["daily", "weekly"] = "daily"
    send_hour_utc: int = Field(default=8, ge=0, le=23)


class DigestPreviewResponse(BaseModel):
    status: Literal["sent", "skipped", "error"]
    detail: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/settings", response_model=DigestSettingsResponse)
def get_digest_settings(user: User = Depends(get_current_user)):
    """
    Return the current user's digest settings.
    If no row exists yet, returns the default values without writing to DB.
    """
    db = get_supabase()
    res = (
        db.table("digest_settings")
        .select("*")
        .eq("user_id", user.id)
        .execute()
    )

    if res.data:
        row = res.data[0]
        return DigestSettingsResponse(
            user_id=row["user_id"],
            enabled=row["enabled"],
            frequency=row["frequency"],
            send_hour_utc=row["send_hour_utc"],
        )

    # Return defaults without persisting (first-time user)
    return DigestSettingsResponse(
        user_id=user.id,
        enabled=True,
        frequency="daily",
        send_hour_utc=8,
    )


@router.put("/settings", response_model=DigestSettingsResponse)
def update_digest_settings(
    body: DigestSettingsUpdate,
    user: User = Depends(get_current_user),
):
    """
    Upsert the current user's digest settings.
    Creates the row on first call; updates on subsequent calls.
    """
    db = get_supabase()

    upsert_data = {
        "user_id": user.id,
        "enabled": body.enabled,
        "frequency": body.frequency,
        "send_hour_utc": body.send_hour_utc,
    }

    try:
        res = (
            db.table("digest_settings")
            .upsert(upsert_data, on_conflict="user_id")
            .execute()
        )
        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to save digest settings.")
        row = res.data[0]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error upserting digest_settings for user %s: %s", user.id, exc)
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    return DigestSettingsResponse(
        user_id=row["user_id"],
        enabled=row["enabled"],
        frequency=row["frequency"],
        send_hour_utc=row["send_hour_utc"],
    )


@router.post("/preview", response_model=DigestPreviewResponse)
def preview_digest(user: User = Depends(get_current_user)):
    """
    Immediately trigger a digest email for the requesting user.

    Useful for:
      - Developer testing without waiting for the Beat schedule
      - Frontend "Send me a test digest" feature

    Returns {"status": "sent"} or {"status": "skipped"} depending on
    whether the user had any recent briefs.
    """
    from truebrief.digest.mailer import send_digest_email
    from truebrief.digest.renderer import render_digest
    from truebrief.tasks.digest_task import _process_user

    db = get_supabase()

    # Ensure the user row exists before attempting to fetch email
    user_res = db.table("users").select("email").eq("id", user.id).execute()
    if not user_res.data:
        raise HTTPException(
            status_code=404,
            detail="User record not found. Ensure you have completed onboarding.",
        )

    try:
        result = _process_user(
            db=db,
            user_id=user.id,
            frequency="daily",
            send_fn=send_digest_email,
            render_fn=render_digest,
        )
        return DigestPreviewResponse(status=result)  # type: ignore[arg-type]
    except Exception as exc:
        logger.error("Digest preview failed for user %s: %s", user.id, exc)
        return DigestPreviewResponse(status="error", detail=str(exc))
