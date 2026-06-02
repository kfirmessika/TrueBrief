"""
Topic data models.

Topic: a user-defined subject to monitor (e.g. "TSMC semiconductor supply chain").
TopicSchedule: polling cadence metadata (Phase 2+).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4


class TopicStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


@dataclass
class Topic:
    """
    A monitored subject. Created by the user. Pipeline runs are scoped to a Topic.

    The Query Builder takes `name` and produces search queries from it.
    """

    name: str                               # User-provided, e.g. "TSMC semiconductor"
    id: str = field(default_factory=lambda: str(uuid4()))
    user_id: Optional[str] = None           # Owning user (Phase 3 auth)
    status: TopicStatus = TopicStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    last_scanned_at: Optional[datetime] = None
    scan_count: int = 0                     # Total pipeline runs for this topic

    # Derived fields (populated by Query Builder, cached for reuse)
    primary_query: Optional[str] = None
    alt_queries: list[str] = field(default_factory=list)
    rss_categories: list[str] = field(default_factory=list)

    def mark_scanned(self) -> None:
        """Call after each successful pipeline run."""
        self.last_scanned_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.scan_count += 1


@dataclass
class TopicSchedule:
    """
    Polling schedule metadata for a Topic. Used by the Celery scheduler (Phase 2).

    AYR (Alpha Yield Rate) drives the poll_interval_minutes:
      High-yield topics → poll more often.
      Quiet topics → poll less often.
    """

    topic_id: str
    poll_interval_minutes: int = 60         # Default: every hour
    ayr_score: float = 0.0                  # Alphas per scan (rolling average)
    last_calculated_at: Optional[datetime] = None
