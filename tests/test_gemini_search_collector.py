"""
Tests for the V5 Gemini Search collector (collector/gemini_search_collector.py).

The citation-marker insertion and source-legend logic are pure Python — tested directly
against fake objects shaped like the real google.genai grounding types (verified live
2026-07-22: segment.start_index/end_index are exact string offsets into response.text,
text[start:end] == segment.text). The JSON-parsing/Alpha-construction logic is tested
with a fake LLMClient — no network, no real API calls.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from truebrief.collector.gemini_search_collector import (
    GeminiSearchCollector,
    _build_source_legend,
    _insert_citation_markers,
)
from truebrief.llm.client import GroundedResult

# Event date inside every collector freshness window (collect() drops non-background
# facts dated well before the reporting window; last_run_date=None → 7-day window).
_RECENT = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")


def make_support(start, end, text, chunk_indices):
    return SimpleNamespace(
        segment=SimpleNamespace(start_index=start, end_index=end, text=text),
        grounding_chunk_indices=chunk_indices,
    )


def make_chunk(uri, title):
    return SimpleNamespace(web=SimpleNamespace(uri=uri, title=title))


# ── Citation marker insertion ──────────────────────────────────────────────────

class TestInsertCitationMarkers:
    def test_single_marker_inserted_at_end_index(self):
        text = "Iran proposed a ceasefire."
        supports = [make_support(0, len(text), text, [0])]
        result = _insert_citation_markers(text, supports)
        assert result == text + "[0]"

    def test_multiple_markers_do_not_shift_each_other(self):
        text = "First fact. Second fact."
        supports = [
            make_support(0, 11, "First fact.", [0]),
            make_support(12, 23, "Second fact", [1, 2]),
        ]
        result = _insert_citation_markers(text, supports)
        # Process order is reverse-by-end_index, so earlier insertions never shift
        # offsets of segments not yet processed.
        assert result == "First fact.[0] Second fact[1,2]."

    def test_support_with_no_chunk_indices_is_skipped(self):
        text = "Unsupported claim."
        supports = [make_support(0, len(text), text, [])]
        result = _insert_citation_markers(text, supports)
        assert result == text  # no marker inserted

    def test_empty_supports_returns_text_unchanged(self):
        assert _insert_citation_markers("plain text", []) == "plain text"


# ── Source legend ────────────────────────────────────────────────────────────

class TestBuildSourceLegend:
    def test_builds_legend_and_index_lists_from_real_chunks(self):
        chunks = [
            make_chunk("https://reuters.com/a", "Reuters"),
            make_chunk("https://apnews.com/b", "AP News"),
        ]
        legend, urls, names = _build_source_legend(chunks)
        assert "[0] Reuters" in legend
        assert "[1] AP News" in legend
        assert urls == ["https://reuters.com/a", "https://apnews.com/b"]
        assert names == ["Reuters", "AP News"]

    def test_no_chunks_returns_placeholder_legend(self):
        legend, urls, names = _build_source_legend([])
        assert legend == "(no sources)"
        assert urls == []
        assert names == []


# ── Fact parsing / Alpha construction ────────────────────────────────────────

class FakeLLMClient:
    """Records calls; returns pre-set grounded result + extract JSON.

    Mirrors the LLMClient named-stage API the collector actually uses
    (collector_search / extract_facts) — provider selection + key resolution +
    prompt-splitting all live inside the real methods and are tested separately
    (tests/test_provider_switch.py).
    """

    def __init__(self, grounded: GroundedResult, extract_json: str):
        self._grounded = grounded
        self._extract_json = extract_json
        self.grounding_calls = []
        self.extract_calls = []

    def collector_search(self, topic_name, last_run_str="", today_str="",
                         known_facts=None, system_prompt=None):
        self.grounding_calls.append(
            dict(topic_name=topic_name, last_run_str=last_run_str,
                 today_str=today_str, known_facts=known_facts, system_prompt=system_prompt)
        )
        return self._grounded

    def extract_facts(self, cited_text, source_legend, topic_name, today, news_window_start=""):
        self.extract_calls.append(
            dict(cited_text=cited_text, source_legend=source_legend,
                 topic_name=topic_name, today=today, news_window_start=news_window_start)
        )
        return self._extract_json


class TestCollectEndToEnd:
    def test_valid_facts_with_citation_get_real_source_url(self):
        grounded = GroundedResult(
            text="Iran proposed a ceasefire.",
            chunks=[make_chunk("https://reuters.com/world/mideast/iran-proposes-ceasefire-2026-07-22/", "Reuters")],
            supports=[make_support(0, 26, "Iran proposed a ceasefire.", [0])],
        )
        extract_json = (
            '[{"alpha_text": "Iran proposed a ceasefire.", "entities": ["Iran"], '
            '"event_date": "2026-07-22", "date_basis": "explicit", "is_background": false, '
            '"context": "", "confidence": 0.9, "importance": 0.8, '
            '"event_class": "development", "citation_indices": [0]}]'
        )
        llm = FakeLLMClient(grounded, extract_json)
        collector = GeminiSearchCollector(llm_client=llm)

        alphas = collector.collect("Iran War", last_run_date=datetime(2026, 7, 20), topic_id="t1")

        assert len(alphas) == 1
        a = alphas[0]
        assert a.alpha_text == "Iran proposed a ceasefire."
        assert a.source_url == "https://reuters.com/world/mideast/iran-proposes-ceasefire-2026-07-22/"
        assert a.source_name == "Reuters"
        assert a.event_class == "development"
        assert a.topic_id == "t1"
        assert llm.grounding_calls[0]["topic_name"] == "Iran War"
        assert llm.grounding_calls[0]["system_prompt"]  # GEMINI_SEARCH_SYSTEM passed through
        assert llm.extract_calls[0]["topic_name"] == "Iran War"

    def test_invalid_citation_index_drops_fact_instead_of_storing_without_evidence(self):
        grounded = GroundedResult(text="Some fact.", chunks=[], supports=[])
        extract_json = (
            '[{"alpha_text": "Some fact.", "entities": [], "event_date": "' + _RECENT + '", '
            '"date_basis": "inferred", "is_background": false, "context": "", '
            '"confidence": 0.9, "importance": 0.5, "event_class": "development", '
            '"citation_indices": [5]}]'  # index 5 doesn't exist — 0 real chunks
        )
        llm = FakeLLMClient(grounded, extract_json)
        collector = GeminiSearchCollector(llm_client=llm)

        alphas = collector.collect("Iran War", last_run_date=None)

        assert alphas == []  # evidence is mandatory; never fabricate or store sourceless facts

    def test_fact_below_confidence_floor_is_dropped(self):
        grounded = GroundedResult(
            text="x", chunks=[make_chunk("https://reuters.com/a", "Reuters")], supports=[]
        )
        extract_json = (
            '[{"alpha_text": "Low confidence fact.", "entities": [], '
            '"event_date": "' + _RECENT + '", "confidence": 0.3, "citation_indices": []}]'
        )
        llm = FakeLLMClient(grounded, extract_json)
        alphas = GeminiSearchCollector(llm_client=llm).collect("Topic", last_run_date=None)
        assert alphas == []

    def test_fact_without_event_date_is_dropped(self):
        grounded = GroundedResult(text="x", chunks=[], supports=[])
        extract_json = (
            '[{"alpha_text": "Undated fact.", "entities": [], "confidence": 0.9, '
            '"citation_indices": []}]'
        )
        llm = FakeLLMClient(grounded, extract_json)
        alphas = GeminiSearchCollector(llm_client=llm).collect("Topic", last_run_date=None)
        assert alphas == []

    def test_empty_grounded_response_short_circuits_without_extract_call(self):
        grounded = GroundedResult(text="", chunks=[], supports=[])
        llm = FakeLLMClient(grounded, extract_json="[]")
        alphas = GeminiSearchCollector(llm_client=llm).collect("Quiet Topic", last_run_date=None)
        assert alphas == []
        assert llm.extract_calls == []  # never wastes a call extracting nothing

    def test_malformed_json_returns_empty_list_not_an_exception(self):
        grounded = GroundedResult(text="some prose", chunks=[], supports=[])
        llm = FakeLLMClient(grounded, extract_json="not valid json{{{")
        alphas = GeminiSearchCollector(llm_client=llm).collect("Topic", last_run_date=None)
        assert alphas == []

    def test_no_facts_error_dict_returns_empty_list(self):
        grounded = GroundedResult(text="some prose", chunks=[], supports=[])
        llm = FakeLLMClient(grounded, extract_json='{"error": "No facts relevant to topic."}')
        alphas = GeminiSearchCollector(llm_client=llm).collect("Topic", last_run_date=None)
        assert alphas == []

    def test_bare_single_fact_object_is_wrapped(self):
        """Matches harvester.py's tolerance for a bare dict instead of a list."""
        grounded = GroundedResult(
            text="x", chunks=[make_chunk("https://reuters.com/a", "Reuters")], supports=[]
        )
        extract_json = (
            '{"alpha_text": "Bare fact.", "entities": [], "event_date": "' + _RECENT + '", '
            '"confidence": 0.9, "citation_indices": [0]}'
        )
        llm = FakeLLMClient(grounded, extract_json)
        alphas = GeminiSearchCollector(llm_client=llm).collect("Topic", last_run_date=None)
        assert len(alphas) == 1
        assert alphas[0].alpha_text == "Bare fact."

    def test_stale_fact_dropped_recent_background_kept_ancient_background_dropped(self):
        """Linkup/Brave "latest news" prose smuggles old items in. Non-background
        before the window → dropped (3-day grace). Background within ~30 days →
        kept (frames a fresh fact). Months-old "background" → dropped (it's the
        same stale context re-surfacing every scan)."""
        import json as _json
        art = "https://reuters.com/world/x-2026-08/"
        grounded = GroundedResult(text="x", chunks=[make_chunk(art, "Reuters")], supports=[])
        now = datetime.utcnow()
        old = (now - timedelta(days=120)).strftime("%Y-%m-%d")       # ancient
        recent_bg = (now - timedelta(days=10)).strftime("%Y-%m-%d")  # within 30d
        fresh = (now - timedelta(hours=6)).strftime("%Y-%m-%d")
        extract_json = _json.dumps([
            {"alpha_text": "Old event, not flagged.", "entities": [], "event_date": old,
             "is_background": False, "confidence": 0.9, "citation_indices": [0]},
            {"alpha_text": "Ancient thing flagged background.", "entities": [], "event_date": old,
             "is_background": True, "confidence": 0.9, "citation_indices": [0]},
            {"alpha_text": "Recent context.", "entities": [], "event_date": recent_bg,
             "is_background": True, "confidence": 0.9, "citation_indices": [0]},
            {"alpha_text": "Fresh thing.", "entities": [], "event_date": fresh,
             "is_background": False, "confidence": 0.9, "citation_indices": [0]},
        ])
        llm = FakeLLMClient(grounded, extract_json)
        texts = [a.alpha_text for a in GeminiSearchCollector(llm_client=llm).collect(
            "AI", last_run_date=now - timedelta(days=1))]
        assert "Old event, not flagged." not in texts
        assert "Ancient thing flagged background." not in texts
        assert "Recent context." in texts
        assert "Fresh thing." in texts

    def test_hub_url_link_dropped_fact_kept_with_attribution(self):
        """foxnews.com/category/... , washingtonpost.com/donald-trump/ etc. can't
        verify a claim — keep the fact + 'per <domain>', drop the dead link."""
        fresh = (datetime.utcnow() - timedelta(hours=6)).strftime("%Y-%m-%d")
        grounded = GroundedResult(
            text="x",
            chunks=[make_chunk("https://www.foxnews.com/category/politics/wars/war-with-iran", "Fox News")],
            supports=[],
        )
        import json as _json
        extract_json = _json.dumps([{
            "alpha_text": "Trump warned Iran against retaliation.", "entities": ["Trump"],
            "event_date": fresh, "is_background": False, "confidence": 0.9, "citation_indices": [0],
        }])
        alphas = GeminiSearchCollector(llm_client=FakeLLMClient(grounded, extract_json)).collect(
            "Iran War", last_run_date=datetime.utcnow() - timedelta(days=1))
        assert len(alphas) == 1
        assert alphas[0].source_url == ""                 # dead link dropped
        assert alphas[0].source_name                      # attribution kept

    def test_no_source_at_all_drops_the_fact(self):
        fresh = (datetime.utcnow() - timedelta(hours=6)).strftime("%Y-%m-%d")
        grounded = GroundedResult(text="Some claim.", chunks=[], supports=[])
        import json as _json
        extract_json = _json.dumps([{
            "alpha_text": "Some claim.", "entities": [], "event_date": fresh,
            "confidence": 0.9, "citation_indices": [7],  # no chunk 7 exists
        }])
        alphas = GeminiSearchCollector(llm_client=FakeLLMClient(grounded, extract_json)).collect(
            "T", last_run_date=None)
        assert alphas == []

    def test_first_run_with_no_last_run_date_passes_empty_window(self):
        grounded = GroundedResult(text="", chunks=[], supports=[])
        llm = FakeLLMClient(grounded, extract_json="[]")
        GeminiSearchCollector(llm_client=llm).collect("New Topic", last_run_date=None)
        # first-ever run → no last_run_str; collector_search / build_gemini_search_prompt
        # turn that into the "last 7 days" window (asserted directly below).
        assert llm.grounding_calls[0]["last_run_str"] == ""

    def test_build_gemini_search_prompt_first_run_uses_seven_day_window(self):
        from truebrief.llm.prompts import build_gemini_search_prompt
        assert "last 7 days" in build_gemini_search_prompt("T", "", "2026-07-22")
        assert "from 2026-07-20 to 2026-07-22" in build_gemini_search_prompt("T", "2026-07-20", "2026-07-22")
