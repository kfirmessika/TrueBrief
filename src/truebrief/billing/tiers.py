"""
Tier Enforcement — billing/tiers.py

Pure in-memory enforcement functions. Zero DB calls; all data comes from the
user_subscriptions row that the caller already loaded (or from TIER_LIMITS for
the user's current tier).

Enforcement points:
  - POST /api/v1/topics          → enforce_topic_limit
  - POST /api/v1/topics/{id}/scan → enforce_speed_limit
  - pipeline/runner.py           → get_allowed_sources
"""

from __future__ import annotations

import datetime
import logging
from typing import Optional

from fastapi import HTTPException

from truebrief.models.tier import TIER_LIMITS, Tier, TierLimits

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Admin bypass
# ---------------------------------------------------------------------------

def is_admin(email: Optional[str]) -> bool:
    """True for founder/admin accounts (settings.ADMIN_EMAILS) — these bypass ALL
    tier limits (scan speed, topic cap). Case-insensitive, comma-separated list."""
    if not email:
        return False
    try:
        from config.settings import settings
        admins = {e.strip().lower() for e in (settings.ADMIN_EMAILS or "").split(",") if e.strip()}
    except Exception:
        admins = set()
    return email.strip().lower() in admins


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_limits(tier_str: str) -> TierLimits:
    """Resolve a tier string to its TierLimits. Falls back to FREE on unknown input."""
    try:
        return TIER_LIMITS[Tier(tier_str)]
    except (ValueError, KeyError):
        logger.warning("Unknown tier '%s', defaulting to FREE limits.", tier_str)
        return TIER_LIMITS[Tier.FREE]


# ---------------------------------------------------------------------------
# Public enforcement API
# ---------------------------------------------------------------------------

def enforce_topic_limit(user_id: str, tier_str: str, current_topic_count: int) -> None:
    """
    Raise HTTP 402 if the user has reached their tier's topic cap.

    Args:
        user_id:             For logging context.
        tier_str:            User's current tier string ("free" | "pro" | "power").
        current_topic_count: How many topics this user currently owns.
    """
    limits = _get_limits(tier_str)
    if limits.max_topics == -1:
        return  # Unlimited (POWER tier)

    if current_topic_count >= limits.max_topics:
        logger.info(
            "Topic limit reached: user=%s tier=%s count=%d cap=%d",
            user_id, tier_str, current_topic_count, limits.max_topics,
        )
        raise HTTPException(
            status_code=402,
            detail=(
                f"Topic limit reached ({limits.max_topics} topics on {tier_str.title()} plan). "
                "Upgrade your plan to add more topics."
            ),
        )


def enforce_speed_limit(
    user_id: str,
    tier_str: str,
    last_scan_at: Optional[datetime.datetime],
) -> None:
    """
    Raise HTTP 429 if the user is trying to scan faster than their tier allows.

    Args:
        user_id:      For logging context.
        tier_str:     User's current tier string.
        last_scan_at: UTC datetime of the last scan, or None if never scanned.
    """
    limits = _get_limits(tier_str)
    min_interval_hours = limits.min_interval_hours

    if last_scan_at is None or min_interval_hours == 0:
        return  # No restriction (never scanned, or POWER tier)

    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    elapsed_hours = (now - last_scan_at).total_seconds() / 3600.0

    if elapsed_hours < min_interval_hours:
        wait_minutes = int((min_interval_hours - elapsed_hours) * 60)
        logger.info(
            "Speed limit hit: user=%s tier=%s elapsed=%.2fh required=%.2fh",
            user_id, tier_str, elapsed_hours, min_interval_hours,
        )
        raise HTTPException(
            status_code=429,
            detail=(
                f"Scan too soon ({tier_str.title()} plan requires {min_interval_hours}h between scans). "
                f"Try again in ~{wait_minutes} minute(s). Upgrade for faster updates."
            ),
        )


def get_allowed_sources(tier_str: str) -> list[str]:
    """
    Return the list of source plugin names this tier may access.

    Returns ["__all__"] for POWER tier (pipeline interprets as no filter).
    """
    limits = _get_limits(tier_str)
    return limits.sources
