"""
History Doc — ledger/history_doc.py  (architecture §7.2, build-seq step 9)

The V3 "story so far": the topic's full timeline, assembled with ZERO LLM by placing
the already-clean fact-sentences in chronological order. This is the context layer that
replaces the paused story-graph (§7) and powers the in-app History view.

No-LLM-first by design: we only place stored facts on a time axis. If it ever reads
choppy, a single optional glue/summary LLM pass can be added later — not now.

doc shape:
  {
    "built_at":   "2026-06-22T...",
    "fact_count": 42,
    "timeline": [
      { "date": "2026-06-21",
        "facts": [ {text, context, event_class, source_domain, source_url,
                    verified_count, contradiction_note, event_date, first_seen_at}, ... ] },
      ...   # date groups, newest first; facts within a day ordered by significance
    ]
  }

Requires migration 018 (history_docs). Degrades gracefully: build_history_doc reads
known_facts directly, so the API can always live-build even if the table is empty.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Max facts pulled into one timeline (keeps a long-running topic's history bounded).
_MAX_FACTS = 600

# Significance ordering within a single day — mirrors the runner's IC2 class weights
# so the history view ranks facts the same way the brief does.
_CLASS_WEIGHT = {
    "state_change": 1.0,
    "escalation":   0.8,
    "development":  0.6,
    "incremental":  0.4,
    "routine":      0.2,
    "tally":        0.1,
}


def _fact_date(row: dict) -> str:
    """The date a fact belongs under: the development date (event_date) when known,
    else the day we first saw it. Returns 'YYYY-MM-DD' (or '' if neither parses)."""
    for key in ("event_date", "first_seen_at"):
        val = row.get(key)
        if not val:
            continue
        try:
            # event_date may be 'YYYY-MM-DD'; first_seen_at a full ISO timestamp.
            return str(val)[:10]
        except Exception:
            continue
    return ""


def _sort_key(row: dict) -> float:
    """Within-day ordering: higher significance first, then more-corroborated."""
    base = _CLASS_WEIGHT.get(row.get("event_class") or "", 0.5)
    verified = float(row.get("verified_count") or 0)
    return base * 10 + min(verified, 9)


def build_history_doc(topic_id: str, db=None) -> dict:
    """
    Assemble the topic's timeline from known_facts. Pure data, no LLM.

    Returns the structured doc (see module docstring). Empty timeline if no facts.
    """
    if db is None:
        from truebrief.ledger.database import get_supabase
        db = get_supabase()

    # Pull the IC4 columns too, but fall back if migration 015 isn't applied.
    base_cols = (
        "alpha_text, context, event_class, event_date, first_seen_at, "
        "source_domain, source_url, verified_count"
    )
    try:
        res = (
            db.table("known_facts")
            .select(base_cols + ", contradiction_note")
            .eq("topic_id", topic_id)
            .order("event_date", desc=True)
            .limit(_MAX_FACTS)
            .execute()
        )
    except Exception:
        res = (
            db.table("known_facts")
            .select(base_cols)
            .eq("topic_id", topic_id)
            .order("event_date", desc=True)
            .limit(_MAX_FACTS)
            .execute()
        )
    rows = res.data or []

    # Group by date, newest day first; order facts within a day by significance.
    by_date: dict[str, list[dict]] = {}
    for row in rows:
        day = _fact_date(row)
        if not day:
            continue
        by_date.setdefault(day, []).append({
            "text":               row.get("alpha_text", ""),
            "context":            row.get("context"),
            "event_class":        row.get("event_class"),
            "event_date":         (str(row.get("event_date"))[:10] if row.get("event_date") else None),
            "first_seen_at":      row.get("first_seen_at"),
            "source_domain":      row.get("source_domain"),
            "source_url":         row.get("source_url"),
            "verified_count":     row.get("verified_count") or 0,
            "contradiction_note": row.get("contradiction_note"),
        })

    timeline = []
    for day in sorted(by_date.keys(), reverse=True):
        facts = sorted(by_date[day], key=_sort_key, reverse=True)
        timeline.append({"date": day, "facts": facts})

    return {
        "built_at":   datetime.now(timezone.utc).isoformat(),
        "fact_count": sum(len(g["facts"]) for g in timeline),
        "timeline":   timeline,
    }


def store_history_doc(topic_id: str, doc: Optional[dict] = None, db=None) -> None:
    """Rebuild (if doc not supplied) and upsert the topic's history doc. Never raises."""
    try:
        if db is None:
            from truebrief.ledger.database import get_supabase
            db = get_supabase()
        if doc is None:
            doc = build_history_doc(topic_id, db=db)
        db.table("history_docs").upsert({
            "topic_id":      topic_id,
            "doc":           doc,
            "fact_count":    doc.get("fact_count", 0),
            "last_built_at": doc.get("built_at"),
        }, on_conflict="topic_id").execute()
        logger.info("[HISTORY] Rebuilt history doc for %s (%d facts).", topic_id[:8], doc.get("fact_count", 0))
    except Exception as exc:
        logger.debug("[HISTORY] store_history_doc failed (non-fatal): %s", exc)


def get_history_doc(topic_id: str, db=None) -> dict:
    """
    Read the stored history doc; fall back to a live build if the table is empty
    or migration 018 isn't applied. Always returns a valid doc shape.
    """
    if db is None:
        from truebrief.ledger.database import get_supabase
        db = get_supabase()
    try:
        res = (
            db.table("history_docs")
            .select("doc")
            .eq("topic_id", topic_id)
            .limit(1)
            .execute()
        )
        if res.data and res.data[0].get("doc", {}).get("timeline"):
            return res.data[0]["doc"]
    except Exception:
        pass  # table missing or other issue → live build
    return build_history_doc(topic_id, db=db)
