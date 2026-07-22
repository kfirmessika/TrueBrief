"""
Regression test for the source_domain bug found 2026-07-22 during the V5 collector's
first live smoke test: add_fact() always derived source_domain from source_url via
extract_domain(), which is correct for V4 collectors' plain article URLs but wrong for
V5's Gemini Search collector, whose source_url is Google's grounding-redirect wrapper
(vertexaisearch.cloud.google.com) — every fact showed the SAME redirect host instead of
the real outlet (al-monitor.com, middleeasteye.net, etc.), which would have made every
source chip in the UI look identical/broken.
"""
from __future__ import annotations

from truebrief.ledger.vector_store import _resolve_source_domain
from truebrief.models.alpha import Alpha


def make_alpha(source_url: str, source_name: str) -> Alpha:
    return Alpha(alpha_text="x", entities=[], source_url=source_url, source_name=source_name)


class TestResolveSourceDomain:
    def test_gemini_grounding_redirect_uses_source_name(self):
        a = make_alpha(
            "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE...",
            "al-monitor.com",
        )
        assert _resolve_source_domain(a) == "al-monitor.com"

    def test_normal_v4_url_behavior_is_unchanged(self):
        """V4 collectors' own domain extraction can differ subtly from the ledger's
        extract_domain() — must NOT switch to source_name for non-Gemini URLs, or the
        still-referenced Phase 4 A/B benchmark (V4's PipelineRunner) would silently
        change behavior."""
        a = make_alpha("https://feeds.bloomberg.com/markets/news", "feeds.bloomberg.com")
        assert _resolve_source_domain(a) == "bloomberg.com"  # from extract_domain(), stripped

    def test_gemini_url_with_empty_source_name_falls_back_to_extract_domain(self):
        a = make_alpha("https://vertexaisearch.cloud.google.com/grounding-api-redirect/x", "")
        # Falls back rather than returning an empty/broken domain.
        assert _resolve_source_domain(a) == "vertexaisearch.cloud.google.com"

    def test_empty_source_url_returns_unknown(self):
        a = make_alpha("", "")
        assert _resolve_source_domain(a) == "unknown"
