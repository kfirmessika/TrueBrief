"""
Signal Scorer - pipeline/signal_scorer.py

Batch LLM quality gate that runs between the Harvester and the Arbiter.
Filters out noise/reaction/rehash facts before they reach dedup or storage.

Two layers:
  1. Embedding pre-filter — compares each fact's embedding against the topic's
     learned signal_prototype vector. Low-similarity facts are skipped (85%)
     with a 15% random pass-through to prevent blind spots.
  2. LLM batch scorer — receives the surviving facts, classifies each as
     STATE_CHANGE / ANNOUNCEMENT / REACTION / NOISE and scores 0-10.
     Gate: score >= 6 AND class NOT IN (REACTION, NOISE).
     Facts scoring >= 7 update the prototype via exponential moving average.

Why batch: all candidates are scored in ONE LLM call per scan. The LLM sees
every fact at once, so it naturally scores duplicates lower (can't give "11
pardons" a 9 three times when it's the same event). This also handles
within-batch dedup implicitly without a separate call.
"""

from __future__ import annotations

import json
import logging
import random
from typing import List, Optional, Tuple

import numpy as np

from truebrief.llm.client import LLMClient, LLMError
from truebrief.models.alpha import Alpha

logger = logging.getLogger(__name__)

# Signal class labels the LLM may return.
_NOISE_CLASSES = {"REACTION", "NOISE"}

# Embedding cosine threshold for prototype pre-filter.
# Below this → fact is probably off-topic; skip unless exploration budget fires.
_PROTO_THRESHOLD = 0.35

# Exploration budget: fraction of low-similarity facts still sent to LLM.
# Prevents the prototype from becoming a closed feedback loop.
_EXPLORATION_RATE = 0.15

# EMA weight for updating the prototype with new high-signal embeddings.
# new = 0.8 * old + 0.2 * mean(high_signal_embeddings)
_EMA_ALPHA = 0.2

_SYSTEM_PROMPT = """\
You are a senior news analyst for a live intelligence briefing system.
Score each candidate fact strictly. Your job is to filter out noise so the
system only stores real developments worth tracking.

Return ONLY a valid JSON array. Nothing else.
"""

_SCORE_PROMPT_TEMPLATE = """\
Topic: {topic}

Classify each candidate fact below and score its signal strength 0-10.

Signal classes (pick exactly one):
  STATE_CHANGE  — a decision, action, or situation that was not true yesterday
  ANNOUNCEMENT  — official statement with a real commitment or consequence
  REACTION      — someone commenting on or responding to existing news; no new event
  NOISE         — opinion, entertainment, social media, poll, tally, rehash, old news

Score guide:
  8-10  Concrete, consequential, real event — something changed in the world
  6-7   Genuine development, worth tracking
  4-5   Borderline — minor update or soft signal
  1-3   Reaction, characterization, tangential mention
  0     Pure noise, off-topic, or identical to a fact already in this list

Rules:
  - Be harsh. On a slow news day most facts score ≤ 4.
  - REACTION can never score above 5.
  - NOISE scores 0-2.
  - If two facts in this list report the same underlying event, give the best
    one a real score and the rest 0-1 (not "two NEW facts" about one event).

Candidate facts:
{numbered_list}

Return a JSON array with exactly {n} objects, in order:
[{{"id": 1, "class": "STATE_CHANGE", "score": 8}}, {{"id": 2, "class": "REACTION", "score": 2}}, ...]
"""


def _cosine(a: list, b: list) -> float:
    av, bv = np.array(a, dtype=float), np.array(b, dtype=float)
    denom = np.linalg.norm(av) * np.linalg.norm(bv)
    return float(np.dot(av, bv) / denom) if denom > 0 else 0.0


