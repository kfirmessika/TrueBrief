"""
Tests for the snippet fallback (completeness fix).

When full-text extraction fails (paywall / 403 / bot wall), the article should
fall back to its feed snippet instead of being dropped with zero facts.
"""

from datetime import datetime

from truebrief.collector.extractor import ArticleExtractor
from truebrief.models.article import ArticleSource, RawArticle


def _article(text=None, snippet=None):
    return RawArticle(
        url="https://www.nytimes.com/2026/06/20/world/iran.html",
        title="U.S. and Iranian officials to meet in Switzerland",
        source_name="nytimes.com",
        source_type=ArticleSource.RSS,
        published_at=datetime(2026, 6, 20),
        text=text,
        snippet=snippet,
    )


def test_fallback_uses_snippet_when_no_text():
    ex = ArticleExtractor()
    art = ex._with_snippet_fallback(_article(text=None, snippet="Talks set for Sunday in Geneva, mediated by Pakistan and Qatar."))
    assert art.text == "Talks set for Sunday in Geneva, mediated by Pakistan and Qatar."


def test_fallback_does_not_override_existing_text():
    ex = ArticleExtractor()
    art = ex._with_snippet_fallback(_article(text="full body", snippet="snippet"))
    assert art.text == "full body"


def test_fallback_noop_when_no_snippet():
    ex = ArticleExtractor()
    art = ex._with_snippet_fallback(_article(text=None, snippet=None))
    assert art.text is None


def test_fallback_ignores_blank_snippet():
    ex = ArticleExtractor()
    art = ex._with_snippet_fallback(_article(text=None, snippet="   "))
    assert art.text is None
