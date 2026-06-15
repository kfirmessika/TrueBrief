"""
Query Rotator - ledger/query_rotator.py

Manages per-topic search query variants using a multi-armed bandit (UCB1).

Lifecycle
---------
1. Topic creation  → QueryBuilder makes ONE LLM call → variants seeded in DB +
                     topic.search_strategy cached.
2. Every subsequent scan → select_variant() picks the best variant via UCB1.
   Zero LLM calls in the common path.
3. All variants disappoint → ONE LLM call to regenerate 3 fresh variants.
   This should be rare (weeks/months between calls for a healthy topic).

UCB1 formula
------------
  score(v) = avg_ayr + C × √(ln N / n)
  where:
    avg_ayr = alphas_yielded / scans_used  (arm mean reward)
    N       = total scans across all variants  (total pulls)
    n       = scans_used for this variant      (pulls on this arm)
    C       = √2 ≈ 1.41  (classic UCB1 exploration constant)

  n == 0  → score = ∞  (always try unexplored arms first)
  N == 0  → pick first variant (all tied at 0)

Disappointment → regenerate
---------------------------
  Triggers when ALL active variants satisfy both:
    • scans_used ≥ MIN_TRIALS_BEFORE_DISAPPOINT
    • ayr        < DISAPPOINT_AYR_THRESHOLD
  → ONE LLM call generates MAX_REGEN_VARIANTS fresh queries.
  → Worst performers retired; best kept for continuity.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ── Configuration ──────────────────────────────────────────────────────────────

UCB1_C = math.sqrt(2)               # standard exploration constant

# Minimum uses per variant before it can be flagged as disappointing
MIN_TRIALS_BEFORE_DISAPPOINT = 3

# AYR (alphas / scan) below which a variant is considered disappointing
DISAPPOINT_AYR_THRESHOLD = 0.05     # < 1 alpha per 20 scans = basically useless

# How many fresh variants to generate in one regeneration call
MAX_REGEN_VARIANTS = 3

# Hard cap on active variants (prevents unbounded growth)
MAX_ACTIVE_VARIANTS = 5


# ── Public API ─────────────────────────────────────────────────────────────────

class QueryRotator:
    """
    Multi-armed bandit over query variants for a topic.

    Designed to be called from PipelineRunner:

        rotator = QueryRotator()

        # Before each scan — UCB1 selection (no LLM in common path)
        variant_id, query_text = rotator.select_variant(
            topic_id, raw_query, alt_queries   # alt_queries only needed on first call
        )

        # After each scan — record alphas produced
        rotator.record_result(variant_id, alphas_produced)
    """

    def has_variants(self, topic_id: str) -> bool:
        """True if this topic has at least one active variant already seeded."""
        try:
            from truebrief.ledger.database import get_supabase
            db = get_supabase()
            res = (
                db.table("topic_query_variants")
                .select("id")
                .eq("topic_id", topic_id)
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
            return bool(res.data)
        except Exception as exc:
            logger.error(f"[ROTATOR] has_variants failed: {exc}")
            return False

    def select_variant(
        self,
        topic_id: str,
        raw_query: str,
        alt_queries: Optional[list[str]] = None,
    ) -> tuple[Optional[str], str]:
        """
        Return (variant_id, query_text) for this scan.

        On first call (no variants in DB yet): seeds from raw_query + alt_queries.
        On subsequent calls: alt_queries is ignored; UCB1 drives selection.

        Includes a disappointment check — may trigger ONE LLM call if all
        variants have been thoroughly tried and are all underperforming.

        Falls back to (None, raw_query) on any error.
        """
        try:
            from truebrief.ledger.database import get_supabase
            db = get_supabase()

            # 1. Seed on first call
            self._ensure_initialized(db, topic_id, raw_query, alt_queries or [])

            # 2. Load active variants
            res = (
                db.table("topic_query_variants")
                .select("id, query_text, scans_used, alphas_yielded, ayr, last_used_at")
                .eq("topic_id", topic_id)
                .eq("is_active", True)
                .limit(MAX_ACTIVE_VARIANTS)
                .execute()
            )
            variants = res.data or []
            if not variants:
                logger.warning(f"[ROTATOR] No active variants for {topic_id}. Falling back.")
                return None, raw_query

            # 3. Check for topic-level disappointment → maybe regenerate (rare LLM call)
            if self._all_disappointing(variants):
                variants = self._regenerate(db, topic_id, raw_query, variants)

            # 4. UCB1 selection
            selected = self._ucb1_select(variants)
            logger.info(
                f"[ROTATOR] UCB1 selected '{selected['query_text'][:60]}' "
                f"(AYR={selected['ayr']:.3f}, n={selected['scans_used']})"
            )
            return selected["id"], selected["query_text"]

        except Exception as exc:
            logger.error(f"[ROTATOR] select_variant failed: {exc}")
            return None, raw_query

    def record_result(
        self,
        variant_id: str,
        alphas_produced: int,
        topic_id: Optional[str] = None,   # kept for API compat, unused
        raw_query: Optional[str] = None,  # kept for API compat, unused
    ) -> None:
        """
        Update variant performance stats after a scan.
        Disappointment check now happens at the START of the next scan
        (inside select_variant), so no per-variant rotation is triggered here.
        """
        if not variant_id:
            return

        try:
            from truebrief.ledger.database import get_supabase
            db = get_supabase()

            res = (
                db.table("topic_query_variants")
                .select("scans_used, alphas_yielded")
                .eq("id", variant_id)
                .single()
                .execute()
            )
            if not res.data:
                return

            cur = res.data
            new_scans  = cur["scans_used"]  + 1
            new_alphas = cur["alphas_yielded"] + alphas_produced
            new_ayr    = round(new_alphas / new_scans, 4)

            db.table("topic_query_variants").update({
                "scans_used":     new_scans,
                "alphas_yielded": new_alphas,
                "ayr":            new_ayr,
                "last_used_at":   datetime.now(timezone.utc).isoformat(),
            }).eq("id", variant_id).execute()

            logger.info(
                f"[ROTATOR] {variant_id[:8]}: scans={new_scans} "
                f"alphas={new_alphas} AYR={new_ayr:.3f}"
            )

        except Exception as exc:
            logger.error(f"[ROTATOR] record_result failed: {exc}")

    # ── Private: UCB1 ─────────────────────────────────────────────────────────

    def _ucb1_score(self, variant: dict, total_n: int) -> float:
        n = variant["scans_used"]
        if n == 0:
            return float("inf")
        avg = variant["ayr"]
        return avg + UCB1_C * math.sqrt(math.log(max(total_n, 1)) / n)

    def _ucb1_select(self, variants: list[dict]) -> dict:
        total_n = sum(v["scans_used"] for v in variants)
        return max(variants, key=lambda v: self._ucb1_score(v, total_n))

    # ── Private: Disappointment + regeneration ─────────────────────────────────

    def _all_disappointing(self, variants: list[dict]) -> bool:
        """True when every variant has been tried ≥ MIN_TRIALS and AYR < threshold."""
        return (
            bool(variants)
            and all(v["scans_used"] >= MIN_TRIALS_BEFORE_DISAPPOINT for v in variants)
            and all(v["ayr"] < DISAPPOINT_AYR_THRESHOLD for v in variants)
        )

    def _regenerate(
        self,
        db,
        topic_id: str,
        raw_query: str,
        current_variants: list[dict],
    ) -> list[dict]:
        """
        ONE LLM call to get MAX_REGEN_VARIANTS fresh query strings.
        Retires all but the best current variant, inserts fresh ones.
        Returns the updated variant list from DB (for UCB1 selection).
        """
        logger.info(
            f"[ROTATOR] All variants disappointing for {topic_id} "
            f"— regenerating via ONE LLM call"
        )

        existing_texts = [v["query_text"] for v in current_variants]
        new_queries = self._llm_generate_variants(raw_query, existing_texts)
        if not new_queries:
            logger.warning("[ROTATOR] LLM regeneration returned nothing — keeping current variants")
            return current_variants

        # Keep the single best-performing variant; retire the rest
        best = max(current_variants, key=lambda v: v["ayr"])
        for v in current_variants:
            if v["id"] != best["id"]:
                try:
                    db.table("topic_query_variants").update(
                        {"is_active": False}
                    ).eq("id", v["id"]).execute()
                except Exception:
                    pass

        max_gen = max((v.get("generation", 0) for v in current_variants), default=0) + 1
        rows = [
            {"topic_id": topic_id, "query_text": q, "generation": max_gen}
            for q in new_queries[:MAX_REGEN_VARIANTS]
        ]
        try:
            db.table("topic_query_variants").insert(rows).execute()
            logger.info(f"[ROTATOR] Inserted {len(rows)} fresh variants (gen {max_gen})")
        except Exception as exc:
            logger.error(f"[ROTATOR] Failed to insert fresh variants: {exc}")
            return current_variants

        # Reload from DB so UCB1 sees the updated picture
        res = (
            db.table("topic_query_variants")
            .select("id, query_text, scans_used, alphas_yielded, ayr, last_used_at")
            .eq("topic_id", topic_id)
            .eq("is_active", True)
            .limit(MAX_ACTIVE_VARIANTS)
            .execute()
        )
        return res.data or current_variants

    def _llm_generate_variants(
        self, raw_query: str, existing: list[str]
    ) -> list[str]:
        """
        ONE LLM call → list of MAX_REGEN_VARIANTS fresh search query strings.
        """
        try:
            from truebrief.llm.client import LLMClient
            llm = LLMClient()
            prompt = f"""You are a news search strategist.

