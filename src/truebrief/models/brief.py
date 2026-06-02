"""
Brief data models.

BriefSection: a labelled group of Alphas (e.g. "NEW", "UPDATE").
Brief: the final deliverable - a structured intelligence report for a Topic + scan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from truebrief.models.alpha import Alpha, DecisionType


class BriefSectionType(str, Enum):
    NEW = "NEW"
    UPDATE = "UPDATE"
    NO_CHANGES = "NO_CHANGES"


@dataclass
class BriefSection:
    """A labelled group of Alphas within a Brief."""

    section_type: BriefSectionType
    alphas: list[Alpha] = field(default_factory=list)
    summary: Optional[str] = None           # LLM-generated section intro (Phase 2+)


@dataclass
class Brief:
    """
    The final deliverable: structured intelligence for a Topic scan.

    Phase 1: brief_text is a formatted plain-text report.
    Phase 2+: sections are used to build rich UI views.
    """

    topic_id: str
    topic_name: str
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    sections: list[BriefSection] = field(default_factory=list)
    brief_text: Optional[str] = None        # Formatted text output from Briefer

    # Metadata
    articles_processed: int = 0
    alphas_extracted: int = 0
    alphas_new: int = 0
    alphas_duplicate: int = 0
    alphas_update: int = 0
    scan_duration_seconds: Optional[float] = None

    @property
    def is_empty(self) -> bool:
        """True if no new or updated facts - suppressed in Phase 2."""
        return self.alphas_new == 0 and self.alphas_update == 0

    def add_section(self, section_type: BriefSectionType, alphas: list[Alpha]) -> None:
        if alphas:
            self.sections.append(BriefSection(section_type=section_type, alphas=alphas))

    def tally(self, decisions: list) -> None:
        """Populate count fields from a list of AlphaDecision objects."""
        for d in decisions:
            self.alphas_extracted += 1
            if d.decision == DecisionType.NEW:
                self.alphas_new += 1
            elif d.decision == DecisionType.DUPLICATE:
                self.alphas_duplicate += 1
            elif d.decision == DecisionType.UPDATE:
                self.alphas_update += 1
