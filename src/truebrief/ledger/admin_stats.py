"""
Admin Stats — ledger/admin_stats.py

Thin wrapper around the `llm_cost_for_topics` RPC (migration 031) for the admin
per-user data drill-down (GET /admin/users/{user_id}).

Uses an RPC rather than a raw `llm_call_log` select for the same reason
`/admin/metrics` uses `llm_cost_by_stage` (see api/routes.py:1700-1706):
PostgREST silently caps an unfiltered/unlimited select at 1000 rows, so an
admin/founder with a heavily-used topic could see a silently undercounted total
from a hand-summed Python loop. The RPC sums server-side instead.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_ZERO_COST = {"total_cost_usd": 0.0, "total_tokens": 0, "run_count": 0}


def get_cost_for_topics(topic_ids: list[str]) -> dict:
    """Return {total_cost_usd, total_tokens, run_count} summed across the given topics'
    pipeline runs. Empty topic_ids short-circuits to zeros without an RPC round-trip.

    Never raises — falls back to zeros (with a warning log) if the RPC is unreachable
    or pre-migration-031, matching the fail-soft pattern the rest of the admin panel uses.
    """
    if not topic_ids:
        return dict(_ZERO_COST)

    try:
        from truebrief.ledger.database import get_supabase

        db = get_supabase()
        res = db.rpc("llm_cost_for_topics", {"topic_ids": topic_ids}).execute()
        rows = res.data or []
        if not rows:
            return dict(_ZERO_COST)
        row = rows[0]
        return {
            "total_cost_usd": float(row.get("total_cost_usd") or 0.0),
            "total_tokens": int(row.get("total_tokens") or 0),
            "run_count": int(row.get("run_count") or 0),
        }
    except Exception as exc:
        logger.warning("get_cost_for_topics failed (non-fatal): %s", exc)
        return dict(_ZERO_COST)
