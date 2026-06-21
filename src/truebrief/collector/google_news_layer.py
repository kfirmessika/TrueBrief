"""
Google News Collector - collector/google_news_layer.py

Implements SourceLayer using Google News RSS.
Uses googlenewsdecoder to resolve obfuscated news.google.com URLs into direct article URLs.
"""

from __future__ import annotations

import logging
import re
import urllib.parse
from typing import List
import feedparser

# Use googlenewsdecoder's new_decoderv1 for reliable decoding
from googlenewsdecoder.new_decoderv1 import decode_google_news_url

from truebrief.collector.base import SourceLayer
from truebrief.collector.query_builder import SearchQuery
from truebrief.models.article import RawArticle

logger = logging.getLogger(__name__)

class GoogleNewsLayer(SourceLayer):
    """
    Fetches articles from Google News via RSS and decodes the URLs.
    """

    @property
    def name(self) -> str:
        return "google_news"

    def search(self, query: SearchQuery) -> List[RawArticle]:
        """Search Google News and return decoded raw articles."""
        
        # Build search query. We add "when:1d" to get recent news.
        search_term = query.primary_query
        
        q = urllib.parse.quote(search_term)
        url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
        
        logger.info(f"[{self.name}] Fetching RSS: {url}")
        
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            logger.error(f"[{self.name}] Failed to parse RSS feed: {e}")
            return []

        articles = []
        for entry in feed.entries[:10]:  # Limit to top 10 to avoid excessive decoding time
            title = getattr(entry, "title", "").strip()
            link = getattr(entry, "link", "").strip()
            
            if not link or not title:
                continue
                
            # Decode Google News URL
            try:
                res = decode_google_news_url(link)
                if res and res.get("status") is True and res.get("decoded_url"):
                    real_url = res["decoded_url"]
                else:
                    logger.debug(f"[{self.name}] Failed to decode URL, falling back to original: {link}")
                    real_url = link # Fallback
            except Exception as e:
                logger.debug(f"[{self.name}] Decoder error: {e}")
                real_url = link

            raw_summary = getattr(entry, "summary", "") or ""
            snippet = re.sub(r"<[^>]+>", " ", raw_summary)
            snippet = re.sub(r"\s+", " ", snippet).strip() or None

            articles.append(
                RawArticle(
                    title=title,
                    url=real_url,
                    text=None,  # Trafilatura will fetch this later in the pipeline
                    source_name="Google News",
                    source_type="rss",
                    snippet=snippet,
                )
            )

        logger.info(f"[{self.name}] Found {len(articles)} articles.")
        return articles