Topic: '{raw_query}'

The following search queries have been exhausted (finding no new facts):
{json.dumps(existing, indent=2)}

Generate {MAX_REGEN_VARIANTS} DIFFERENT search queries that approach this topic
from fresh angles (e.g. financial impact, geopolitical, technical, personnel, regional).
Each query must be meaningfully different from the exhausted ones above.

Return ONLY valid JSON: {{"queries": ["query1", "query2", "query3"]}}"""

            response = llm.call(
                step_name="query_rotator",
                prompt=prompt,
                json_mode=True,
                system_prompt="You are a professional news intelligence researcher.",
            )
            data = json.loads(response)
            return [q.strip() for q in data.get("queries", []) if q.strip()]
        except Exception as exc:
            logger.error(f"[ROTATOR] LLM generation failed: {exc}")
            return []

    # ── Private: Initialization ────────────────────────────────────────────────

    def _ensure_initialized(
        self,
        db,
        topic_id: str,
        raw_query: str,
        alt_queries: list[str],
    ) -> None:
        """Seed variants on the very first call for a topic. No-op on subsequent calls."""
        res = (
            db.table("topic_query_variants")
            .select("id")
            .eq("topic_id", topic_id)
            .limit(1)
            .execute()
        )
        if res.data:
            return  # already seeded

        all_queries = [raw_query] + [q for q in alt_queries if q != raw_query]
        rows = [
            {"topic_id": topic_id, "query_text": q, "generation": 0}
            for q in all_queries[:MAX_ACTIVE_VARIANTS]
        ]
        try:
            db.table("topic_query_variants").insert(rows).execute()
            logger.info(
                f"[ROTATOR] Seeded {len(rows)} initial variant(s) for topic {topic_id}"
            )
        except Exception as exc:
            logger.error(f"[ROTATOR] Failed to seed variants: {exc}")
