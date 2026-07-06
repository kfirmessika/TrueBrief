"""
Signal Scorer - pipeline/signal_scorer.py

Batch LLM quality gate that runs between the Harvester and the Arbiter.
Filters out noise/reaction/rehash facts before they reach dedup or storage.

Three layers:
  1. Embedding pre-filter — compares each fact's embedding against the topic's
     learned signal_prototype vector. Low-similarity facts are skipped (85%)
     with a 15% random pass-through to prevent blind spots.
  2. Within-batch dedup — compares all facts in this scan against each other.
     If cosine > 0.92 between two facts, the shorter/lower-confidence one is
     dropped. Catches "11 pardons x3" before the LLM call.
  3. LLM batch scorer — receives surviving facts, classifies each as
     STATE_CHANGE / ANNOUNCEMENT / REACTION / NOISE and scores 0-10.
     Gate: score >= 6 AND class NOT IN (REACTION, NOISE).
     Facts scoring >= 7 update the prototype via exponential moving average.

Returns (passed_facts, score_log) where score_log contains ALL facts with their
scores and drop reasons — wire this into pipeline_trace for debugging.
"""

from __future__ import annotations

import json
import logging
import random
from typing import Dict, List, Optional, Tuple

import numpy as np

from truebrief.llm.client import LLMClient, LLMError
from truebrief.models.alpha import Alpha

logger = logging.getLogger(__name__)

# Signal class labels the LLM may return.
_NOISE_CLASSES = {"REACTION", "NOISE"}

# Embedding cosine threshold for prototype pre-filter.
_PROTO_THRESHOLD = 0.35

# Exploration budget: fraction of low-proto-similarity facts still sent to LLM.
_EXPLORATION_RATE = 0.15

# Within-batch dedup threshold: facts this similar are the same event.
_BATCH_DEDUP_THRESHOLD = 0.92

