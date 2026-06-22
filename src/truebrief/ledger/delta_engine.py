"""
Delta Engine — ledger/delta_engine.py  (architecture §8 / §8B, build-seq step 10)

The per-user "what's new since you looked" feed. $0 LLM — pure Postgres reads.
For each topic a user subscribes to, the feed is simply:

    known_facts WHERE first_seen_at > <the user's anchor for that topic>

Two anchors, ONE feed (§8/§13):
  - "seen"   → last_seen_at   → the LIVE window (open often = real-time feel)
  - "digest" → last_digest_at → the DAILY SUMMARY window (open once a day = digest feel)

Reading advances last_seen_at, so "all caught up" (zero new) is a first-class state.

§8B development-recency gate: a fact first-seen today but DATED far in the past is
"new to us, not new to the world" — it belongs in the History timeline (§7.2), not at
the top of today. We drop such large-lag backfills from the feed.

Requires migration 019 (user_topic_state). Degrades gracefully: a missing state row
is treated as a short look-back window so existing users still get a sensible feed.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# A (user, topic) with no state row yet is treated as "looked this long ago" — so
# existing users see recent activity without the entire backlog dumping as "new".
DEFAULT_WINDOW_HOURS = 48

# §8B: a fact whose development pre-dates when we first saw it by more than this is a
# historical backfill → route to History, never the live feed.
BACKFILL_LAG_DAYS = 45

# Per-topic cap so one noisy topic can't swamp the cross-topic feed.
PER_TOPIC_CAP = 15

# Significance ordering — mirrors the runner's IC2 class weights so the feed ranks
# facts the same way the brief and the history timeline do.
_CLASS_WEIGHT = {
    "state_change": 1.0,
    "escalation":   0.8,
    "development":  0.6,
    "incremental":  0.4,
    "routine":      0.2,
    "tally":        0.1,
}

_FACT_COLS = (
    "alpha_text, context, event_class, event_date, first_seen_at, "
    "source_domain, source_url, verified_count"
)


def _parse_ts(val) -> Optional[datetime]:
    if not val:
        return None
    try:
        s = str(val).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _is_backfill(row: dict) -> bool:
    """True if the fact's development long pre-dates when we first saw it (§8B)."""
    ev = _parse_ts(row.get("event_date"))
    seen = _parse_ts(row.get("first_seen_at"))
    if not ev or not seen:
        return False
    return (seen - ev) > timedelta(days=BACKFILL_LAG_DAYS)


def _salience(row: dict) -> float:
    """Significance × light recency, for ordering within and across topics."""
    base = _CLASS_WEIGHT.get(row.get("event_class") or "", 0.5)
    seen = _parse_ts(row.get("first_seen_at")) or datetime.now(timezone.utc)
    age_h = max((datetime.now(timezone.utc) - seen).total_seconds() / 3600.0, 0.0)
    recency = 0.5 ** (age_h / 36.0)          # ~half-weight per 36h
    verified = min(float(row.get("verified_count") or 0), 5) / 50.0
    return base * (0.6 + 0.4 * recency) + verified


def _shape(row: dict) -> dict:
    return {
        "text":            row.get("alpha_text", ""),
        "context":         row.get("context"),
        "event_class":     row.get("event_class"),
        "event_date":      (str(row.get("event_date"))[:10] if row.get("event_date") else None),
        "first_seen_at":   row.get("first_seen_at"),
        "source_domain":   row.get("source_domain"),
        "source_url":      row.get("source_url"),
        "verified_count":  row.get("verified_count") or 0,
    }


