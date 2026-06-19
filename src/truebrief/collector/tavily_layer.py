"""
Tavily Layer Collector Plugin - collector/tavily_layer.py

Search the web for topic-specific intelligence.
Provides high coverage and clean extracted text.
"""

from __future__ import annotations

import logging
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import List

from tavily import TavilyClient
from config.settings import settings
from truebrief.collector.base import SourceLayer
from truebrief.collector.query_builder import SearchQuery
from truebrief.models.article import RawArticle, ArticleSource

logger = logging.getLogger(__name__)

class TavilyLayer(SourceLayer):
    """
    Tavily Search API Layer.
    Fills gaps that curated RSS feeds don't cover.
    """

    def __init__(self) -> None:
        api_key = settings.TAVILY_API_KEY
        if not api_key:
            logger.warning("TAVILY_API_KEY not found in settings. Tavily search will be disabled.")
            self._client = None
        else:
            self._client = TavilyClient(api_key=api_key)

    @property
    def name(self) -> str:
        return "tavily"

    def search(self, query: SearchQuery) -> List[RawArticle]:
        """
        Perform a search and return raw articles with text included.
        """
        if not self._client:
            return []

        logger.info(f"Tavily searching for: {query.primary_query}")
        
        try:
            # Using 'search' with topic="news" guarantees diverse, recent news coverage.
            # This solves the "information spread" problem directly via the search engine.
            response = self._client.search(
                query=query.primary_query,
                topic="news",
                days=7,
                max_results=5,
                include_raw_content=False, # We want the clean 150-word snippet
            )

            articles: List[RawArticle] = []
            for result in response.get("results", []):
                url = result.get("url")
                title = result.get("title")
                content = result.get("content") or result.get("raw_content") # Tavily 'content' is snippets, 'raw_content' is bigger if enabled
                
                if not url or not title:
                    continue

                pub_date: datetime | None = None
                raw_pub = result.get("published_date")
                if raw_pub:
                    try:
                        pub_date = parsedate_to_datetime(raw_pub).replace(tzinfo=None)
                    except Exception:
                        pass

                articles.append(RawArticle(
                    url=url,
                    title=title,
                    source_name=self._extract_domain(url),
                    source_type=ArticleSource.TAVILY,
                    published_at=pub_date,
                    text=content,
                ))
            
            return articles

        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return []

    def _extract_domain(self, url: str) -> str:
        """Extract a simple domain name from a URL."""
        from urllib.parse import urlparse
        try:
            netloc = urlparse(url).netloc
            return netloc.replace("www.", "")
        except:
            return "Web Source"

if __name__ == "__main__":
    # Smoke Test
    logging.basicConfig(level=logging.INFO)
    layer = TavilyLayer()
    q = SearchQuery(topic_name="Nvidia", primary_query="Nvidia Blackwell GPU production news")
    res = layer.search(q)
    print(f"Found {len(res)} results.")
    if res:
        print(f"First result: {res[0].title} (Text length: {len(res[0].text or '')})")
