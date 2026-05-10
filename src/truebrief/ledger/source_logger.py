"""
Source Quality Logger - ledger/source_logger.py

Logs every Arbiter decision to `source_quality_log` in Supabase.
This is the raw data layer for AYR (Alpha Yield Rate) - Phase 2.8.

Responsibilities:
  - Extract domain from source_url (e.g. "https://reuters.com/..." → "reuters.com")
  - Batch-insert all decisions from a single pipeline run in one DB call
  - Never crash the pipeline - all errors are logged and swallowed

Used by Task 2.10 (AYR calculation) to compute per-source yield rates:
  AYR = (NEW + UPDATE decisions) / total decisions for that domain

Design:
  - Fire-and-forget: the pipeline calls log_batch() and doesn't wait for success
  - Batch insert (one call per pipeline run, not per alpha) for efficiency
  - Defensive: fails silently so quality logging never blocks brief delivery
"""

from __future__ import annotations

import logging
from typing import List
from urllib.parse import urlparse

from truebrief.models.alpha import AlphaDecision, DecisionType

logger = logging.getLogger(__name__)


def extract_domain(url: str) -> str:
    """
    Extract the bare domain from a URL, stripping common non-content subdomains.

    Examples:
        "https://www.reuters.com/technology/article"    → "reuters.com"
        "https://feeds.bloomberg.com/markets/news"      → "bloomberg.com"
        "https://rss.nytimes.com/..."                   → "nytimes.com"
        "https://m.techcrunch.com/..."                  → "techcrunch.com"
        "bad-url"                                       → "bad-url"
    """
    # Subdomains that are infrastructure/delivery, not editorial identity
    _STRIP_PREFIXES = ("www.", "feeds.", "feed.", "rss.", "news.", "m.", "amp.")

    try:
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path  # path fallback for malformed URLs
        host = host.lower()
        for prefix in _STRIP_PREFIXES:
            if host.startswith(prefix):
                host = host[len(prefix):]
                break  # only strip one level
        return host or "unknown"
    except Exception:
        return "unknown"



class SourceQualityLogger:
    """
    Logs Arbiter decisions to `source_quality_log` for AYR tracking.

    Usage (in pipeline runner):
        logger = SourceQualityLogger()
        logger.log_batch(decisions, topic_id)   # one call per pipeline run
    """

    def log_batch(
        self,
        decisions: List[AlphaDecision],
        topic_id: str | None,
    ) -> int:
        """
        Insert all decisions from one pipeline run as a batch into Supabase.

        Args:
            decisions: The full list of AlphaDecision objects from the Arbiter.
            topic_id:  The topic UUID (may be None in test runs).

        Returns:
            Number of rows successfully inserted (0 on failure).
        """
        if not decisions:
            return 0

        rows = []
        for d in decisions:
            try:
                rows.append({
                    "topic_id":        topic_id,
                    "alpha_id":        d.alpha.id,
                    "source_url":      d.alpha.source_url,
                    "source_name":     d.alpha.source_name,
                    "source_domain":   extract_domain(d.alpha.source_url),
                    "decision":        d.decision.value,         # "NEW" | "UPDATE" | "DUPLICATE"
                    "similarity_score": d.similarity_score,
                })
            except Exception as row_err:
                logger.warning(f"SourceQualityLogger: skipping malformed decision: {row_err}")

        if not rows:
            return 0

        try:
            from truebrief.ledger.database import get_supabase
            db = get_supabase()
            res = db.table("source_quality_log").insert(rows).execute()
            inserted = len(res.data) if res.data else 0
            logger.info(
                f"[SOURCE LOG] Logged {inserted}/{len(rows)} decisions "
                f"for topic={topic_id}"
            )
            return inserted
        except Exception as exc:
            # Non-fatal - quality logging must never crash the pipeline
            logger.error(f"[SOURCE LOG] Batch insert failed: {exc}")
            return 0

    def get_domain_stats(
        self,
        topic_id: str,
        days: int = 30,
    ) -> list[dict]:
        """
        Return per-domain AYR stats for a topic over the last N days.

        Returns list of dicts:
            [{"source_domain": "reuters.com", "total": 42, "alphas": 18, "ayr": 0.43}, ...]

        Used by Task 2.10 (AYR calculation engine).
        """
        try:
            from truebrief.ledger.database import get_supabase
            from datetime import datetime, timedelta, timezone

            db = get_supabase()
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

            res = (
                db.table("source_quality_log")
                .select("source_domain, decision")
                .eq("topic_id", topic_id)
                .gte("created_at", cutoff)
                .execute()
            )

            rows = res.data or []

            # Aggregate in Python (simpler than Supabase RPC for now)
            stats: dict[str, dict] = {}
            for row in rows:
                domain = row["source_domain"]
                if domain not in stats:
                    stats[domain] = {"source_domain": domain, "total": 0, "alphas": 0}
                stats[domain]["total"] += 1
                if row["decision"] in ("NEW", "UPDATE"):
                    stats[domain]["alphas"] += 1

            result = []
            for s in stats.values():
                s["ayr"] = round(s["alphas"] / s["total"], 3) if s["total"] > 0 else 0.0
                result.append(s)

            # Sort by AYR descending
            result.sort(key=lambda x: x["ayr"], reverse=True)
            return result

        except Exception as exc:
            logger.error(f"[SOURCE LOG] get_domain_stats failed: {exc}")
            return []
