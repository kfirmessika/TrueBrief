"""
API Key Service — apikeys/service.py

Key lifecycle + verification + usage metering for the developer API product.

Security model:
  - Full key format: tb_live_<43 url-safe chars> (256 bits of entropy).
  - Only the SHA-256 hex of the full key is stored; lookup is by hash.
    The plaintext key is returned to the user exactly once, at creation.
  - Revocation is soft (revoked_at) so usage history survives.
  - Per-tier daily quota enforced via the increment_api_usage() Postgres
    function (atomic upsert-increment, returns the new count).
"""

from __future__ import annotations

import datetime
import hashlib
import logging
import secrets
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException

from truebrief.models.tier import TIER_LIMITS, Tier

logger = logging.getLogger(__name__)

KEY_PREFIX = "tb_live_"
MAX_ACTIVE_KEYS_PER_USER = 5
PREFIX_DISPLAY_LEN = 12  # chars of the key shown in list views, e.g. "tb_live_Ab3d"


# ---------------------------------------------------------------------------
# Key material
# ---------------------------------------------------------------------------

def generate_key() -> tuple[str, str, str]:
    """Return (full_key, key_hash, key_prefix). full_key is shown once, never stored."""
    full_key = KEY_PREFIX + secrets.token_urlsafe(32)
    return full_key, hash_key(full_key), full_key[:PREFIX_DISPLAY_LEN]


def hash_key(full_key: str) -> str:
    return hashlib.sha256(full_key.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Verification (the public-API auth path)
# ---------------------------------------------------------------------------

@dataclass
class ApiKeyIdentity:
    key_id: str
    user_id: str
    user_email: str
    tier: str  # "free" | "pro" | "power"


def verify_api_key(db, full_key: str) -> ApiKeyIdentity:
    """Resolve a presented key to its owner, or raise 401.

    Looks up by hash (unique index), rejects revoked keys, and joins the
    owner's tier from user_subscriptions (missing row = free).
    """
    if not full_key or not full_key.startswith(KEY_PREFIX):
        raise HTTPException(status_code=401, detail="Invalid API key.")

    res = (
        db.table("api_keys")
        .select("id, user_id, revoked_at")
        .eq("key_hash", hash_key(full_key))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=401, detail="Invalid API key.")
    row = res.data[0]
    if row.get("revoked_at"):
        raise HTTPException(status_code=401, detail="API key has been revoked.")

    user_res = db.table("users").select("id, email").eq("id", row["user_id"]).execute()
    if not user_res.data:
        raise HTTPException(status_code=401, detail="Invalid API key.")
    user = user_res.data[0]

    sub_res = (
        db.table("user_subscriptions")
        .select("tier")
        .eq("user_id", row["user_id"])
        .execute()
    )
    tier = (sub_res.data[0].get("tier") if sub_res.data else None) or "free"

    # Best-effort last_used stamp — never let it fail a request.
    try:
        db.table("api_keys").update(
            {"last_used_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
        ).eq("id", row["id"]).execute()
    except Exception:
        pass

    return ApiKeyIdentity(
        key_id=row["id"], user_id=user["id"], user_email=user.get("email", ""), tier=tier
    )


# ---------------------------------------------------------------------------
# Quota metering
# ---------------------------------------------------------------------------

def daily_limit_for_tier(tier_str: str) -> int:
    try:
        return TIER_LIMITS[Tier(tier_str)].api_calls_per_day
    except (ValueError, KeyError):
        return TIER_LIMITS[Tier.FREE].api_calls_per_day


def meter_and_enforce(db, identity: ApiKeyIdentity) -> None:
    """Count this call and raise 402/429 if the tier's daily quota is exceeded.

    402 = tier has NO API access (free) — upgrade required.
    429 = quota exhausted for today.
    """
    limit = daily_limit_for_tier(identity.tier)
    if limit == 0:
        raise HTTPException(
            status_code=402,
            detail="The developer API requires a Pro or Power plan.",
        )

    today = datetime.date.today().isoformat()
    try:
        # RPC increments this key's counter and returns the USER's daily total
        # across all keys — quota is per-user, not per-key.
        res = db.rpc(
            "increment_api_usage",
            {"p_key_id": identity.key_id, "p_user_id": identity.user_id, "p_day": today},
        ).execute()
        user_total = res.data if isinstance(res.data, int) else int(res.data or 0)
    except Exception as exc:
        # Metering failure must not take the API down — log and allow.
        logger.error("API usage metering failed for key %s: %s", identity.key_id, exc)
        return

    if limit != -1 and user_total > limit:
        raise HTTPException(
            status_code=429,
            detail=f"Daily API quota reached ({limit} calls/day on the {identity.tier} plan).",
        )


def get_usage_today(db, identity: ApiKeyIdentity) -> dict:
    """Return today's usage across ALL of the user's keys, plus the tier limit."""
    today = datetime.date.today().isoformat()
    res = (
        db.table("api_usage_daily")
        .select("count")
        .eq("user_id", identity.user_id)
        .eq("day", today)
        .execute()
    )
    used = sum(r.get("count", 0) for r in (res.data or []))
    return {
        "day": today,
        "calls_used": used,
        "daily_limit": daily_limit_for_tier(identity.tier),
        "tier": identity.tier,
    }
