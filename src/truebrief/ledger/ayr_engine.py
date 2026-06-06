"""
AYR Engine - ledger/ayr_engine.py

Implements the architecture-spec AYR formula:

  session_yield  = alphas / total          (NEW+UPDATE decisions / all decisions)
  AYR_new        = (session_yield × EMA_ALPHA) + (stored_ayr × (1 − EMA_ALPHA))
  poll_interval  = T_base / max(AYR_new, 0.1)

Where T_base = topics.user_interval_seconds (user's chosen base frequency).
Because AYR ≤ 1.0, poll_interval is ALWAYS ≥ T_base — the user's setting is the
fastest the pipeline can ever run. AYR only slows it down when topics go quiet.

If the user chose Auto (user_interval_seconds IS NULL), T_base falls back to the
fastest tier floor among the topic's subscribers.

Public surface:
  calculate_topic_ayr(topic_id, days)  → dict  (stats for API / debugging)
  update_topic_interval(topic_id)      → int   (new interval in seconds, or None)
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ── Configuration ─────────────────────────────────────────────────────────────

EMA_ALPHA   = 0.3     # weight of fresh session data vs stored history
MIN_SAMPLES = 5       # decisions needed before trusting the AYR signal
MIN_INTERVAL = 900    # 15 min — hard floor regardless of tier or AYR
MAX_INTERVAL = 86400  # 24 h  — hard ceiling regardless of AYR


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_tier_floor(db, topic_id: str) -> int:
    """
    Fastest allowed interval for this topic based on its subscribers' tiers.
    Power=900s, Pro=3600s, Free=86400s. Falls back to MAX_INTERVAL on error.
    Used as T_base when the user chose Auto (user_interval_seconds IS NULL).
    """
    try:
        subs = (
            db.table("topic_subscriptions")
            .select("user_id")
            .eq("topic_id", topic_id)
            .execute()
        )
        if not subs.data:
            return MAX_INTERVAL

        user_ids = [r["user_id"] for r in subs.data]

        tier_rows = (
            db.table("user_subscriptions")
            .select("tier")
            .in_("user_id", user_ids)
            .execute()
        )
        if not tier_rows.data:
            return MAX_INTERVAL

        tier_names = list({r["tier"] for r in tier_rows.data})
        ti_rows = (
            db.table("tier_intervals")
            .select("poll_interval_seconds")
            .in_("tier", tier_names)
            .execute()
        )
        if not ti_rows.data:
            return MAX_INTERVAL

        return min(r["poll_interval_seconds"] for r in ti_rows.data)

    except Exception as exc:
        logger.warning(f"[AYR] Could not compute tier floor for {topic_id}: {exc}")
        return MAX_INTERVAL


def _get_topic_row(db, topic_id: str) -> dict:
    """Return the topics row fields needed for AYR: user_interval_seconds, ayr_score."""
    try:
        res = (
            db.table("topics")
            .select("user_interval_seconds, ayr_score")
            .eq("id", topic_id)
            .single()
            .execute()
        )
        return res.data or {}
    except Exception as exc:
        logger.warning(f"[AYR] Could not read topic row for {topic_id}: {exc}")
        return {}


# ── Public API ────────────────────────────────────────────────────────────────

def calculate_topic_ayr(topic_id: str, days: int = 30) -> dict:
    """
    Compute AYR statistics for a topic over the last N days.

    Returns:
        {
          "topic_id":        str,
          "days":            int,
          "total":           int,    # total Arbiter decisions in window
          "alphas":          int,    # NEW + UPDATE
          "duplicates":      int,
          "session_yield":   float,  # alphas / total for this window (raw, not EMA)
          "ayr_score":       float,  # stored EMA score from DB
          "trusted":         bool,   # False if total < MIN_SAMPLES
          "t_base_s":        int,    # T_base used for interval formula
          "recommended_interval_s": int | None,
          "by_domain":       list,
        }
    """
    from truebrief.ledger.source_logger import SourceQualityLogger
    from truebrief.ledger.database import get_supabase

    logger.info(f"[AYR] Calculating AYR for topic={topic_id}, days={days}")

    sql = SourceQualityLogger()
    by_domain = sql.get_domain_stats(topic_id, days=days)

    total  = sum(d["total"]  for d in by_domain)
    alphas = sum(d["alphas"] for d in by_domain)
    dupes  = total - alphas

    session_yield = round(alphas / total, 4) if total > 0 else 0.0
    trusted = total >= MIN_SAMPLES

    db = get_supabase()
    topic_row = _get_topic_row(db, topic_id)

    stored_ayr = topic_row.get("ayr_score") or 0.5
    user_interval = topic_row.get("user_interval_seconds")  # None = Auto

    # EMA: blend fresh session data with stored history
    if trusted:
        ema_ayr = round((session_yield * EMA_ALPHA) + (stored_ayr * (1 - EMA_ALPHA)), 4)
    else:
        ema_ayr = stored_ayr  # not enough data — keep history as-is

    # T_base: user's chosen floor, or tier default for Auto
    if user_interval is not None:
        t_base = int(user_interval)
    else:
        t_base = _get_tier_floor(db, topic_id)

    if trusted:
        raw_interval = int(t_base / max(ema_ayr, 0.1))
        recommended = max(MIN_INTERVAL, min(MAX_INTERVAL, raw_interval))
    else:
        recommended = None

    logger.info(
        f"[AYR] topic={topic_id}: total={total}, alphas={alphas}, "
        f"session_yield={session_yield:.2%}, ema_ayr={ema_ayr:.2%}, "
        f"t_base={t_base}s, recommended={recommended}s, trusted={trusted}"
    )

    return {
        "topic_id":               topic_id,
        "days":                   days,
        "total":                  total,
        "alphas":                 alphas,
        "duplicates":             dupes,
        "session_yield":          session_yield,
        "ayr_score":              ema_ayr,
        "trusted":                trusted,
        "min_samples_required":   MIN_SAMPLES,
        "t_base_s":               t_base,
        "recommended_interval_s": recommended,
        "by_domain":              by_domain,
    }


def update_topic_interval(topic_id: str, days: int = 30) -> Optional[int]:
    """
    Recalculate AYR for a topic and update poll_interval_seconds in Supabase.

    Uses architecture formula: poll_interval = T_base / max(AYR_ema, 0.1)
    T_base = user_interval_seconds (never changes unless user edits it).
    AYR_ema is updated via exponential moving average each run.

    Because AYR ≤ 1.0, poll_interval is always ≥ T_base — the user's chosen
    frequency is a hard floor. AYR can only make polling slower, never faster.

    Called after every successful pipeline run. Fire-and-forget.
    Returns new interval in seconds, or None if not enough data yet.
    """
    try:
        stats = calculate_topic_ayr(topic_id, days=days)

        if not stats["trusted"]:
            logger.info(
                f"[AYR] Topic {topic_id}: only {stats['total']}/{MIN_SAMPLES} samples — "
                f"keeping existing interval, updating ayr_score to {stats['ayr_score']:.3f}"
            )
            # Still persist the EMA score even without enough data to change interval
            from truebrief.ledger.database import get_supabase
            get_supabase().table("topics").update(
                {"ayr_score": stats["ayr_score"]}
            ).eq("id", topic_id).execute()
            return None

        new_interval = stats["recommended_interval_s"]
        new_ayr      = stats["ayr_score"]

        from truebrief.ledger.database import get_supabase
        get_supabase().table("topics").update({
            "poll_interval_seconds": new_interval,
            "ayr_score":             new_ayr,
        }).eq("id", topic_id).execute()

        logger.info(
            f"[AYR] Updated topic {topic_id}: "
            f"session_yield={stats['session_yield']:.0%}, "
            f"ayr_ema={new_ayr:.3f}, "
            f"t_base={stats['t_base_s']}s → "
            f"poll_interval={new_interval}s ({new_interval // 60} min)"
        )
        return new_interval

    except Exception as exc:
        logger.error(f"[AYR] update_topic_interval failed for {topic_id}: {exc}")
        return None
