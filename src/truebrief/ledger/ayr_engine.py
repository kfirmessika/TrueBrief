"""
AYR Engine - ledger/ayr_engine.py

Calculates Alpha Yield Rate (AYR) per topic and dynamically adjusts poll intervals.

AYR Definition:
  AYR = (NEW + UPDATE decisions) / total decisions for a topic

  Range: 0.0 (pure noise - everything was a duplicate)
         1.0 (pure signal - every article yielded new information)

AYR → Poll Interval Logic:
  High AYR  → poll more often  (topic is actively changing)
  Low AYR   → poll less often  (topic has gone quiet; save resources)

Interval bands (tunable in AYR_BANDS below):
  AYR >= 0.70 → 30 min   (hot topic - breaking developments)
  AYR >= 0.50 → 1 hour   (active topic - default)
  AYR >= 0.30 → 2 hours  (moderate activity)
  AYR >= 0.10 → 4 hours  (low activity - cooling down)
  AYR < 0.10  → 6 hours  (dormant - minimal new info expected)

MIN_SAMPLES guard:
  AYR is only trusted after MIN_SAMPLES decisions have been logged.
  Below that threshold, the topic keeps its configured interval unchanged.
  This prevents an overreaction on the very first pipeline run.

Public surface:
  calculate_topic_ayr(topic_id, days)  → dict  (stats for API / debugging)
  update_topic_interval(topic_id)      → int   (new interval in seconds)
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ── Configuration ─────────────────────────────────────────────────────────────

# Minimum decisions logged before we trust the AYR signal
MIN_SAMPLES = 5

# (min_ayr, interval_seconds) - evaluated top-to-bottom, first match wins
AYR_BANDS: list[tuple[float, int]] = [
    (0.70, 1800),    # ≥ 70% yield → 30 min
    (0.50, 3600),    # ≥ 50% yield → 1 hour  (standard)
    (0.30, 7200),    # ≥ 30% yield → 2 hours
    (0.10, 14400),   # ≥ 10% yield → 4 hours
    (0.00, 21600),   # <  10% yield → 6 hours (dormant)
]

# Hard bounds - never poll faster than 15 min or slower than 24 hours
MIN_INTERVAL = 900       # 15 minutes
MAX_INTERVAL = 86400     # 24 hours


# ── Public API ─────────────────────────────────────────────────────────────────

def ayr_to_interval(ayr: float) -> int:
    """
    Convert an AYR score (0.0–1.0) to a poll interval in seconds.

    Args:
        ayr: Alpha Yield Rate - fraction of decisions that were NEW or UPDATE.

    Returns:
        Interval in seconds (clamped between MIN_INTERVAL and MAX_INTERVAL).
    """
    for threshold, interval in AYR_BANDS:
        if ayr >= threshold:
            return max(MIN_INTERVAL, min(MAX_INTERVAL, interval))
    # Fallback - should never reach here due to 0.00 catch-all band
    return MAX_INTERVAL


def calculate_topic_ayr(topic_id: str, days: int = 30) -> dict:
    """
    Compute AYR statistics for a topic over the last N days.

    Queries `source_quality_log` and aggregates:
      - total decisions logged
      - alphas (NEW + UPDATE decisions)
      - overall AYR = alphas / total
      - per-domain breakdown

    Returns:
        {
          "topic_id":        str,
          "days":            int,
          "total":           int,      # total decisions in window
          "alphas":          int,      # NEW + UPDATE
          "duplicates":      int,
          "ayr":             float,    # 0.0 to 1.0
          "trusted":         bool,     # False if total < MIN_SAMPLES
          "recommended_interval_s": int,
          "by_domain": [
            {"source_domain": str, "total": int, "alphas": int, "ayr": float},
            ...
          ]
        }
    """
    from truebrief.ledger.source_logger import SourceQualityLogger

    logger.info(f"[AYR] Calculating AYR for topic={topic_id}, days={days}")

    sql = SourceQualityLogger()
    by_domain = sql.get_domain_stats(topic_id, days=days)

    total   = sum(d["total"]  for d in by_domain)
    alphas  = sum(d["alphas"] for d in by_domain)
    dupes   = total - alphas

    if total == 0:
        ayr = 0.0
    else:
        ayr = round(alphas / total, 4)

    trusted = total >= MIN_SAMPLES
    recommended_interval = ayr_to_interval(ayr) if trusted else None

    logger.info(
        f"[AYR] topic={topic_id}: total={total}, alphas={alphas}, "
        f"ayr={ayr:.2%}, trusted={trusted}, "
        f"recommended={recommended_interval}s"
    )

    return {
        "topic_id":               topic_id,
        "days":                   days,
        "total":                  total,
        "alphas":                 alphas,
        "duplicates":             dupes,
        "ayr":                    ayr,
        "trusted":                trusted,
        "min_samples_required":   MIN_SAMPLES,
        "recommended_interval_s": recommended_interval,
        "by_domain":              by_domain,
    }


def _get_tier_floor(db, topic_id: str) -> int:
    """
    Return the minimum allowed poll_interval_seconds for this topic based on
    the fastest-tier subscriber.  Power=900s, Pro=3600s, Free=86400s.

    Falls back to MAX_INTERVAL on any error so we never accidentally over-poll.
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
        logger.warning(f"[AYR] Could not compute tier floor for topic {topic_id}: {exc}")
        return MAX_INTERVAL


