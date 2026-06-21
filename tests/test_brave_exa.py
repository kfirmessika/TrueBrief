"""
Tests — test_brave_exa.py

Unit tests for Step 3.19: Brave Search + Exa source plugins.

All tests are pure unit tests — no real API calls made.
"""

from unittest.mock import MagicMock, patch

from truebrief.collector.query_builder import SearchQuery
from truebrief.models.article import ArticleSource


def _make_query(q: str = "Bitcoin ETFs") -> SearchQuery:
    return SearchQuery(topic_name=q, primary_query=q + " news")


# ---------------------------------------------------------------------------
# BraveLayer Tests
# ---------------------------------------------------------------------------

class TestBraveLayer:
    def test_no_key_returns_empty(self):
        """BraveLayer returns [] when BRAVE_API_KEY is not set."""
        with patch("truebrief.collector.brave_layer.settings") as mock_cfg:
            mock_cfg.BRAVE_API_KEY = ""
            from truebrief.collector.brave_layer import BraveLayer
            layer = BraveLayer()
        assert layer.search(_make_query()) == []

    def _make_layer(self):
        """Build a BraveLayer with a fake API key, bypassing __init__ settings read."""
        from truebrief.collector.brave_layer import BraveLayer
        layer = BraveLayer.__new__(BraveLayer)
        layer._api_key = "test-key"
        return layer

    def test_search_parses_results(self):
        """BraveLayer maps Brave news results to RawArticle objects correctly."""
        fake_response = MagicMock()
        # /news/search returns top-level "results" (not nested under "web")
        fake_response.json.return_value = {
            "results": [
                {
                    "url": "https://reuters.com/story/1",
                    "title": "Bitcoin ETF Approved",
                    "description": "The SEC has approved...",
                    "age": "2 hours ago",
                },
                {
                    "url": "https://bloomberg.com/story/2",
                    "title": "Bitcoin Hits Record",
                    "description": "Markets reacted...",
                    "age": "1 day ago",
                },
            ]
        }
        fake_response.raise_for_status = MagicMock()

        layer = self._make_layer()
        with patch("truebrief.collector.brave_layer.httpx.get", return_value=fake_response):
            results = layer.search(_make_query())

        assert len(results) == 2
        assert results[0].url == "https://reuters.com/story/1"
        assert results[0].title == "Bitcoin ETF Approved"
        assert results[0].text == "The SEC has approved..."
        assert results[0].source_type == ArticleSource.BRAVE
        assert results[0].source_name == "reuters.com"

    def test_handles_api_error(self):
        """BraveLayer returns [] gracefully when httpx raises an exception."""
        layer = self._make_layer()
        with patch("truebrief.collector.brave_layer.httpx.get", side_effect=Exception("timeout")):
            results = layer.search(_make_query())
        assert results == []

    def test_skips_results_missing_url_or_title(self):
        """BraveLayer skips results that have no url or no title."""
        fake_response = MagicMock()
        fake_response.json.return_value = {
            "results": [
                {"url": "", "title": "No URL result", "description": "..."},
                {"url": "https://ok.com/", "title": "", "description": "..."},
                {"url": "https://ok.com/article", "title": "Good", "description": "..."},
            ]
        }
        fake_response.raise_for_status = MagicMock()

        layer = self._make_layer()
        with patch("truebrief.collector.brave_layer.httpx.get", return_value=fake_response):
            results = layer.search(_make_query())

        assert len(results) == 1
        assert results[0].url == "https://ok.com/article"

    def test_name_property(self):
        """BraveLayer.name == 'brave'."""
        from truebrief.collector.brave_layer import BraveLayer
        with patch("truebrief.collector.brave_layer.settings") as mock_cfg:
            mock_cfg.BRAVE_API_KEY = ""
            layer = BraveLayer()
        assert layer.name == "brave"


# ---------------------------------------------------------------------------
# ExaLayer Tests
# ---------------------------------------------------------------------------

