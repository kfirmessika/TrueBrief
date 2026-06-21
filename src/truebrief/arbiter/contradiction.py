"""
Contradiction detection - arbiter/contradiction.py  (IC4 — architecture §5/§8B)

Two facts about the same actors at the same time that assert INCOMPATIBLE values
(Strait of Hormuz "closed" vs "open"; death toll 3,912 vs 3,468) are usually the
story — flag the pair instead of storing both deadpan as unrelated NEW facts.

This detector is deliberately CONSERVATIVE and deterministic (no LLM call): it
only fires on clear hard-state polarity flips or same-time numeric conflicts on a
shared metric. It would rather miss a subtle contradiction than raise a false one.
A running tally (3,468 → 3,912 across different days) is NOT a contradiction — that
is an IC1 update — so numeric conflicts require the SAME time window and a non-tally
classification.
"""

from __future__ import annotations

import re
from typing import List, Optional

from truebrief.arbiter.temporal import temporal_overlap

# Gates: a contradiction needs a shared SUBJECT and an overlapping time window.
# (Unlike dedup, the actors usually DIFFER — Iran says "closed", the US says "open" —
#  so we require a shared subject entity, not high Jaccard overlap.)
MIN_TEMPORAL_OVERLAP = 0.7          # polarity flips
NUMERIC_TEMPORAL_OVERLAP = 0.9      # numeric conflicts: stricter (same day) to exclude tallies

# Hard-state opposites only — deliberately excludes rose/fell/up/down (those are
# tallies/markets, handled elsewhere and prone to false positives).
ANTONYM_PAIRS = [
    ("open", "closed"),
    ("open", "shut"),
    ("open", "closure"),
    ("open", "closing"),
    ("open", "sealed"),
    ("reopened", "closed"),
    ("reopened", "closure"),
    ("agreed", "rejected"),
    ("signed", "rejected"),
    ("approved", "rejected"),
    ("accepted", "rejected"),
    ("confirmed", "denied"),
    ("confirmed", "refuted"),
    ("advancing", "withdrawing"),
    ("advance", "retreat"),
    ("ongoing", "ceased"),
    ("continues", "halted"),
    ("escalating", "de-escalating"),
    ("released", "detained"),
    ("released", "captured"),
    ("alive", "killed"),
    ("survived", "killed"),
    ("won", "lost"),
    ("victory", "defeat"),
]

# A numeric conflict only counts if both facts are talking about the same kind of
# quantity (so "4 drones" vs "$80 billion" never collide).
METRIC_KEYWORDS = [
    "toll", "killed", "dead", "death", "deaths", "casualties", "wounded", "injured",
    "billion", "million", "trillion", "percent", "%", "troops", "soldiers", "fighters",
]

_NUM_RE = re.compile(r"\b\d{1,3}(?:,\d{3})+\b|\b\d+(?:\.\d+)?\b")


# Generic actor/place words that, alone, are too weak to anchor a contradiction.
_GENERIC_ENTITIES = {"us", "u.s.", "usa", "united states", "officials", "government"}


def _shares_subject(entities_a: List[str], entities_b: List[str]) -> bool:
    """True if the two facts share at least one non-generic subject entity.

    Contradictions usually come from different actors making opposing claims about
    the SAME subject, so we require a shared subject (e.g. "Strait of Hormuz") rather
    than high overall entity overlap.
    """
    a = {e.strip().lower() for e in (entities_a or []) if e and e.strip()}
    b = {e.strip().lower() for e in (entities_b or []) if e and e.strip()}
    shared = a & b
    meaningful = shared - _GENERIC_ENTITIES
    return bool(meaningful)


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z%]+", text.lower()))


def _numbers(text: str) -> set[float]:
    out: set[float] = set()
    for m in _NUM_RE.findall(text):
        try:
            out.add(float(m.replace(",", "")))
        except ValueError:
            pass
    return out


def _polarity_conflict(text_a: str, text_b: str) -> Optional[str]:
    """One fact asserts a hard state, the other its opposite."""
    wa, wb = _words(text_a), _words(text_b)
    for x, y in ANTONYM_PAIRS:
        if (x in wa and y in wb) or (y in wa and x in wb):
            return f"status conflict: '{x}' vs '{y}'"
    return None


def _numeric_conflict(text_a: str, text_b: str) -> Optional[str]:
    """Same metric, different headline numbers (same-time => not a tally)."""
    wa, wb = _words(text_a), _words(text_b)
    shared_metric = (set(METRIC_KEYWORDS) & wa) & (set(METRIC_KEYWORDS) & wb)
    if not shared_metric:
        return None
    na, nb = _numbers(text_a), _numbers(text_b)
    if not na or not nb:
        return None
    # If the two facts share no number AND each has a distinct value, they conflict.
    if na != nb and not (na & nb):
        a_max, b_max = max(na), max(nb)
        if a_max != b_max:
            return f"value conflict: {a_max:g} vs {b_max:g}"
    return None


def detect_contradiction(
    text_a: str,
    entities_a: List[str],
    date_a,
    class_a: Optional[str],
    text_b: str,
    entities_b: List[str],
    date_b,
    class_b: Optional[str],
) -> Optional[str]:
    """
    Return a short reason string if fact A contradicts fact B, else None.

    Gates (both required): same actors (entity overlap) + overlapping time.
    Then: a hard-state polarity flip, or a same-time numeric conflict on a shared
    metric where neither fact is a running tally.
    """
    if not text_a or not text_b:
        return None
    if not _shares_subject(entities_a, entities_b):
        return None

    t_overlap = temporal_overlap(date_a, date_b)
    if t_overlap < MIN_TEMPORAL_OVERLAP:
        return None

    # Polarity flips are valid across the looser (same-ish week) window.
    polarity = _polarity_conflict(text_a, text_b)
    if polarity:
        return polarity

    # Numeric conflicts must be same-time AND not a running tally on either side.
    is_tally = (class_a == "tally") or (class_b == "tally")
    if not is_tally and t_overlap >= NUMERIC_TEMPORAL_OVERLAP:
        numeric = _numeric_conflict(text_a, text_b)
        if numeric:
            return numeric

    return None
