"""
Temporal Overlap Engine - arbiter/temporal.py

Computes a temporal proximity score between two facts based on their event dates.
This score is used by the Arbiter to adjust cosine similarity: facts about
different time periods should never be merged, even if their text is similar.

Example:
  "TSMC Q3 2025 revenue was $22B"  vs  "TSMC Q1 2026 revenue was $25B"
  → Vector similarity might be 0.91 (both about TSMC revenue)
  → Temporal overlap = 0.0 (different quarters, >90 days apart)
  → Adjusted score = 0.91 × (0.7 + 0.3 × 0.0) = 0.637 → falls to UPDATE zone
"""

from __future__ import annotations

import logging
from datetime import datetime, date
from typing import Optional, Union

logger = logging.getLogger(__name__)

# How far apart (days) two event dates can be before temporal overlap = 0
TEMPORAL_WINDOW_DAYS = 30

# Weight of temporal signal in the adjusted similarity formula:
# adjusted = score × (SCORE_WEIGHT + TEMPORAL_WEIGHT × temporal_overlap)
SCORE_WEIGHT = 0.70
TEMPORAL_WEIGHT = 0.30


def temporal_overlap(
    date1: Optional[Union[datetime, date]],
    date2: Optional[Union[datetime, date]],
    window_days: int = TEMPORAL_WINDOW_DAYS,
) -> float:
    """
    Compute temporal proximity between two event dates.

    Returns:
        1.0  → same date (maximum proximity)
        0.5  → either date is unknown (neutral - don't penalize)
        0.0  → dates are >= window_days apart (no temporal overlap)

    Args:
        date1: Event date of fact 1 (datetime or date)
        date2: Event date of fact 2 (datetime or date)
        window_days: Number of days beyond which overlap = 0
    """
    if date1 is None or date2 is None:
        # Unknown dates: be neutral - don't penalize, don't reward
        return 0.5

    def _to_date(v):
        """Accept datetime, date, or ISO-format string (from Supabase JSON)."""
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, date):
            return v
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00")).date()
            except Exception:
                return None
        return None

    d1 = _to_date(date1)
    d2 = _to_date(date2)

    if d1 is None or d2 is None:
        return 0.5

    delta_days = abs((d1 - d2).days)

    if delta_days >= window_days:
        return 0.0

    return 1.0 - (delta_days / window_days)


def entity_overlap(
    entities1: list[str],
    entities2: list[str],
) -> float:
    """
    Compute the Jaccard-style overlap between two entity lists.

    Returns:
        1.0  → identical entity sets (strong signal: same subject)
        0.5  → one or both lists empty (neutral — can't penalise missing entities)
        0.0  → no entity overlap at all (different subjects)

    Used by the V3 entity-aware dedup path in the Arbiter.
    """
    if not entities1 or not entities2:
        return 0.5

    set1 = {e.lower() for e in entities1}
    set2 = {e.lower() for e in entities2}
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union else 0.5


def adjusted_similarity(
    vector_score: float,
    date1: Optional[Union[datetime, date]],
    date2: Optional[Union[datetime, date]],
    window_days: int = TEMPORAL_WINDOW_DAYS,
) -> float:
    """
    Adjust a cosine similarity score using the temporal proximity signal.

    Formula:
        adjusted = vector_score × (SCORE_WEIGHT + TEMPORAL_WEIGHT × temporal_overlap)

    Effect:
        - Same dates    → multiplied by (0.70 + 0.30 × 1.0) = 1.00 (no change)
        - Unknown dates → multiplied by (0.70 + 0.30 × 0.5) = 0.85 (small penalty)
        - 30+ days apart → multiplied by (0.70 + 0.30 × 0.0) = 0.70 (significant penalty)

    Args:
        vector_score: Raw cosine similarity from pgvector (0.0–1.0)
        date1: Event date of the new incoming fact
        date2: Event date of the known stored fact
        window_days: Passed to temporal_overlap
    """
    t_overlap = temporal_overlap(date1, date2, window_days)
    multiplier = SCORE_WEIGHT + TEMPORAL_WEIGHT * t_overlap
    result = vector_score * multiplier

    logger.debug(
        f"Temporal adjustment: score={vector_score:.3f} × multiplier={multiplier:.2f} "
        f"(temporal={t_overlap:.2f}) → {result:.3f}"
    )

    return result
