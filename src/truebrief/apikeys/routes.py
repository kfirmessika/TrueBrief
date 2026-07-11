"""
API Key Management Routes — apikeys/routes.py

Clerk-authenticated endpoints for the settings UI. Creating a key requires a
paid tier (the free tier has api_calls_per_day=0, so a key would be useless
and confusing). The full key is returned exactly once, at creation.

Routes (mounted under /api/v1):
  POST   /api-keys        → create a key (returns full key ONCE)
  GET    /api-keys        → list keys (prefix + metadata, never the key)
  DELETE /api-keys/{id}   → revoke a key (soft)
  GET    /api-keys/usage  → today's usage vs the tier's daily quota
"""

from __future__ import annotations

import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from truebrief.api.rate_limit import limiter
from truebrief.apikeys.service import (
    MAX_ACTIVE_KEYS_PER_USER,
    daily_limit_for_tier,
    generate_key,
)
from truebrief.auth.dependencies import User, get_current_user
from truebrief.ledger.database import get_supabase

router = APIRouter(prefix="/api-keys", tags=["api-keys"])
logger = logging.getLogger(__name__)


class CreateKeyRequest(BaseModel):
    name: str = Field(default="default", min_length=1, max_length=60)


def _user_tier(db, user_id: str) -> str:
    res = db.table("user_subscriptions").select("tier").eq("user_id", user_id).execute()
    return (res.data[0].get("tier") if res.data else None) or "free"


@router.post("")
@limiter.limit("10/hour")
def create_api_key(request: Request, body: CreateKeyRequest, user: User = Depends(get_current_user)):
    db = get_supabase()

    tier = _user_tier(db, user.id)
    if daily_limit_for_tier(tier) == 0:
        raise HTTPException(
            status_code=402,
            detail="The developer API requires a Pro or Power plan. Upgrade to create API keys.",
        )

    active = (
        db.table("api_keys")
        .select("id")
        .eq("user_id", user.id)
        .is_("revoked_at", "null")
        .execute()
    )
    if len(active.data or []) >= MAX_ACTIVE_KEYS_PER_USER:
        raise HTTPException(
            status_code=400,
            detail=f"Key limit reached ({MAX_ACTIVE_KEYS_PER_USER} active keys). Revoke one first.",
        )

    full_key, key_hash, key_prefix = generate_key()
    try:
        res = (
            db.table("api_keys")
            .insert({
                "user_id": user.id,
                "name": body.name.strip(),
                "key_hash": key_hash,
                "key_prefix": key_prefix,
            })
            .execute()
        )
        if not res.data:
            raise HTTPException(status_code=500, detail="Could not create API key.")
        row = res.data[0]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("API key creation failed for user %s: %s", user.id, exc)
        raise HTTPException(status_code=500, detail="Could not create API key.") from exc

    return {
        "id": row["id"],
        "name": row["name"],
        "key": full_key,  # shown ONCE — never retrievable again
        "key_prefix": key_prefix,
        "created_at": row.get("created_at"),
    }


@router.get("")
def list_api_keys(user: User = Depends(get_current_user)):
    db = get_supabase()
    res = (
        db.table("api_keys")
        .select("id, name, key_prefix, created_at, last_used_at, revoked_at")
        .eq("user_id", user.id)
        .order("created_at", desc=True)
        .execute()
    )
    return {"keys": res.data or []}


@router.delete("/{key_id}")
def revoke_api_key(key_id: str, user: User = Depends(get_current_user)):
    db = get_supabase()
    # Ownership check before revoke — never trust the id alone.
    res = db.table("api_keys").select("id, user_id, revoked_at").eq("id", key_id).execute()
    if not res.data or res.data[0]["user_id"] != user.id:
        raise HTTPException(status_code=404, detail="API key not found.")
    if res.data[0].get("revoked_at"):
        return {"status": "already_revoked"}

    db.table("api_keys").update(
        {"revoked_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    ).eq("id", key_id).execute()
    return {"status": "revoked"}


@router.get("/usage")
def get_my_usage(user: User = Depends(get_current_user)):
    db = get_supabase()
    tier = _user_tier(db, user.id)
    today = datetime.date.today().isoformat()
    res = (
        db.table("api_usage_daily")
        .select("count")
        .eq("user_id", user.id)
        .eq("day", today)
        .execute()
    )
    used = sum(r.get("count", 0) for r in (res.data or []))
    return {
        "day": today,
        "calls_used": used,
        "daily_limit": daily_limit_for_tier(tier),
        "tier": tier,
    }
