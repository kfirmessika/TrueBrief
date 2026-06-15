"""
Arbiter - arbiter/arbiter.py

Pillar 4: Judge.

Determines whether each incoming Alpha is:
  NEW      - Not seen before. Store and include in brief.
  UPDATE   - New information that extends a known fact. Store with delta. Include in brief.
  DUPLICATE- Same fact already known. Skip. Log for source quality tracking.

Phase 2 Fast-Path Logic (saves ~50% of Judge LLM calls):
  Score > AUTO_MERGE_THRESHOLD  → AUTO-DUPLICATE  (no LLM, obvious duplicate)
  Score in GREY ZONE            → Judge LLM        (ambiguous, need reasoning)
  Score < GREY_ZONE_MIN or 0 matches → AUTO-NEW   (no LLM, obviously new)

Temporal overlap adjusts every score before thresholding, so facts from
different time periods can't be wrongly merged even at high vector similarity.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from config.settings import (
    SIMILARITY_THRESHOLD_DUPLICATE,
    SIMILARITY_THRESHOLD_UPDATE,
    settings,
)
from truebrief.arbiter.judge import JudgeLLM
from truebrief.arbiter.temporal import adjusted_similarity, entity_overlap
from truebrief.ledger.vector_store import VectorStore
from truebrief.models.alpha import Alpha, AlphaDecision, DecisionType

logger = logging.getLogger(__name__)

# ── Threshold constants ────────────────────────────────────────────────────────
# Auto-merge (DUPLICATE) if adjusted score exceeds this. No LLM call needed.
AUTO_MERGE_THRESHOLD: float = 0.97

# Grey zone: [GREY_ZONE_MIN, AUTO_MERGE_THRESHOLD) → send to Judge LLM.
# Below GREY_ZONE_MIN and when there are zero matches → AUTO-NEW.
GREY_ZONE_MIN: float = SIMILARITY_THRESHOLD_UPDATE   # 0.75 from settings

# How many matches to retrieve from the ledger for each judgment.
# 1 is enough for fast-path; we fetch up to 3 so the Judge LLM has context.
LEDGER_FETCH_LIMIT: int = 3

# Low-threshold fetch: cast a wider net so we don't miss the best match.
# The actual thresholding is done in Python after retrieval.
LEDGER_FETCH_THRESHOLD: float = 0.50


class Arbiter:
    """
    Pillar 4: The Judge.

    Phase 2 decision flow per Alpha:
      1. Generate embedding (if not already present)
      2. Fetch top-N similar facts from the Ledger
      3. Apply temporal adjustment to each score
      4. Fast-path: auto-DUPLICATE if top score > AUTO_MERGE_THRESHOLD
      5. Fast-path: auto-NEW if top score < GREY_ZONE_MIN (or zero matches)
      6. Grey-zone: call Judge LLM for MERGE / UPDATE / NEW decision
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        judge: Optional[JudgeLLM] = None,
    ) -> None:
        self.ledger = vector_store or VectorStore()
        self._judge_llm = judge or JudgeLLM(llm=self.ledger.llm)

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def judge_alpha(self, alpha: Alpha, topic_id: Optional[str] = None) -> AlphaDecision:
        """
        Evaluate a single Alpha and return a verdict.

        Args:
            alpha:    The incoming fact to evaluate.
            topic_id: Scope the ledger search to this topic (recommended).

        Returns:
            AlphaDecision with decision, score, matched_alpha_id, reasoning, and delta.
        """
        log_prefix = f"[ARBITER] '{alpha.alpha_text[:60]}...'"
        logger.info(f"{log_prefix}")

        # Step 1 - Ensure we have an embedding
        alpha = self._ensure_embedding(alpha, log_prefix)
        if alpha.embedding is None:
            # Embedding failed - fail safe to NEW so the fact isn't silently dropped
            logger.warning(f"{log_prefix} → AUTO-NEW (embedding failure)")
            return AlphaDecision(
                alpha=alpha,
                decision=DecisionType.NEW,
                reasoning="Embedding generation failed. Defaulting to NEW.",
            )

        # Step 2 - Fetch similar facts from the Ledger
        raw_matches = self._fetch_matches(alpha, topic_id)

        # Step 3 - Apply temporal (and optionally entity) adjustment to each raw score
        adjusted: List[Tuple[Alpha, float]] = []
        for match, score in raw_matches:
            adj = adjusted_similarity(score, alpha.event_date, match.event_date)
            if settings.V3_ENTITY_DEDUP:
                # Penalise / reward based on entity overlap: no-overlap → 20% penalty,
                # full-overlap → no change, neutral (empty entities) → 10% penalty.
                e_factor = 0.80 + 0.20 * entity_overlap(alpha.entities, match.entities)
                adj *= e_factor
            adjusted.append((match, adj))

        # Sort by adjusted score descending
        adjusted.sort(key=lambda x: x[1], reverse=True)

        # Step 4/5 - Fast paths (no LLM needed)
        if not adjusted:
            logger.info(f"{log_prefix} → AUTO-NEW (zero ledger matches)")
            return AlphaDecision(
                alpha=alpha,
                decision=DecisionType.NEW,
                reasoning="No similar facts found in ledger.",
            )

        top_match, top_score = adjusted[0]

        if top_score >= AUTO_MERGE_THRESHOLD:
            logger.info(
                f"{log_prefix} → AUTO-DUPLICATE "
                f"(score={top_score:.3f} >= {AUTO_MERGE_THRESHOLD})"
            )
            return AlphaDecision(
                alpha=alpha,
                decision=DecisionType.DUPLICATE,
                similarity_score=top_score,
                matched_alpha_id=top_match.id,
                reasoning=f"Auto-merge: adjusted score {top_score:.3f} exceeds {AUTO_MERGE_THRESHOLD}.",
            )

        if top_score < GREY_ZONE_MIN:
            logger.info(
                f"{log_prefix} → AUTO-NEW "
                f"(score={top_score:.3f} < {GREY_ZONE_MIN})"
            )
            return AlphaDecision(
                alpha=alpha,
                decision=DecisionType.NEW,
                similarity_score=top_score,
                matched_alpha_id=top_match.id,
                reasoning=f"Highest adjusted score {top_score:.3f} below grey-zone threshold {GREY_ZONE_MIN}.",
            )

        # Step 6 - Grey zone: call Judge LLM
        logger.info(
            f"{log_prefix} → GREY ZONE (score={top_score:.3f}) - calling Judge LLM"
        )
        decision, delta = self._judge_llm.call(alpha, adjusted)

        logger.info(f"{log_prefix} → Judge decision: {decision.value}" + (f" | delta: {delta}" if delta else ""))

        return AlphaDecision(
            alpha=alpha,
            decision=decision,
            similarity_score=top_score,
            matched_alpha_id=top_match.id,
            reasoning=f"Judge LLM decision. Top match score: {top_score:.3f}.",
            delta=delta,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Backward-compatibility alias
    # ──────────────────────────────────────────────────────────────────────────

    def judge(self, alpha: Alpha, topic_id: Optional[str] = None) -> AlphaDecision:
        """
        Alias for judge_alpha(). Kept so existing callers (pipeline/runner.py)
        don't break. Prefer judge_alpha() in new code.
        """
        return self.judge_alpha(alpha, topic_id)

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _ensure_embedding(self, alpha: Alpha, log_prefix: str) -> Alpha:
        """Generate embedding if not already attached to the Alpha."""
        if alpha.embedding:
            return alpha
        try:
            alpha.embedding = self.ledger.llm.embed(alpha.alpha_text)
        except Exception as exc:
            logger.error(f"{log_prefix} Embedding failed: {exc}")
            alpha.embedding = None
        return alpha

    def _fetch_matches(
        self, alpha: Alpha, topic_id: Optional[str]
    ) -> List[Tuple[Alpha, float]]:
        """Fetch the closest known facts from the ledger."""
        try:
            return self.ledger.find_similar(
                embedding=alpha.embedding,
                topic_id=topic_id,
                limit=LEDGER_FETCH_LIMIT,
                threshold=LEDGER_FETCH_THRESHOLD,
            )
        except Exception as exc:
            logger.error(f"Ledger fetch failed: {exc}. Treating as zero matches.")
            return []