class SignalScorer:
    """
    Batch signal quality gate between harvester and arbiter.

    Usage:
        scorer = SignalScorer()
        passed = scorer.score(alphas, topic_name="Iran nuclear deal", topic_id="uuid")
        # passed: subset of alphas that are real news (score>=6, not REACTION/NOISE)
    """

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        db=None,
    ) -> None:
        self.llm = llm or LLMClient()
        self._db = db  # lazy-loaded via _get_db()

    def _get_db(self):
        if self._db is None:
            from truebrief.ledger.database import get_supabase
            self._db = get_supabase()
        return self._db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score(
        self,
        alphas: List[Alpha],
        topic_name: str,
        topic_id: Optional[str] = None,
    ) -> List[Alpha]:
        """
        Filter alphas by signal quality. Returns only alphas that pass
        (score >= 6, class not REACTION or NOISE).

        Side-effect: updates signal_prototype in DB for facts scoring >= 7.
        """
        if not alphas:
            return []

        # 1. Ensure embeddings exist (reuse if harvester already computed them).
        self._ensure_embeddings(alphas)

        # 2. Load the topic's signal prototype (may be None on early scans).
        prototype = self._load_prototype(topic_id) if topic_id else None

        # 3. Embedding pre-filter.
        if prototype:
            to_score, skipped = self._proto_filter(alphas, prototype)
            if skipped:
                logger.info(
                    "  [SignalScorer] Proto-filter: %d sent to LLM, %d skipped (low similarity)",
                    len(to_score),
                    len(skipped),
                )
        else:
            to_score = alphas

        if not to_score:
            logger.info("  [SignalScorer] All %d facts filtered by prototype.", len(alphas))
            return []

        # 4. LLM batch scoring.
        scored = self._llm_score(to_score, topic_name)
        if scored is None:
            # LLM failed — fail open (pass everything to arbiter).
            logger.warning("  [SignalScorer] LLM scoring failed — passing all facts through.")
            return alphas

        # 5. Gate: score >= 6 AND class not in (REACTION, NOISE).
        passed = []
        high_signal_embeddings = []
        for alpha, cls, score in scored:
            if score >= 6 and cls not in _NOISE_CLASSES:
                passed.append(alpha)
            else:
                logger.info(
                    "  [SignalScorer] DROPPED [%s/%d]: %s",
                    cls,
                    score,
                    alpha.alpha_text[:80],
                )
            if score >= 7:
                high_signal_embeddings.append(alpha.embedding)

        logger.info(
            "  [SignalScorer] %d/%d facts passed signal gate.",
            len(passed),
            len(to_score),
        )

        # 6. Update prototype with high-signal facts (fire-and-forget, non-fatal).
        if topic_id and high_signal_embeddings:
            try:
                self._update_prototype(topic_id, high_signal_embeddings, prototype)
            except Exception as upd_err:
                logger.warning("  [SignalScorer] Prototype update failed (non-fatal): %s", upd_err)

        return passed

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_embeddings(self, alphas: List[Alpha]) -> None:
        """Embed any alphas that don't already have embeddings."""
        missing = [a for a in alphas if not a.embedding]
        if not missing:
            return
        texts = [a.alpha_text for a in missing]
        try:
            embeddings = self.llm.embed_batch(texts)
            for alpha, emb in zip(missing, embeddings):
                alpha.embedding = emb
        except Exception as emb_err:
            logger.warning("  [SignalScorer] embed_batch failed: %s", emb_err)
            # Fall back to individual embeds.
            for alpha in missing:
                try:
                    alpha.embedding = self.llm.embed(alpha.alpha_text)
                except Exception:
                    pass

    def _proto_filter(
        self, alphas: List[Alpha], prototype: List[float]
    ) -> Tuple[List[Alpha], List[Alpha]]:
        """
        Split alphas into (to_score, skipped) using prototype cosine similarity.
        Low-similarity facts have a _EXPLORATION_RATE chance of still being scored.
        """
        to_score, skipped = [], []
        for alpha in alphas:
            if not alpha.embedding:
                to_score.append(alpha)  # no embedding → can't filter, send to LLM
                continue
            sim = _cosine(alpha.embedding, prototype)
            if sim >= _PROTO_THRESHOLD or random.random() < _EXPLORATION_RATE:
                to_score.append(alpha)
            else:
                skipped.append(alpha)
        return to_score, skipped

    def _llm_score(
        self, alphas: List[Alpha], topic_name: str
    ) -> Optional[List[Tuple[Alpha, str, int]]]:
        """
        One LLM call scoring all alphas. Returns (alpha, class, score) tuples
        in the same order as the input list, or None on unrecoverable failure.
        """
        numbered = "\n".join(
            f"{i+1}. {a.alpha_text}" for i, a in enumerate(alphas)
        )
        prompt = _SCORE_PROMPT_TEMPLATE.format(
            topic=topic_name,
            numbered_list=numbered,
            n=len(alphas),
        )

        for attempt in range(1, 3):
            try:
                raw = self.llm.call(
                    step_name="signal_scorer",
                    prompt=prompt,
                    json_mode=True,
                    system_prompt=_SYSTEM_PROMPT,
                )
                parsed = self._parse_response(raw, len(alphas))
                if parsed is not None:
                    return [(alphas[i], cls, score) for i, (cls, score) in enumerate(parsed)]
                logger.warning(
                    "  [SignalScorer] Parse failed (attempt %d/2), retrying.", attempt
                )
            except LLMError as e:
                logger.error("  [SignalScorer] LLM call failed (attempt %d/2): %s", attempt, e)

        return None

    @staticmethod
    def _parse_response(
        raw: str, expected: int
    ) -> Optional[List[Tuple[str, int]]]:
        """
        Parse JSON array of {"id": N, "class": ..., "score": N}.
        Returns list of (class, score) in 1-based id order, or None on failure.
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None

        # Tolerate wrapped responses.
        if isinstance(data, dict):
            for key in ("results", "facts", "items"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break

        if not isinstance(data, list) or len(data) != expected:
            return None

        # Sort by explicit id if present.
        if all(isinstance(d, dict) and isinstance(d.get("id"), int) for d in data):
            data = sorted(data, key=lambda d: d["id"])

        results: List[Tuple[str, int]] = []
        for item in data:
            if not isinstance(item, dict):
                return None
            cls = str(item.get("class", "NOISE")).upper().strip()
            if cls not in {"STATE_CHANGE", "ANNOUNCEMENT", "REACTION", "NOISE"}:
                cls = "NOISE"
            try:
                score = max(0, min(10, int(item.get("score", 0))))
            except (TypeError, ValueError):
                score = 0
            results.append((cls, score))

        return results

    def _load_prototype(self, topic_id: str) -> Optional[List[float]]:
        """Load the signal_prototype vector for a topic. Returns None if not set."""
        try:
            db = self._get_db()
            resp = (
                db.table("topics")
                .select("signal_prototype")
                .eq("id", topic_id)
                .single()
                .execute()
            )
            proto = resp.data.get("signal_prototype") if resp.data else None
            if proto is None:
                return None
            # Supabase may return list or JSON string.
            if isinstance(proto, str):
                proto = json.loads(proto)
            return list(proto)
        except Exception as e:
            logger.debug("  [SignalScorer] Could not load prototype: %s", e)
            return None

    def _update_prototype(
        self,
        topic_id: str,
        high_signal_embeddings: List[List[float]],
        current: Optional[List[float]],
    ) -> None:
        """Update signal_prototype via EMA: new = 0.8*old + 0.2*mean(high_signal)."""
        mean_emb = np.mean(
            [np.array(e, dtype=float) for e in high_signal_embeddings], axis=0
        )
        if current is not None:
            updated = (1 - _EMA_ALPHA) * np.array(current, dtype=float) + _EMA_ALPHA * mean_emb
        else:
            updated = mean_emb

        db = self._get_db()
        db.table("topics").update(
            {"signal_prototype": updated.tolist()}
        ).eq("id", topic_id).execute()

        logger.info(
            "  [SignalScorer] Prototype updated with %d high-signal embeddings.",
            len(high_signal_embeddings),
        )
