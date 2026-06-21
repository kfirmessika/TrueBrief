"""
RSS Layer Collector Plugin - collector/rss_layer.py

Scans curated RSS feeds based on topic categories.
Primary real-time data source.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

import feedparser
import yaml
import dateparser
from config.settings import RSS_FEEDS_PATH
from truebrief.collector.base import SourceLayer
from truebrief.collector.query_builder import SearchQuery
from truebrief.models.article import RawArticle, ArticleSource

logger = logging.getLogger(__name__)

class RSSLayer(SourceLayer):
    """
    Direct RSS Scan.
    Uses categories suggested by the Query Builder to find candidate feeds.
    """

    def __init__(self) -> None:
        self._feeds_db = self._load_feeds_db()

    @property
    def name(self) -> str:
        return "rss"

    def _load_feeds_db(self) -> dict:
        """Load the full curated feed database."""
        try:
            with open(RSS_FEEDS_PATH, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed to load RSS feeds from {RSS_FEEDS_PATH}: {e}")
            return {}

    def search(self, query: SearchQuery) -> List[RawArticle]:
        """
        Poll all feeds in the matched categories.
        """
        all_articles: List[RawArticle] = []
        
        # Get unique feeds from all matched categories
        target_feeds = []
        seen_urls = set()
        
        # Category aliases: map LLM-generated names to actual config keys
        _ALIASES: dict[str, str] = {
            "middle_east": "geopolitics",
            "world": "geopolitics",
            "politics": "geopolitics",
            "international": "geopolitics",
            "business": "finance",
            "tech": "technology",
        }

        for cat in query.rss_categories:
            resolved = _ALIASES.get(cat.lower(), cat)
            feeds = self._feeds_db.get(resolved, [])
            if not feeds and resolved != cat:
                logger.info(f"RSS category '{cat}' → alias '{resolved}' found no feeds.")
            for f in feeds:
                f_url = f.get("url")
                if f_url and f_url not in seen_urls:
                    target_feeds.append(f)
                    seen_urls.add(f_url)

        if not target_feeds:
            logger.warning(
                f"No feeds found for categories {query.rss_categories} — "
                "falling back to 'geopolitics'."
            )
            for f in self._feeds_db.get("geopolitics", []):
                f_url = f.get("url")
                if f_url and f_url not in seen_urls:
                    target_feeds.append(f)
                    seen_urls.add(f_url)

        logger.info(f"Scanning {len(target_feeds)} RSS feeds for topic: {query.topic_name}")

        for feed_info in target_feeds:
            articles = self._scan_feed(feed_info)
            all_articles.extend(articles)

        return all_articles

    def _scan_feed(self, feed_info: dict) -> List[RawArticle]:
        """Poll a single RSS feed."""
        url = feed_info.get("url")
        name = feed_info.get("name", "Unknown Source")
        
        try:
            # We don't use 'seen_urls' here because the Arbiter/Ledger 
            # will handle system-wide deduplication later.
            feed = feedparser.parse(url)
            
            articles: List[RawArticle] = []
            for entry in feed.entries:
                link = entry.get("link")
                title = entry.get("title")
                
                if not link or not title:
                    continue

                # Clean link (remove tracking params if possible - Phase 2)
                
                # Parse date
                pub_date = None
                raw_date = entry.get("published") or entry.get("updated")
                if raw_date:
                    pub_date = dateparser.parse(raw_date)

                # Feed summary → snippet fallback (used if full-text fetch fails).
                raw_summary = entry.get("summary") or entry.get("description") or ""
                snippet = re.sub(r"<[^>]+>", " ", raw_summary)        # strip HTML tags
                snippet = re.sub(r"\s+", " ", snippet).strip() or None

                articles.append(RawArticle(
                    url=link,
                    title=title,
                    source_name=name,
                    source_type=ArticleSource.RSS,
                    published_at=pub_date,
                    text=None,  # RSS doesn't give full text, Extractor will handle
                    snippet=snippet,
                ))
            
            return articles

        except Exception as e:
            logger.error(f"Error scanning feed {url}: {e}")
            return []

if __name__ == "__main__":
    # Smoke Test
    logging.basicConfig(level=logging.INFO)
    layer = RSSLayer()
    q = SearchQuery(topic_name="Tech", primary_query="Tech", rss_categories=["technology"])
    res = layer.search(q)
    print(f"Found {len(res)} articles.")
    if res:
        print(f"First result: {res[0].title} from {res[0].source_name}")
