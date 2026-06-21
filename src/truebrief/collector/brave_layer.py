"""
Brave Search Layer - collector/brave_layer.py

Queries the Brave News Search API for topic intelligence.
Uses httpx directly (no SDK); requires BRAVE_API_KEY in settings.

Uses the /news/search endpoint (not /web/search): this returns only news articles,
behaves like Tavily's topic="news" mode, and surfaces sources Tavily misses
(Haaretz, Ynet, CFR, Arab News, IBTimes, regional press).

Brave is a targeted search engine — results are already on-topic,
so the pipeline's keyword pre-filter is skipped for this source.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import List
from urllib.parse import urlparse

import httpx

from config.settings import settings
from truebrief.collector.base import SourceLayer
from truebrief.collector.query_builder import SearchQuery
from truebrief.models.article import ArticleSource, RawArticle

logger = logging.getLogger(__name__)

# /news/search returns actual news articles (not generic web results).
# Switched from /web/search which returned Wikipedia/homepages on abstract queries.
_BRAVE_NEWS_ENDPOINT = "https://api.search.brave.com/res/v1/news/search"
_TIMEOUT = 10.0
_MAX_RESULTS = 5


class BraveLayer(SourceLayer):
    """
    Brave News Search API source plugin.

    Hits /news/search with freshness=pd (past 24h) — returns only recent news articles,
    different source diversity than Tavily. The description field serves as article text.
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
                _BRAVE_NEWS_ENDPOINT,
                headers={
                    "X-Subscription-Token": self._api_key,
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                },
                params={
                    "q": query.primary_query,
                    "count": _MAX_RESULTS,
                    "freshness": "pd",   # past 24 hours
                    "country": "US",
                    "text_decorations": "false",
                },
                timeout=_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.error("Brave search failed: %s", exc)
            return []

        # /news/search returns top-level "results" list (not nested under "web")
        articles: List[RawArticle] = []
        for result in data.get("results", []):
            url: str = result.get("url", "")
            title: str = result.get("title", "")
            description: str = result.get("description", "")
            if not url or not title:
                continue

            # News endpoint returns age as relative string ("2 hours ago", "1 day ago")
            pub_date = self._parse_age(result.get("age", ""))

            articles.append(
                RawArticle(
                    url=url,
                    title=title,
                    source_name=self._domain(url),
                    source_type=ArticleSource.BRAVE,
                    published_at=pub_date,
                    text=description or None,
                )
            )

        logger.info("Brave returned %d results.", len(articles))
        return articles

    @staticmethod
    def _parse_age(age_str: str) -> datetime | None:
        """Convert Brave's relative age string to datetime.
        Examples: '2 hours ago', '1 day ago', '30 minutes ago'
        """
        if not age_str:
            return None
        try:
            now = datetime.utcnow()
            age_str = age_str.lower().strip()
            m = re.search(r'(\d+)\s+(minute|hour|day|week)', age_str)
            if not m:
                return None
            n, unit = int(m.group(1)), m.group(2)
            if unit == "minute":
                return now - timedelta(minutes=n)
            if unit == "hour":
                return now - timedelta(hours=n)
            if unit == "day":
                return now - timedelta(days=n)
            if unit == "week":
                return now - timedelta(weeks=n)
        except Exception:
            pass
        return None

    @staticmethod
    def _domain(url: str) -> str:
        try:
            return urlparse(url).netloc.replace("www.", "") or "brave"
        except Exception:
            return "brave"