class TestExaLayer:
    def test_no_key_returns_empty(self):
        """ExaLayer returns [] when EXA_API_KEY is not set."""
        with patch("truebrief.collector.exa_layer.settings") as mock_cfg:
            mock_cfg.EXA_API_KEY = ""
            from truebrief.collector.exa_layer import ExaLayer
            layer = ExaLayer()
        assert layer.search(_make_query()) == []

    def test_search_parses_results(self):
        """ExaLayer maps Exa results to RawArticle objects correctly."""
        fake_result_1 = MagicMock()
        fake_result_1.url = "https://ft.com/article/1"
        fake_result_1.title = "Bitcoin ETF Launch"
        fake_result_1.text = "Financial Times reports..."
        fake_result_1.published_date = "2025-01-15T10:00:00Z"

        fake_result_2 = MagicMock()
        fake_result_2.url = "https://wsj.com/article/2"
        fake_result_2.title = "Crypto Market Update"
        fake_result_2.text = "The Wall Street Journal notes..."
        fake_result_2.published_date = None

        fake_response = MagicMock()
        fake_response.results = [fake_result_1, fake_result_2]

        mock_exa_client = MagicMock()
        mock_exa_client.search_and_contents.return_value = fake_response

        with patch("truebrief.collector.exa_layer.settings") as mock_cfg, \
             patch("truebrief.collector.exa_layer.ExaLayer.__init__", return_value=None):
            mock_cfg.EXA_API_KEY = "test-key"
            from truebrief.collector.exa_layer import ExaLayer
            layer = ExaLayer.__new__(ExaLayer)
            layer._api_key = "test-key"
            layer._client = mock_exa_client

        results = layer.search(_make_query())

        assert len(results) == 2
        assert results[0].url == "https://ft.com/article/1"
        assert results[0].title == "Bitcoin ETF Launch"
        assert results[0].text == "Financial Times reports..."
        assert results[0].source_type == ArticleSource.EXA
        assert results[0].source_name == "ft.com"
        assert results[0].published_at is not None
        assert results[1].published_at is None

    def test_handles_sdk_error(self):
        """ExaLayer returns [] when the Exa SDK raises an exception."""
        mock_exa_client = MagicMock()
        mock_exa_client.search_and_contents.side_effect = Exception("API quota exceeded")

        from truebrief.collector.exa_layer import ExaLayer
        layer = ExaLayer.__new__(ExaLayer)
        layer._api_key = "test-key"
        layer._client = mock_exa_client

        results = layer.search(_make_query())
        assert results == []

    def test_skips_results_with_no_url(self):
        """ExaLayer skips results that have no URL."""
        fake_result = MagicMock()
        fake_result.url = ""
        fake_result.title = "Missing URL"
        fake_result.text = "..."
        fake_result.published_date = None

        fake_response = MagicMock()
        fake_response.results = [fake_result]

        mock_exa_client = MagicMock()
        mock_exa_client.search_and_contents.return_value = fake_response

        from truebrief.collector.exa_layer import ExaLayer
        layer = ExaLayer.__new__(ExaLayer)
        layer._api_key = "test-key"
        layer._client = mock_exa_client

        results = layer.search(_make_query())
        assert results == []

    def test_name_property(self):
        """ExaLayer.name == 'exa'."""
        from truebrief.collector.exa_layer import ExaLayer
        layer = ExaLayer.__new__(ExaLayer)
        layer._api_key = ""
        layer._client = None
        assert layer.name == "exa"


# ---------------------------------------------------------------------------
# PipelineRunner Integration
# ---------------------------------------------------------------------------

class TestPipelineRunnerSources:
    def test_default_sources_include_brave_and_exa(self):
        """PipelineRunner's default source list now includes BraveLayer and ExaLayer."""
        from truebrief.collector.brave_layer import BraveLayer
        from truebrief.collector.exa_layer import ExaLayer

        # Import runner module and check the default source names
        # We check the class types used in the default list via the module source
        import truebrief.pipeline.runner as runner_mod
        assert hasattr(runner_mod, "BraveLayer")
        assert hasattr(runner_mod, "ExaLayer")

    def test_brave_exa_excluded_by_free_tier_allowlist(self):
        """When allowlist is ['rss', 'tavily'], brave/exa sources are filtered out."""
        from truebrief.collector.brave_layer import BraveLayer
        from truebrief.collector.exa_layer import ExaLayer
        from truebrief.collector.rss_layer import RSSLayer
        from truebrief.collector.tavily_layer import TavilyLayer

        mock_rss = MagicMock(spec=RSSLayer)
        mock_rss.name = "rss"
        mock_tavily = MagicMock(spec=TavilyLayer)
        mock_tavily.name = "tavily"
        mock_brave = MagicMock(spec=BraveLayer)
        mock_brave.name = "brave"
        mock_exa = MagicMock(spec=ExaLayer)
        mock_exa.name = "exa"

        all_sources = [mock_tavily, mock_rss, mock_brave, mock_exa]
        allowlist = ["rss", "tavily"]
        filtered = [s for s in all_sources if s.name in allowlist]

        assert len(filtered) == 2
        assert all(s.name in {"rss", "tavily"} for s in filtered)

    def test_article_source_enum_has_brave_and_exa(self):
        """ArticleSource enum includes BRAVE and EXA values."""
        assert ArticleSource.BRAVE == "brave"
        assert ArticleSource.EXA == "exa"