# EMA weight for prototype updates.
# new = (1 - EMA_ALPHA) * old + EMA_ALPHA * mean(high_signal_embs)
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
    one a real score and the rest 0-1 (not two separate NEW facts about one event).

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
        passed, score_log = scorer.score(alphas, topic_name="...", topic_id="...")
        # passed: facts that are real news (score>=6, not REACTION/NOISE)
        # score_log: all facts with scores + drop reasons — write to pipeline_trace
    """

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        db=None,
    ) -> None:
        self.llm = llm or LLMClient()
        self._db = db

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
    ) -> Tuple[List[Alpha], List[Dict]]:
        """
        Filter alphas by signal quality.

        Returns:
            passed:    alphas with score >= 6 and class not REACTION/NOISE.
                       Each alpha has signal_score and signal_class set.
            score_log: one dict per input alpha with keys:
                       text, class, score, kept, drop_reason, source_url
                       Wire into pipeline_trace for full auditability.
        """
        if not alphas:
            return [], []

        score_log: List[Dict] = []

        # 1. Ensure embeddings.
        self._ensure_embeddings(alphas)

        # 2. Load prototype.
        prototype = self._load_prototype(topic_id) if topic_id else None

        # 3. Prototype pre-filter — low-similarity facts skipped with exploration budget.
        if prototype:
            to_score, proto_skipped = self._proto_filter(alphas, prototype)
            for a in proto_skipped:
                score_log.append({
                    "text": a.alpha_text[:200],
                    "class": None,
                    "score": None,
                    "kept": False,
                    "drop_reason": "proto_filter",
                    "source_url": a.source_url,
                })
                logger.info("  [SignalScorer] PROTO-SKIP: %s", a.alpha_text[:80])
        else:
            to_score = list(alphas)

        if not to_score:
            return [], score_log

        # 4. Within-batch dedup — drop near-identical facts before LLM call.
        to_score, batch_dupes = self._batch_dedup(to_score)
        for a in batch_dupes:
            score_log.append({
                "text": a.alpha_text[:200],
                "class": None,
                "score": None,
                "kept": False,
                "drop_reason": "batch_duplicate",
                "source_url": a.source_url,
            })
            logger.info("  [SignalScorer] BATCH-DUP: %s", a.alpha_text[:80])

        if not to_score:
            return [], score_log

        # 5. LLM batch scoring.
        raw_scored = self._llm_score(to_score, topic_name)
        if raw_scored is None:
            # LLM failed — fail open, pass everything through.
            logger.warning("  [SignalScorer] LLM scoring failed — passing all %d facts through.", len(to_score))
            for a in to_score:
                score_log.append({
                    "text": a.alpha_text[:200],
                    "class": None,
                    "score": None,
                    "kept": True,
                    "drop_reason": None,
                    "source_url": a.source_url,
                })
            return to_score, score_log

        # 6. Apply gate + annotate alphas + collect high-signal embeddings.
        passed: List[Alpha] = []
        high_signal_embeddings: List[List[float]] = []

        for alpha, cls, score in raw_scored:
            keeps = score >= 6 and cls not in _NOISE_CLASSES
            alpha.signal_score = score
            alpha.signal_class = cls
            score_log.append({
                "text": alpha.alpha_text[:200],
                "class": cls,
                "score": score,
                "kept": keeps,
                "drop_reason": None if keeps else f"{cls}/{score}",
                "source_url": alpha.source_url,
            })
            if keeps:
                passed.append(alpha)
                if score >= 7:
                    high_signal_embeddings.append(alpha.embedding)
            else:
                logger.info(
                    "  [SignalScorer] DROPPED [%s/%d]: %s",
                    cls, score, alpha.alpha_text[:80],
                )

        logger.info(
            "  [SignalScorer] %d/%d passed gate (batch: %d batch-duped, %d LLM-scored).",
            len(passed), len(alphas), len(batch_dupes), len(to_score),
        )

        # 7. Update prototype with high-signal facts.
        if topic_id and high_signal_embeddings:
            try:
                self._update_prototype(topic_id, high_signal_embeddings, prototype)
            except Exception as upd_err:
                logger.warning("  [SignalScorer] Prototype update failed (non-fatal): %s", upd_err)

        return passed, score_log

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
            logger.warning("  [SignalScorer] embed_batch failed: %s — falling back per-alpha.", emb_err)
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
                to_score.append(alpha)
                continue
            sim = _cosine(alpha.embedding, prototype)
            if sim >= _PROTO_THRESHOLD or random.random() < _EXPLORATION_RATE:
                to_score.append(alpha)
            else:
                skipped.append(alpha)
        return to_score, skipped

    def _batch_dedup(
        self, alphas: List[Alpha]
    ) -> Tuple[List[Alpha], List[Alpha]]:
        """
        Remove within-batch near-duplicates before the LLM call.

        If two facts have cosine > _BATCH_DEDUP_THRESHOLD, they're the same event
        from two different articles. Keep the longer/higher-confidence one.

        This is O(N²) but N is typically 10-50 per scan — fine.
        """
        if len(alphas) <= 1:
            return alphas, []

        kept_indices: List[int] = []
        dropped_indices: List[int] = []

        for i, alpha in enumerate(alphas):
            if not alpha.embedding:
                kept_indices.append(i)
                continue
            is_dup = False
            for j in kept_indices:
                other = alphas[j]
                if not other.embedding:
                    continue
                sim = _cosine(alpha.embedding, other.embedding)
                if sim >= _BATCH_DEDUP_THRESHOLD:
                    # Keep the one with more text content (more complete fact).
                    if len(alpha.alpha_text) > len(other.alpha_text):
                        # Replace the already-kept one with this better version.
                        kept_indices[kept_indices.index(j)] = i
                        dropped_indices.append(j)
                    else:
                        dropped_indices.append(i)
                    is_dup = True
                    break
            if not is_dup:
                kept_indices.append(i)

        kept = [alphas[i] for i in kept_indices]
        dropped = [alphas[i] for i in dropped_indices]

        if dropped:
            logger.info(
                "  [SignalScorer] Within-batch dedup: %d facts collapsed to %d.",
                len(alphas), len(kept),
            )

        return kept, dropped

    def _llm_score(
        self, alphas: List[Alpha], topic_name: str
    ) -> Optional[List[Tuple[Alpha, str, int]]]:
        """One LLM call scoring all alphas. Returns (alpha, class, score) or None on failure."""
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
                logger.warning("  [SignalScorer] Parse failed (attempt %d/2).", attempt)
            except LLMError as e:
                logger.error("  [SignalScorer] LLM call failed (attempt %d/2): %s", attempt, e)

        return None

    @staticmethod
    def _parse_response(raw: str, expected: int) -> Optional[List[Tuple[str, int]]]:
        """Parse JSON array into (class, score) list in id order, or None on failure."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None

        if isinstance(data, dict):
            for key in ("results", "facts", "items"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break

        if not isinstance(data, list) or len(data) != expected:
            return None

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
        """Load signal_prototype for a topic. Returns None if not set."""
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
