"""
Alarm-clock scheduling — ledger/alarm_schedule.py (V5, docs/core/architecture_v5.md §7)

Replaces AYR's adaptive poll_interval_seconds with explicit, user-set daily run times
(UTC hour:minute). Pure date math in this module (no DB), so it's trivially testable;
DB read/write helpers are thin wrappers at the bottom.
"""
from __future__ import annotations

import logging
from datetime import datetime, time, timedelta
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Used when a topic has zero configured schedule_times rows — one run/day, UTC.
DEFAULT_HOUR = 9
DEFAULT_MINUTE = 0

Times = List[Tuple[int, int]]


def compute_next_run(schedule_times: Times, now: datetime) -> datetime:
    """Return the soonest datetime STRICTLY AFTER `now` matching one of the given
    (hour, minute) UTC times. Falls back to one default time/day when the list is empty.

    Callers that must guarantee moving past a slot that just fired (the scheduler,
    after enqueuing) should pass `now=fired_at + timedelta(minutes=1)` — this function
    itself only guarantees "after now", not "after the last fire", to keep it a pure,
    single-purpose date computation.
    """
    times = schedule_times or [(DEFAULT_HOUR, DEFAULT_MINUTE)]
    today = now.date()
    candidates = []
    for hour, minute in times:
        candidate = datetime.combine(today, time(hour=hour, minute=minute))
        if candidate <= now:
            candidate += timedelta(days=1)
        candidates.append(candidate)
    return min(candidates)


def min_spacing_hours_ok(schedule_times: Times, min_interval_hours: float) -> bool:
    """True if every pair of times is at least min_interval_hours apart (wrapping
    across midnight). Reuses the EXISTING tier meaning (models/tier.py
    TIER_LIMITS.min_interval_hours, "this tier can't scan faster than X") instead of
    inventing a separate max-times-per-day tier dimension: free's 24h floor naturally
    allows only one time/day, pro's 1h floor allows up to 24, etc.
    """
    if min_interval_hours <= 0 or len(schedule_times) <= 1:
        return True
    minutes = sorted(h * 60 + m for h, m in schedule_times)
    n = len(minutes)
    min_gap_minutes = min_interval_hours * 60
    for i in range(n):
        nxt = minutes[(i + 1) % n]
        gap = (nxt - minutes[i]) % (24 * 60)
        if gap == 0:
            continue  # duplicate; the unique DB constraint already prevents this
        if gap < min_gap_minutes:
            return False
    return True


# ── DB helpers ────────────────────────────────────────────────────────────────

def get_schedule_times(db, topic_id: str) -> Times:
    """Read a topic's configured (hour, minute) times, ordered. Empty list = default."""
    res = (
        db.table("topic_schedule_times")
        .select("hour, minute")
        .eq("topic_id", topic_id)
        .order("hour")
        .order("minute")
        .execute()
    )
    return [(r["hour"], r["minute"]) for r in (res.data or [])]


def set_schedule_times(db, topic_id: str, schedule_times: Times) -> None:
    """Replace a topic's schedule times with the given list (delete-then-insert)."""
    db.table("topic_schedule_times").delete().eq("topic_id", topic_id).execute()
    if schedule_times:
        rows = [{"topic_id": topic_id, "hour": h, "minute": m} for h, m in schedule_times]
        db.table("topic_schedule_times").insert(rows).execute()


def reschedule_topic(db, topic_id: str, anchor: Optional[datetime] = None) -> datetime:
    """Read the topic's schedule times, compute its next run, and write next_run_at.
    Returns the computed next_run_at (UTC, naive)."""
    from datetime import timezone

    now = anchor or datetime.now(timezone.utc).replace(tzinfo=None)
    times = get_schedule_times(db, topic_id)
    next_run = compute_next_run(times, now)
    db.table("topics").update({"next_run_at": next_run.isoformat()}).eq("id", topic_id).execute()
    return next_run
