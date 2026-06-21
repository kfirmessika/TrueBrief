"""
Source Stats - ledger/source_stats.py

Tracks per-(topic × tool) AYR (alpha yield rate) so the runner can UCB1-select
which search tools to call each scan, balancing quality against API cost.

Matrix shape: topic_id × tool_name → {scans, alphas_new, ayr, ...}

Cold-start rule: all tools fire for the first MIN_EXPLORATION_SCANS runs per topic.
After that: UCB1 score = ayr + C * sqrt(ln(total_scans) / tool_scans).
Free tools (RSS, Google News) always fire regardless of UCB1.

Requires migration 017 (source_stats table).
Degrades gracefully to "fire all tools" if table is missing.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)

# Always fire all tools for the first N scans per topic (cold-start exploration).
# Keeps the cost of learning to 3 real scans per topic — no wasted synthetic calls.
MIN_EXPLORATION_SCANS = 3

# UCB1 exploration constant (√2 = classic; lower = more exploitative)
UCB1_C = math.sqrt(2)

# Tools that are free / nearly free: always fire, never skip via UCB1.
# We never want to miss RSS or Google News to save budget.
FREE_TOOLS = {"rss", "google_news"}

# EMA smoothing factor for AYR update (0.3 = moderate responsiveness to recent scans)
EMA_ALPHA = 0.3


# ---------------------------------------------------------------------------
# Write: record scan outcome per tool
# ---------------------------------------------------------------------------

def update_tool_stats(
    topic_id: str,
    tool_results: dict[str, dict],
) -> None:
    """
    Upsert per-tool scan stats after a pipeline run.

    Args:
        topic_id: The topic UUID.
        tool_results: {tool_name: {offered, selected, new_alphas}}
            offered     = articles returned by this tool and passed to dedup
            selected    = articles from this tool that survived MMR
            new_alphas  = NEW/UPDATE decisions traced back to this tool's articles
    """
    if not topic_id or not tool_results:
        return
    try:
        from truebrief.ledger.database import get_supabase
        db = get_supabase()

        # Load current stats for all tools involved (one query, not N)
        res = (
            db.table("source_stats")
            .select("tool_name, scans, articles_offered, articles_selected, alphas_new, ayr")
            .eq("topic_id", topic_id)
            .in_("tool_name", list(tool_results.keys()))
            .execute()
        )
        current: dict[str, dict] = {row["tool_name"]: row for row in (res.data or [])}

        rows = []
        for tool, result in tool_results.items():
            cur = current.get(tool, {})
            new_scans     = cur.get("scans", 0) + 1
            new_offered   = cur.get("articles_offered", 0) + result.get("offered", 0)
            new_selected  = cur.get("articles_selected", 0) + result.get("selected", 0)
            new_alphas    = cur.get("alphas_new", 0) + result.get("new_alphas", 0)

            # AYR = EMA of per-scan new_alphas (not cumulative / scans — avoids dilution)
            scan_ayr  = float(result.get("new_alphas", 0))
            old_ayr   = cur.get("ayr", 0.0)
            new_ayr   = round(EMA_ALPHA * scan_ayr + (1 - EMA_ALPHA) * old_ayr, 4)

            rows.append({
                "topic_id":          topic_id,
                "tool_name":         tool,
                "scans":             new_scans,
                "articles_offered":  new_offered,
                "articles_selected": new_selected,
                "alphas_new":        new_alphas,
                "ayr":               new_ayr,
            })

        if rows:
            db.table("source_stats").upsert(
                rows, on_conflict="topic_id,tool_name"
            ).execute()
            logger.info(
                "[SOURCE_STATS] Updated %d tool(s) for topic %s: %s",
                len(rows),
                topic_id[:8],
                {r["tool_name"]: f"ayr={r['ayr']:.2f}" for r in rows},
            )
    except Exception as exc:
        logger.debug("[SOURCE_STATS] update_tool_stats failed (non-fatal): %s", exc)


# ---------------------------------------------------------------------------
# Read: UCB1 tool selection
# ---------------------------------------------------------------------------

def get_tool_fire_set(
    topic_id: Optional[str],
    available_tools: list[str],
) -> set[str]:
    """
    Return which tools to fire this scan based on UCB1 per (topic, tool).

    Rules:
    - No topic_id → fire everything (anonymous / test run).
    - Cold-start (any tool has < MIN_EXPLORATION_SCANS) → fire everything.
    - After cold-start: UCB1 score decides; free tools always fire.
    - Any DB error → fire everything (safe fallback).

    The caller filters self.sources to only the returned set before collection.
    """
    if not topic_id:
        return set(available_tools)

    try:
        from truebrief.ledger.database import get_supabase
        db = get_supabase()

        res = (
            db.table("source_stats")
            .select("tool_name, scans, ayr")
            .eq("topic_id", topic_id)
            .execute()
        )
        stats: dict[str, dict] = {row["tool_name"]: row for row in (res.data or [])}

        # Cold-start: if any available PAID tool has < MIN_EXPLORATION_SCANS, explore all.
        paid_tools = [t for t in available_tools if t not in FREE_TOOLS]
        for tool in paid_tools:
            if stats.get(tool, {}).get("scans", 0) < MIN_EXPLORATION_SCANS:
                logger.info(
                    "[SOURCE_STATS] Cold-start: tool '%s' has < %d scans — firing all tools.",
                    tool, MIN_EXPLORATION_SCANS,
                )
                return set(available_tools)

        # Post cold-start: UCB1 selection.
        total_scans = max((s["scans"] for s in stats.values()), default=1)
        fire: set[str] = set(FREE_TOOLS) & set(available_tools)  # free tools always on

        for tool in paid_tools:
            s = stats.get(tool, {})
            n = s.get("scans", 0)
            ayr = s.get("ayr", 0.0)
            score = ayr + UCB1_C * math.sqrt(math.log(max(total_scans, 1)) / max(n, 1))
            # Fire if score > 0 (exploiting) or n == 0 (unexplored — always try once)
            if score > 0 or n == 0:
                fire.add(tool)
            else:
                logger.info(
                    "[SOURCE_STATS] UCB1 skipping '%s' this scan (score=%.3f, ayr=%.3f, n=%d).",
                    tool, score, ayr, n,
                )

        logger.info("[SOURCE_STATS] Tools selected for this scan: %s", sorted(fire))
        return fire

    except Exception as exc:
        logger.debug("[SOURCE_STATS] get_tool_fire_set failed (non-fatal): %s", exc)
        return set(available_tools)  # safe fallback: fire all
