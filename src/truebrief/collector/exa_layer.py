"""
Exa Search Layer - collector/exa_layer.py

Queries the Exa neural/keyword search API for topic intelligence.
Uses the official `exa-py` SDK; requires EXA_API_KEY in settings.

Exa returns full extracted article text directly (like Tavily), so the
pipeline's ArticleExtractor step is a no-op for Exa results.
Exa is a targeted search engine — results are already on-topic,
so the pipeline's keyword pre-filter is skipped for this source.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List
from urllib.parse import urlparse

from config.settings import settings
from truebrief.collector.base import SourceLayer
from truebrief.collector.query_builder import SearchQuery
from truebrief.models.article import ArticleSource, RawArticle

logger = logging.getLogger(__name__)

_MAX_RESULTS = 5
_MAX_TEXT_CHARS = 1500


class ExaLayer(SourceLayer):
    """
    Exa Search source plugin.

    Uses keyword search (not neural) to keep queries deterministic and
    closely matched to the pipeline's primary_query string.
    Full article text is returned by Exa directly via `search_and_contents()`.
    """

    def __init__(self) -> None:
        self._api_key: str = settings.EXA_API_KEY
        self._client = None
        if not self._api_key:
            logger.warning("EXA_API_KEY not set — ExaLayer will return no results.")
            return
        try:
            from exa_py import Exa  # type: ignore[import]
            self._client = Exa(api_key=self._api_key)
        except ImportError:
            logger.error("exa-py is not installed. Run: pip install exa-py")

    @property
    def name(self) -> str:
        return "exa"

    def search(self, query: SearchQuery) -> List[RawArticle]:
        if not self._client:
            return []

        logger.info("Exa searching for: %s", query.primary_query)

        try:
            results = self._client.search_and_contents(
                query.primary_query,
                num_results=_MAX_RESULTS,
                text={"max_characters": _MAX_TEXT_CHARS},
                type="keyword",
                use_autoprompt=False,
            )
        except Exception as exc:
            logger.error("Exa search failed: %s", exc)
            return []

        articles: List[RawArticle] = []
        for r in results.results:
            url: str = getattr(r, "url", "") or ""
            title: str = getattr(r, "title", "") or url
            text: str = getattr(r, "text", "") or ""
            published_raw = getattr(r, "published_date", None)

            if not url:
                continue

            published_at: datetime | None = None
            if published_raw:
                try:
                    published_at = datetime.fromisoformat(
                        str(published_raw).replace("Z", "+00:00")
                    )
                except Exception:
                    pass

            articles.append(
                RawArticle(
                    url=url,
                    title=title or self._domain(url),
                    source_name=self._domain(url),
                    source_type=ArticleSource.EXA,
                    published_at=published_at,
                    text=text or None,
                )
            )

        logger.info("Exa returned %d results.", len(articles))
        return articles

    @staticmethod
    def _domain(url: str) -> str:
        try:
            return urlparse(url).netloc.replace("www.", "") or "exa"
        except Exception:
            return "exa"
