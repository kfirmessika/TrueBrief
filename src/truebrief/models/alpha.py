"""
Alpha data models.

Alpha: an atomic, verifiable fact extracted from an article.
AlphaDecision: the Arbiter's verdict on whether an Alpha is NEW, DUPLICATE, or UPDATE.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4


class DecisionType(str, Enum):
    NEW = "NEW"
    DUPLICATE = "DUPLICATE"
    UPDATE = "UPDATE"


@dataclass
class Alpha:
    """
    A single, atomic, verifiable fact extracted by the Harvester.

    Example:
        alpha_text   = "TSMC Q1 2025 revenue was $25.5B, up 41.6% YoY."
        entities     = ["TSMC"]
        event_date   = datetime(2025, 4, 17)
        confidence   = 0.92
    """

    alpha_text: str                         # The fact itself, self-contained
    entities: list[str]                     # Named entities (companies, people, places)
    source_url: str                         # Article URL the fact came from
    source_name: str                        # Human-readable source label
    event_date: Optional[datetime] = None   # When did the event happen? (not published_at)
    context: Optional[str] = None           # Extra context (e.g. broader headline)
    confidence: float = 1.0                 # 0.0–1.0; facts < 0.6 are dropped by Harvester
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    topic_id: Optional[str] = None

    # Populated after storage in the Ledger
    embedding: Optional[list[float]] = None

    # Development-type label emitted by the harvester (IC2 / §10B.2a).
    # state_change | escalation | development | incremental | tally | routine | None (unlabelled)
    event_class: Optional[str] = None

    # Populated by the Verifier stage (before Ledger)
    verified_count: int = 0                       # number of independent sources that confirmed this fact
    verifier_flags: list[str] = field(default_factory=list)  # e.g. ["retrospective", "ungrounded"]

    # IC4 contradiction flag (set by the Arbiter when this fact contradicts a stored one).
    contradicts_id: Optional[str] = None          # known_facts.id of the contradicted fact
    contradiction_note: Optional[str] = None      # short reason, e.g. "status conflict: 'closed' vs 'open'"


@dataclass
class AlphaDecision:
    """The Arbiter's verdict for a single Alpha."""

    alpha: Alpha
    decision: DecisionType
    similarity_score: float = 0.0           # Cosine similarity to nearest known fact
    matched_alpha_id: Optional[str] = None  # ID of the fact this duplicates/updates
    reasoning: Optional[str] = None         # Explanation (fast-path reason or Judge LLM)
    delta: Optional[str] = None             # UPDATE only: one sentence - what is new
