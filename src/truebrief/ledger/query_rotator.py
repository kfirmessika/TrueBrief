"""
Query Rotator - ledger/query_rotator.py

Manages per-topic search query variants for dynamic keyword rotation.

The Problem:
  A fixed primary_query like "TSMC semiconductor" eventually saturates -
  all the sources know about it, so you keep getting the same articles.
  Rotating through semantically diverse alt_queries surfaces different
  sources and angles, increasing the chance of finding genuinely new facts.

The Solution:
  1. First scan: initialize variants from QueryBuilder's alt_queries.
  2. Before each scan: select the best-performing active variant (highest AYR).
     If tied, pick the least-recently-used one to ensure round-robin coverage.
  3. After each scan: update the selected variant's performance stats.
  4. If a variant has been used ROTATION_AFTER_SCANS times and has AYR below
     LOW_AYR_THRESHOLD, retire it and generate a fresh replacement via LLM.

AYR per variant:
  variant_ayr = alphas_yielded / scans_used
  (same formula as topic-level AYR, but scoped to one query string)

Design:
  - All errors are logged and silently swallowed. The pipeline must never
    fail because of query rotation.
  - The selected variant's text replaces query.primary_query in the pipeline.
  - The raw_query on the topic remains unchanged - rotation is an optimization
    layer, not a change to the user's original intent.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ── Configuration ─────────────────────────────────────────────────────────────

# Minimum uses before we consider retiring a variant
ROTATION_AFTER_SCANS = 5

# If AYR is below this threshold after ROTATION_AFTER_SCANS uses → retire
LOW_AYR_THRESHOLD = 0.15

# Maximum active variants per topic (prevents unbounded growth)
MAX_ACTIVE_VARIANTS = 5


# ── Public API ─────────────────────────────────────────────────────────────────

class QueryRotator:
    """
    Manages query variant lifecycle for a topic.

    Usage in PipelineRunner:
        rotator = QueryRotator()

        # Before scan - get the best query to use
        variant_id, query_text = rotator.select_variant(
            topic_id, raw_query, alt_queries
        )

        # After scan - record how many alphas it produced
        rotator.record_result(variant_id, alphas_produced=3)
    """

    def select_variant(
        self,
        topic_id: str,
        raw_query: str,
        alt_queries: list[str],
    ) -> tuple[Optional[str], str]:
        """
        Select the best active query variant for this scan.

        Initialises variants from [raw_query] + alt_queries on first call.
        Returns (variant_id, query_text). query_text replaces primary_query.

        On any error, returns (None, raw_query) - safe fallback.
        """
        try:
            from truebrief.ledger.database import get_supabase
            db = get_supabase()

            # 1. Ensure variants exist (initialize on first run)
            self._ensure_initialized(db, topic_id, raw_query, alt_queries)

            # 2. Fetch all active variants ordered by: AYR desc, last_used_at asc
            #    (best yield first, break ties by least recently used)
            res = (
                db.table("topic_query_variants")
                .select("id, query_text, scans_used, alphas_yielded, ayr, last_used_at")
                .eq("topic_id", topic_id)
                .eq("is_active", True)
                .order("ayr", desc=True)
                .limit(MAX_ACTIVE_VARIANTS)
                .execute()
            )

            variants = res.data or []
            if not variants:
                logger.warning(f"[ROTATOR] No active variants for topic {topic_id}. Using raw_query.")
                return None, raw_query

            # 3. Among variants with the same AYR (or all 0 on first run),
            #    prefer the least recently used to ensure round-robin
            top_ayr = variants[0]["ayr"]
            tied = [v for v in variants if v["ayr"] == top_ayr]

            # Sort tied variants by last_used_at ascending (None = never used → pick first)
            tied.sort(key=lambda v: v["last_used_at"] or "")
            selected = tied[0]

            logger.info(
                f"[ROTATOR] Selected variant for topic {topic_id}: "
                f"'{selected['query_text'][:60]}' "
                f"(AYR={selected['ayr']:.2%}, uses={selected['scans_used']})"
            )
            return selected["id"], selected["query_text"]

        except Exception as exc:
            logger.error(f"[ROTATOR] select_variant failed: {exc}")
            return None, raw_query

    def record_result(
        self,
        variant_id: str,
        alphas_produced: int,
        topic_id: Optional[str] = None,
        raw_query: Optional[str] = None,
    ) -> None:
        """
        Update variant performance stats after a scan.
        Also triggers rotation check if the variant is underperforming.
        """
        if not variant_id:
            return  # Rotation was disabled for this run (fallback mode)

        try:
            from truebrief.ledger.database import get_supabase
            db = get_supabase()

            # Fetch current stats
            res = (
                db.table("topic_query_variants")
                .select("scans_used, alphas_yielded, generation")
                .eq("id", variant_id)
                .single()
                .execute()
            )
            if not res.data:
                return

            current = res.data
            new_scans = current["scans_used"] + 1
            new_alphas = current["alphas_yielded"] + alphas_produced
            new_ayr = round(new_alphas / new_scans, 4) if new_scans > 0 else 0.0

            db.table("topic_query_variants").update({
                "scans_used":     new_scans,
                "alphas_yielded": new_alphas,
                "ayr":            new_ayr,
                "last_used_at":   datetime.now(timezone.utc).isoformat(),
            }).eq("id", variant_id).execute()

            logger.info(
                f"[ROTATOR] Variant {variant_id}: "
                f"scans={new_scans}, alphas={new_alphas}, AYR={new_ayr:.2%}"
            )

            # Check if this variant should be rotated out
            if (
                new_scans >= ROTATION_AFTER_SCANS
                and new_ayr < LOW_AYR_THRESHOLD
                and topic_id
                and raw_query
            ):
                self._rotate_out(
                    db, variant_id, topic_id, raw_query,
                    generation=current.get("generation", 0)
                )

        except Exception as exc:
            logger.error(f"[ROTATOR] record_result failed: {exc}")

    # ── Private Helpers ────────────────────────────────────────────────────────

    def _ensure_initialized(
        self,
        db,
        topic_id: str,
        raw_query: str,
        alt_queries: list[str],
    ) -> None:
        """Create initial variants if none exist yet for this topic."""
        count_res = (
            db.table("topic_query_variants")
            .select("id", count="exact")
            .eq("topic_id", topic_id)
            .execute()
        )
        count = count_res.count if hasattr(count_res, "count") else len(count_res.data or [])
        if count > 0:
            return  # Already initialized

        # Seed with raw_query first, then alt_queries
        all_queries = [raw_query] + [q for q in alt_queries if q != raw_query]
        rows = [
            {
                "topic_id":   topic_id,
                "query_text": q,
                "generation": 0,
            }
            for q in all_queries[:MAX_ACTIVE_VARIANTS]
        ]
        try:
            db.table("topic_query_variants").insert(rows).execute()
            logger.info(
                f"[ROTATOR] Initialized {len(rows)} variant(s) for topic {topic_id}"
            )
        except Exception as exc:
            logger.error(f"[ROTATOR] Failed to initialize variants: {exc}")

    def _rotate_out(
        self,
        db,
        variant_id: str,
        topic_id: str,
        raw_query: str,
        generation: int,
    ) -> None:
        """
        Retire an underperforming variant and generate a replacement via LLM.
        Retirement is skipped if the raw_query itself is the underperformer
        (we always keep at least one variant).
        """
        # Fetch the variant's query text to check if it's the raw_query
        v_res = (
            db.table("topic_query_variants")
            .select("query_text")
            .eq("id", variant_id)
            .single()
            .execute()
        )
        if not v_res.data:
            return

        query_text = v_res.data["query_text"]

        # Never retire the original raw_query - it's the user's intent anchor
        if query_text.strip().lower() == raw_query.strip().lower():
            logger.info(f"[ROTATOR] Skipping retire - this is the raw_query anchor.")
            return

        # Check if retiring this would leave zero active variants
        active_res = (
            db.table("topic_query_variants")
            .select("id", count="exact")
            .eq("topic_id", topic_id)
            .eq("is_active", True)
            .execute()
        )
        active_count = active_res.count if hasattr(active_res, "count") else len(active_res.data or [])
        if active_count <= 1:
            logger.info(f"[ROTATOR] Skipping retire - only 1 active variant left.")
            return

        # Retire the bad variant
        db.table("topic_query_variants").update({"is_active": False}).eq("id", variant_id).execute()
        logger.info(f"[ROTATOR] Retired low-AYR variant: '{query_text[:60]}'")

        # Generate a replacement
        new_query = self._generate_replacement(raw_query, query_text)
        if new_query:
            try:
                db.table("topic_query_variants").insert({
                    "topic_id":   topic_id,
                    "query_text": new_query,
                    "generation": generation + 1,
                }).execute()
                logger.info(f"[ROTATOR] New variant added (gen {generation+1}): '{new_query[:60]}'")
            except Exception as exc:
                logger.error(f"[ROTATOR] Failed to insert replacement: {exc}")

    def _generate_replacement(self, raw_query: str, retiring_query: str) -> Optional[str]:
        """Ask the LLM to generate a fresh search query for this topic."""
        try:
            from truebrief.llm.client import LLMClient
            import json

            llm = LLMClient()
            prompt = f"""You are a news search strategist. 
A search query for the topic '{raw_query}' has been underperforming: '{retiring_query}'.

Generate ONE alternative news search query that:
- Targets the same topic from a different angle (e.g. financial impact, geopolitical angle, technical developments, market reaction)
- Is specific enough to find genuine news, not just opinion pieces
- Is different enough from the retiring query to surface new sources

Return ONLY a JSON object: {{"query": "your search query here"}}"""

            response = llm.call(
                step_name="query_rotator",
                prompt=prompt,
                json_mode=True,
                system_prompt="You are a professional news intelligence researcher.",
            )
            data = json.loads(response)
            return data.get("query", "").strip() or None
        except Exception as exc:
            logger.error(f"[ROTATOR] LLM replacement generation failed: {exc}")
            return None
