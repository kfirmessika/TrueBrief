"""
Brave Search Layer - collector/brave_layer.py

Queries the Brave Search Web API for topic intelligence.
Uses httpx directly (no SDK); requires BRAVE_API_KEY in settings.

Brave is a targeted search engine — results are already on-topic,
so the pipeline's keyword pre-filter is skipped for this source.
"""

from __future__ import annotations

import logging
from typing import List
from urllib.parse import urlparse

import httpx

from config.settings import settings
from truebrief.collector.base import SourceLayer
from truebrief.collector.query_builder import SearchQuery
from truebrief.models.article import ArticleSource, RawArticle

logger = logging.getLogger(__name__)

_BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
_TIMEOUT = 10.0
_MAX_RESULTS = 5


class BraveLayer(SourceLayer):
    """
    Brave Search Web API source plugin.

    Freshness filter (pd = past day) keeps results timely.
    The snippet from Brave's `description` field serves as the article text;
    ArticleExtractor can optionally fetch the full body downstream.
    """

    def __init__(self) -> None:
        self._api_key: str = settings.BRAVE_API_KEY
        if not self._api_key:
            logger.warning("BRAVE_API_KEY not set — BraveLayer will return no results.")

    @property
    def name(self) -> str:
        return "brave"

    def search(self, query: SearchQuery) -> List[RawArticle]:
        if not self._api_key:
            return []

        logger.info("Brave searching for: %s", query.primary_query)

        try:
            response = httpx.get(
                _BRAVE_ENDPOINT,
                headers={
                    "X-Subscription-Token": self._api_key,
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                },
                params={
                    "q": query.primary_query,
                    "count": _MAX_RESULTS,
                    "freshness": "pd",          # past 24 hours
                    "result_filter": "web",
                    "text_decorations": "false",
                },
                timeout=_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.error("Brave search failed: %s", exc)
            return []

        articles: List[RawArticle] = []
        for result in data.get("web", {}).get("results", []):
            url: str = result.get("url", "")
            title: str = result.get("title", "")
            description: str = result.get("description", "")
            if not url or not title:
                continue

            articles.append(
                RawArticle(
                    url=url,
                    title=title,
                    source_name=self._domain(url),
                    source_type=ArticleSource.BRAVE,
                    published_at=None,
                    text=description or None,
                )
            )

        logger.info("Brave returned %d results.", len(articles))
        return articles

    @staticmethod
    def _domain(url: str) -> str:
        try:
            return urlparse(url).netloc.replace("www.", "") or "brave"
        except Exception:
            return "brave"
