"""
Article Extractor - collector/extractor.py

Fetches and extracts clean text from raw URLs using trafilatura.
Includes URL-based caching and bot detection.
"""

from __future__ import annotations

import hashlib
import logging

import httpx
import trafilatura
from truebrief.models.article import RawArticle

logger = logging.getLogger(__name__)

class ArticleExtractor:
    """
    Extracts clean article text from URLs.
    Used primarily for RSS links.
    """

    def __init__(self) -> None:
        # Simple in-memory cache for the prototype.
        # Phase 2 will move this to Redis.
        self._url_cache: set[str] = set()

    def _get_url_hash(self, url: str) -> str:
        """Create a deterministic hash of the URL for caching."""
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    def _check_bot_detection(self, html: str) -> bool:
        """Check if the page is a bot-protection challenge."""
        html_lower = html.lower()
        challenges = [
            "attention required!",
            "cloudflare",
            "please verify you are a human",
            "are you a robot?",
            "px-captcha",
            "datadome"
        ]
        return any(challenge in html_lower for challenge in challenges)

    def extract(self, article: RawArticle) -> RawArticle:
        """
        Fetch HTML and extract text for a given RawArticle.
        Modifies the article in-place and returns it.
        Skips if already cached or if text is already present.
        """
        if article.text:
            return article  # Already has text (e.g., from Tavily)

        url_hash = self._get_url_hash(article.url)
        if url_hash in self._url_cache:
            logger.info(f"Skipping cached URL: {article.url}")
            return article

        logger.info(f"Extracting text from: {article.url}")
        
        try:
            # We use httpx with browser-like headers to avoid basic blocks
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
            
            with httpx.Client(timeout=15.0, headers=headers, follow_redirects=True) as client:
                response = client.get(article.url)
                response.raise_for_status()
                html = response.text

            if self._check_bot_detection(html):
                logger.warning(f"Bot detection triggered for: {article.url}")
                self._url_cache.add(url_hash) # Cache to avoid retrying blocked sites
                return self._with_jina_or_snippet(article)

            text = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                no_fallback=False
            )

            if text:
                article.text = text
            else:
                logger.warning(f"Trafilatura failed to extract text from: {article.url}")
                self._with_jina_or_snippet(article)

            self._url_cache.add(url_hash)
            return article

        except Exception as e:
            logger.error(f"Failed to fetch {article.url}: {e}")
            self._url_cache.add(url_hash) # Prevent retrying broken links
            return self._with_jina_or_snippet(article)

    # A snippet shorter than this is a bare headline/link, not a real summary —
    # feeding it to the harvester invites hallucination, so we'd rather drop the
    # article. Real RSS summaries (BBC, Guardian, etc.) comfortably clear this.
    _MIN_SNIPPET_CHARS = 120

    def _with_jina_or_snippet(self, article: RawArticle) -> RawArticle:
        """Tier-2/3 fallback chain for failed extraction:
        Jina Reader (free server-side render, bypasses soft paywalls + bot walls)
        → substantial snippet → drop."""
        from config.settings import settings  # lazy: config/ sits outside src/ import root
        if settings.V3_JINA_READER:
            jina_text = self._try_jina_reader(article.url)
            if jina_text:
                article.text = jina_text
                return article
        return self._with_snippet_fallback(article)

    # Jina Reader: articles shorter than this (e.g. paywall stubs, error pages) are
    # rejected so we don't hallucinate from "Subscribe to read more" body text.
    _MIN_JINA_CHARS = 300

    def _try_jina_reader(self, url: str) -> str | None:
        """Fetch via https://r.jina.ai/<url> — Jina renders the page server-side
        and returns clean plain text/markdown. Free, no API key, rate-limited gently
        at low volume. Returns None on failure or when the returned body is too thin."""
        jina_url = f"https://r.jina.ai/{url}"
        try:
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "text/plain, text/markdown, */*",
                # Ask Jina to skip nav/footer boilerplate
                "X-No-Cache": "true",
            }
            with httpx.Client(timeout=20.0, headers=headers, follow_redirects=True) as client:
                resp = client.get(jina_url)
                resp.raise_for_status()
                body = resp.text.strip()
            if len(body) >= self._MIN_JINA_CHARS:
                logger.info(f"Jina Reader: recovered {len(body)} chars for {url}")
                return body
            logger.info(f"Jina Reader: stub response ({len(body)} chars) — not using: {url}")
            return None
        except Exception as e:
            logger.info(f"Jina Reader failed for {url}: {e}")
            return None

    def _with_snippet_fallback(self, article: RawArticle) -> RawArticle:
        """When full-text extraction fails, fall back to the feed snippet so
        paywalled / bot-walled sources (NYT, WSJ) still yield headline facts —
        but ONLY when the snippet is substantial enough to be grounded. A bare
        link-only snippet (Google News) is dropped rather than risk a fabricated fact."""
        if not article.text and article.snippet:
            s = article.snippet.strip()
            if len(s) >= self._MIN_SNIPPET_CHARS:
                logger.info(f"Using feed snippet fallback for: {article.url}")
                article.text = s
            else:
                logger.info(f"Snippet too thin ({len(s)} chars) — not harvesting: {article.url}")
        return article

if __name__ == "__main__":
    from datetime import datetime
    from truebrief.models.article import ArticleSource
    
    logging.basicConfig(level=logging.INFO)
    extractor = ArticleExtractor()
    
    test_article = RawArticle(
        url="https://arstechnica.com/information-technology/2024/04/the-ai-hype-bubble-is-getting-too-big-for-its-britches/",
        title="Test Ars Technica",
        source_name="arstechnica.com",
        source_type=ArticleSource.RSS,
        published_at=datetime.now(),
        text=None
    )
    
    result = extractor.extract(test_article)
    if result.text:
        print(f"Extracted {len(result.text)} characters.")
        print(f"Preview: {result.text[:200]}...")
    else:
        print("Extraction failed.")
