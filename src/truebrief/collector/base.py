"""
Base classes for Collector plugins - collector/base.py
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from truebrief.collector.query_builder import SearchQuery
from truebrief.models.article import RawArticle


class SourceLayer(ABC):
    """
    Abstract base class for all data sources (RSS, Tavily, Google News, etc.).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Machine-friendly name of the source layer (e.g. 'rss', 'tavily')."""
        pass

    @abstractmethod
    def search(self, query: SearchQuery) -> List[RawArticle]:
        """
        Search this layer for articles matching the query.
        Returns a list of RawArticle objects.
        """
        pass