def get_delta_feed(user_id: str, anchor: str = "seen", db=None) -> dict:
    """
    Build the user's cross-topic delta feed.

    Args:
        user_id: the viewer.
        anchor:  "seen" (live window, last_seen_at) or "digest" (last_digest_at).

    Returns:
        {
          "all_quiet": bool,           # True = nothing new since the anchor
          "total": int,                # total new facts across topics
          "topic_count": int,          # subscribed topics
          "topics": [ { topic_id, topic_name, new_count, facts:[...] }, ... ],
        }
    """
    if db is None:
        from truebrief.ledger.database import get_supabase
        db = get_supabase()

    anchor_col = "last_digest_at" if anchor == "digest" else "last_seen_at"
    empty = {"all_quiet": True, "total": 0, "topic_count": 0, "topics": []}

    # 1. The user's subscriptions.
    subs = db.table("topic_subscriptions").select("topic_id").eq("user_id", user_id).execute()
    topic_ids = [s["topic_id"] for s in (subs.data or [])]
    if not topic_ids:
        return empty

    # 2. Topic names.
    topics = db.table("topics").select("id, raw_query").in_("id", topic_ids).execute()
    name_of = {t["id"]: t["raw_query"] for t in (topics.data or [])}

    # 3. Per-topic anchors (one query); missing rows → short look-back window.
    default_anchor = (datetime.now(timezone.utc) - timedelta(hours=DEFAULT_WINDOW_HOURS)).isoformat()
    anchors: dict[str, str] = {}
    try:
        st = (
            db.table("user_topic_state")
            .select("topic_id, " + anchor_col)
            .eq("user_id", user_id)
            .in_("topic_id", topic_ids)
            .execute()
        )
        for r in (st.data or []):
            anchors[r["topic_id"]] = r.get(anchor_col) or default_anchor
    except Exception:
        pass  # table missing (pre-019) → everyone gets the default window

    # 4. Per-topic delta query, gated + ranked.
    out_topics = []
    total = 0
    for tid in topic_ids:
        since = anchors.get(tid, default_anchor)
        try:
            res = (
                db.table("known_facts")
                .select(_FACT_COLS)
                .eq("topic_id", tid)
                .gt("first_seen_at", since)
                .order("first_seen_at", desc=True)
                .limit(PER_TOPIC_CAP * 3)
                .execute()
            )
        except Exception as exc:
            logger.debug("[DELTA] fact query failed for topic %s: %s", tid, exc)
            continue
        rows = [r for r in (res.data or []) if not _is_backfill(r)]
        if not rows:
            continue
        rows.sort(key=_salience, reverse=True)
        rows = rows[:PER_TOPIC_CAP]
        out_topics.append({
            "topic_id":   tid,
            "topic_name": name_of.get(tid, "Topic"),
            "new_count":  len(rows),
            "top_salience": _salience(rows[0]),
            "facts":      [_shape(r) for r in rows],
        })
        total += len(rows)

    # 5. Order topics by their hottest fact (most significant / recent first).
    out_topics.sort(key=lambda t: t["top_salience"], reverse=True)
    for t in out_topics:
        t.pop("top_salience", None)

    return {
        "all_quiet":   total == 0,
        "total":       total,
        "topic_count": len(topic_ids),
        "topics":      out_topics,
    }


def advance_seen(user_id: str, topic_ids: Optional[list[str]] = None, db=None) -> None:
    """Advance last_seen_at = now for the given topics (default: all subscribed).
    Called on view so the next look shows 'all caught up'. Never raises."""
    _advance(user_id, "last_seen_at", topic_ids, db)


def advance_digest(user_id: str, topic_ids: Optional[list[str]] = None, db=None) -> None:
    """Advance last_digest_at = now (after a digest is sent). Never raises."""
    _advance(user_id, "last_digest_at", topic_ids, db)


def _advance(user_id: str, col: str, topic_ids: Optional[list[str]], db) -> None:
    try:
        if db is None:
            from truebrief.ledger.database import get_supabase
            db = get_supabase()
        if topic_ids is None:
            subs = db.table("topic_subscriptions").select("topic_id").eq("user_id", user_id).execute()
            topic_ids = [s["topic_id"] for s in (subs.data or [])]
        if not topic_ids:
            return
        now = datetime.now(timezone.utc).isoformat()
        rows = [{"user_id": user_id, "topic_id": tid, col: now} for tid in topic_ids]
        db.table("user_topic_state").upsert(rows, on_conflict="user_id,topic_id").execute()
        logger.info("[DELTA] Advanced %s for %d topic(s), user %s.", col, len(rows), user_id[:8])
    except Exception as exc:
        logger.debug("[DELTA] _advance(%s) failed (non-fatal): %s", col, exc)