def _get_user_floor(db, topic_id: str) -> Optional[int]:
    """
    Return topics.user_interval_seconds — the user's locked minimum interval.
    Returns None when user chose Auto (AYR controls freely).
    """
    try:
        res = (
            db.table("topics")
            .select("user_interval_seconds")
            .eq("id", topic_id)
            .single()
            .execute()
        )
        val = (res.data or {}).get("user_interval_seconds")
        return int(val) if val is not None else None
    except Exception as exc:
        logger.warning(f"[AYR] Could not read user_interval_seconds for topic {topic_id}: {exc}")
        return None


def update_topic_interval(topic_id: str, days: int = 30) -> Optional[int]:
    """
    Recalculate AYR for a topic and update poll_interval_seconds in Supabase.

    The final interval is max(ayr_recommended, tier_floor) so that:
      - free-tier topics never poll faster than every 24 h
      - power-tier topics poll at the AYR-recommended rate (down to MIN_INTERVAL)

    Called after every successful pipeline run (in pipeline_task.py).
    Fire-and-forget: any DB error is logged but never propagates.

    Returns:
        New interval in seconds, or None if not updated (not enough data, or error).
    """
    try:
        stats = calculate_topic_ayr(topic_id, days=days)

        if not stats["trusted"]:
            logger.info(
                f"[AYR] Topic {topic_id}: only {stats['total']}/{MIN_SAMPLES} samples - "
                f"keeping existing interval."
            )
            return None

        ayr_interval = stats["recommended_interval_s"]

        from truebrief.ledger.database import get_supabase
        db = get_supabase()

        tier_floor    = _get_tier_floor(db, topic_id)
        user_floor    = _get_user_floor(db, topic_id)  # None = Auto

        # Final interval = slowest of (AYR recommendation, user preference, tier floor)
        # This ensures AYR never fires faster than what the user explicitly chose.
        candidates = [ayr_interval, tier_floor]
        if user_floor is not None:
            candidates.append(user_floor)
        new_interval = max(candidates)

        db.table("topics").update({
            "poll_interval_seconds": new_interval
        }).eq("id", topic_id).execute()

        ayr_pct = f"{stats['ayr']:.0%}"
        logger.info(
            f"[AYR] Updated topic {topic_id}: "
            f"AYR={ayr_pct} → ayr={ayr_interval}s, "
            f"tier_floor={tier_floor}s, user_floor={user_floor}s → final={new_interval}s "
            f"({new_interval // 60} min)"
        )
        return new_interval

    except Exception as exc:
        logger.error(f"[AYR] update_topic_interval failed for {topic_id}: {exc}")
        return None
