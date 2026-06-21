"""
Article data models.

RawArticle: what we get from a collector (RSS or Tavily).
ProcessedArticle: after text extraction (trafilatura), ready for the Harvester.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ArticleSource(str, Enum):
    RSS = "rss"
    TAVILY = "tavily"
    GOOGLE_NEWS = "google_news"  # Phase 2
    BRAVE = "brave"              # Phase 3 — Step 3.19
    EXA = "exa"                  # Phase 3 — Step 3.19


@dataclass
class RawArticle:
    """An article as returned by a collector layer - URL + metadata, text may be present."""

    url: str
    title: str
    source_name: str                    # e.g. "Reuters", "TechCrunch"
    source_type: ArticleSource
    published_at: Optional[datetime] = None
    # Text is populated immediately for Tavily (returns full text).
    # For RSS it's populated by the Extractor after fetching the URL.
    text: Optional[str] = None
    topic_id: Optional[str] = None      # links back to the Topic that triggered collection
    # Feed-provided summary/description. Used by the Extractor as a fallback when
    # full-text fetch fails (paywalls / 403 / bot walls) so the article still yields facts.
    snippet: Optional[str] = None


@dataclass
class ProcessedArticle:
    """An article with clean extracted text, ready for the Harvester."""

    url: str
    title: str
    source_name: str
    source_type: ArticleSource
    published_at: Optional[datetime]
    text: str                           # guaranteed non-empty
    word_count: int = field(init=False)
    topic_id: Optional[str] = None

    def __post_init__(self) -> None:
        self.word_count = len(self.text.split())

    @classmethod
    def from_raw(cls, raw: RawArticle) -> "ProcessedArticle":
        """Promote a RawArticle once its text has been extracted."""
        if not raw.text:
            raise ValueError(f"Cannot promote RawArticle with no text: {raw.url}")
        return cls(
            url=raw.url,
            title=raw.title,
            source_name=raw.source_name,
            source_type=raw.source_type,
            published_at=raw.published_at,
            text=raw.text,
            topic_id=raw.topic_id,
        )
