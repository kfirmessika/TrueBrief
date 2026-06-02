"""
Story Node data models.

StoryNode: a cluster of related Alphas that tell an evolving narrative.
Facts are grouped into stories so users see coherent threads rather than
a flat list of disconnected facts.

Phase 3, Task 3.1 - Story Nodes
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4


class StoryStatus(str, Enum):
    """Lifecycle status of a StoryNode."""
    ACTIVE = "active"       # Story is still developing (new facts arriving)
    RESOLVED = "resolved"   # Story has concluded (e.g. event happened, outcome known)
    STALE = "stale"         # No new facts for a long time (auto-set by staleness check)


@dataclass
class StoryNode:
    """
    A cluster of related Alphas that form an evolving narrative thread.

    Example:
        title        = "TSMC Arizona Fab Construction"
        summary      = "TSMC is building a new semiconductor fab in Arizona.
                        Construction is 60% complete as of Jan 2025.
                        Production is scheduled to begin Q2 2025."
        fact_count   = 3
        status       = ACTIVE

    Lifecycle:
        1. Created when a NEW Alpha doesn't match any existing story (or first Alpha in topic)
        2. Grows as UPDATE and related NEW Alphas are attached
        3. Summary is regenerated on each update (Task 3.3)
        4. Marked STALE if no updates in X days (future)
        5. Marked RESOLVED manually or by LLM detection (future)
    """

    title: str                                          # Short headline for the story cluster
    topic_id: str                                       # Which topic this story belongs to
    id: str = field(default_factory=lambda: str(uuid4()))
    summary: str = ""                                   # LLM-generated summary (Task 3.3)
    status: StoryStatus = StoryStatus.ACTIVE
    fact_count: int = 0                                 # Number of Alphas in this story
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Populated after storage - for story-level vector matching (Task 3.2)
    summary_embedding: Optional[list[float]] = None

    def add_fact(self) -> None:
        """Increment fact count and update timestamp when a new fact is attached."""
        self.fact_count += 1
        self.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
