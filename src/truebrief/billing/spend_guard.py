"""
Spend guardrails — billing/spend_guard.py

Two brakes on user-triggered pipeline spend. Both fail OPEN: if the brake itself
errors (Redis down, RPC missing), the scan proceeds — a broken guardrail must
never take the product down.

  1. Per-account daily scan cap — an atomic Redis counter, INCR per user-initiated
     scan, keyed by user id + UTC date, 48h TTL. This is the brake the per-topic
     `min_interval_hours` limit misses: deleting a topic and recreating it resets
     `last_run_at`, so create → scan → delete → recreate is otherwise an unbounded
     loop. Caps live in TIER_LIMITS.max_scans_per_day. Admins bypass.

  2. Global daily spend circuit-breaker — reads today's total from the
     `llm_cost_by_day` RPC; once it crosses settings.GLOBAL_DAILY_SPEND_CEILING_USD
     every non-admin scan trigger gets a 503 until 00:00 UTC. Admins bypass.
     Set the ceiling to 0 to disable.

Wired into POST /api/v1/topics (new-topic branch) and POST /api/v1/topics/{id}/scan,
immediately before enqueue_pipeline.
"""

from __future__ import annotations

import datetime
import logging

from fastapi import HTTPException

from config.settings import settings
from truebrief.billing.tiers import is_admin
from truebrief.models.tier import TIER_LIMITS, Tier

logger = logging.getLogger(__name__)

_SCAN_COUNTER_TTL_SECONDS = 172_800  # 48h — comfortably past any UTC-day boundary


def _utc_today() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")


def _counter_key(user_id: str) -> str:
    return f"scans:{user_id}:{_utc_today()}"


def _max_scans_for_tier(tier_str: str) -> int:
    try:
        return TIER_LIMITS[Tier(tier_str)].max_scans_per_day
    except (ValueError, KeyError):
        return TIER_LIMITS[Tier.FREE].max_scans_per_day


def enforce_and_record_scan_cap(user_id: str, tier_str: str, email: str | None) -> None:
    """Atomically count this scan against the user's UTC-day cap; raise 429 if over.

    Call this exactly once per user-initiated scan, right before enqueue. Admins and
    unlimited tiers are not counted. Fails open on any Redis error.
    """
    if is_admin(email):
        return

    cap = _max_scans_for_tier(tier_str)
    if cap < 0:
        return  # unlimited tier

    from truebrief.api.cache import _get_redis

    r = _get_redis()
    if r is None:
        return  # no Redis (dev / outage) — fail open

    try:
        key = _counter_key(user_id)
        count = r.incr(key)
        if count == 1:
            r.expire(key, _SCAN_COUNTER_TTL_SECONDS)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("[SPEND-GUARD] scan-cap counter unavailable, allowing scan: %s", exc)
        return

    if count > cap:
        logger.info(
            "[SPEND-GUARD] daily scan cap hit: user=%s tier=%s count=%d cap=%d",
            user_id, tier_str, count, cap,
        )
        raise HTTPException(
            status_code=429,
            detail=(
                f"Daily scan limit reached ({cap} scans/day on the {tier_str.title()} plan). "
                "Resets at 00:00 UTC. Upgrade for a higher limit."
            ),
        )


def enforce_global_spend_ceiling(db, email: str | None) -> None:
    """Raise 503 if today's total LLM spend (UTC) is at/over the configured ceiling.

    Admins bypass. A ceiling of 0 disables the breaker. Fails open if the cost RPC
    is unavailable.
    """
    if is_admin(email):
        return

    ceiling = float(settings.GLOBAL_DAILY_SPEND_CEILING_USD or 0.0)
    if ceiling <= 0:
        return

    try:
        rows = db.rpc("llm_cost_by_day", {"days_back": 1}).execute().data or []
        today = _utc_today_date()
        spent = 0.0
        for row in rows:
            if str(row.get("day")) == today:
                spent = float(row.get("total_cost_usd") or 0.0)
                break
    except Exception as exc:
        logger.warning("[SPEND-GUARD] global spend check unavailable, allowing scan: %s", exc)
        return

    if spent >= ceiling:
        logger.error(
            "[SPEND-GUARD] global daily spend ceiling hit: spent=$%.2f ceiling=$%.2f — blocking non-admin scans",
            spent, ceiling,
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "TrueBrief has reached its daily processing budget. "
                "New scans resume at 00:00 UTC."
            ),
        )


def _utc_today_date() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
