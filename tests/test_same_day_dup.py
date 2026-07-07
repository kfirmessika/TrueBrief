"""
Tests for the arbiter's same-day near-identical fast-path (Step 3c) and the
harvester's meta-sentence guard — both added after the 2026-07-06 accumulated
validation found duplicate and garbage facts stored in production.

All tests are pure-Python — no LLM, no Supabase, no network.
"""
from __future__ import annotations

from datetime import datetime

from truebrief.arbiter.arbiter import Arbiter, _digit_runs
from truebrief.harvester.harvester import Harvester
from truebrief.models.alpha import Alpha, DecisionType


def make_alpha(text: str, day: int = 6) -> Alpha:
    return Alpha(
        alpha_text=text,
        entities=["Ali Khamenei"],
        source_url="https://a.com/x",
        source_name="Test",
        event_date=datetime(2026, 7, day),
        topic_id="t1",
        embedding=[0.1] * 8,  # pre-set so _ensure_embedding is a no-op
    )


class FakeJudge:
    """Records whether the Judge LLM was consulted."""

    def __init__(self):
        self.calls = 0

    def call(self, alpha, matches):
        self.calls += 1
        return (DecisionType.NEW, None)

    def call_batch(self, cases):
        self.calls += len(cases)
        return [(DecisionType.NEW, None) for _ in cases]


class FakeVectorStore:
    class _LLM:
        def embed(self, text):
            return [0.1] * 8

    def __init__(self, matches):
        self._matches = matches
        self.llm = self._LLM()

    def find_similar(self, embedding, topic_id, limit, threshold):
        return self._matches


# ── Same-day near-identical fast-path ─────────────────────────────────────────

class TestSameDayDupFastPath:
    def test_same_day_high_sim_is_duplicate_without_llm(self, monkeypatch):
        # The exact prod case: "three sons attended funeral" reworded, 0.959.
        # V3_ENTITY_DEDUP off so this exercises Step 3c, not the IC3 entity path.
        monkeypatch.setattr("truebrief.arbiter.arbiter.settings.V3_ENTITY_DEDUP", False)

        known = make_alpha("Khamenei's three sons attended a funeral ceremony.")
        vs = FakeVectorStore(matches=[(known, 0.959)])
        judge = FakeJudge()
        arbiter = Arbiter(vector_store=vs, judge=judge)

        incoming = make_alpha("Three sons of Ali Khamenei attended a funeral.")
        decision = arbiter.judge_alpha(incoming, topic_id="t1")

        assert decision.decision == DecisionType.DUPLICATE
        assert judge.calls == 0  # fast path — Judge LLM never consulted

    def test_different_numbers_defer_to_judge(self, monkeypatch):
        # Same-day tally revision must NOT be swallowed as a duplicate.
        # Isolate Step 3c: IC3 entity path off, IC4 contradiction flag off (IC4
        # would legitimately catch a toll conflict before the Judge in prod).
        monkeypatch.setattr("truebrief.arbiter.arbiter.settings.V3_ENTITY_DEDUP", False)
        monkeypatch.setattr("truebrief.arbiter.arbiter.settings.V3_CONTRADICTION_FLAG", False)

        known = make_alpha("The death toll rose to 20 in the strike.")
        vs = FakeVectorStore(matches=[(known, 0.95)])
        judge = FakeJudge()
        arbiter = Arbiter(vector_store=vs, judge=judge)

        incoming = make_alpha("The death toll rose to 25 in the strike.")
        decision = arbiter.judge_alpha(incoming, topic_id="t1")

        assert judge.calls == 1  # grey zone — Judge decides, not the fast path

    def test_different_day_defers_to_judge(self, monkeypatch):
        monkeypatch.setattr("truebrief.arbiter.arbiter.settings.V3_ENTITY_DEDUP", False)

        known = make_alpha("Funeral ceremonies for Ali Khamenei began.", day=4)
        vs = FakeVectorStore(matches=[(known, 0.95)])
        judge = FakeJudge()
        arbiter = Arbiter(vector_store=vs, judge=judge)

        incoming = make_alpha("Funeral ceremonies for Khamenei have begun.", day=5)
        decision = arbiter.judge_alpha(incoming, topic_id="t1")

        assert judge.calls == 1  # different event_date — not the fast path

    def test_below_threshold_defers_to_judge(self, monkeypatch):
        monkeypatch.setattr("truebrief.arbiter.arbiter.settings.V3_ENTITY_DEDUP", False)

        known = make_alpha("Iran issued a warning about the Strait of Hormuz.")
        vs = FakeVectorStore(matches=[(known, 0.90)])
        judge = FakeJudge()
        arbiter = Arbiter(vector_store=vs, judge=judge)

        incoming = make_alpha("Iran threatened action in the Strait of Hormuz.")
        decision = arbiter.judge_alpha(incoming, topic_id="t1")

        assert judge.calls == 1  # 0.90 < 0.93 — grey zone


def test_digit_runs():
    assert _digit_runs("toll rose to 25 on July 3") == ["25", "3"]
    assert _digit_runs("no numbers here") == []
    assert _digit_runs("11 pardons") == _digit_runs("issued 11 pardons today")
    assert _digit_runs("toll 20") != _digit_runs("toll 25")


# ── Harvester meta-sentence guard ─────────────────────────────────────────────

class TestMetaSentenceGuard:
    def test_catches_prod_garbage(self):
        # All of these were found stored as facts in production.
        garbage = [
            "There are no facts in the provided article relevant to the Iran Conflict.",
            "The provided article does not contain any facts relevant to the Israel geopolitical situation.",
            "News organizations published updates regarding a deal in the Middle East.",
            "The article contains no information regarding the geopolitical situation in Israel.",
            "The provided article text consists only of a website verification message.",
        ]
        for text in garbage:
            assert Harvester._is_meta_sentence(text), f"should catch: {text}"

    def test_passes_real_facts(self):
        real = [
            "Supreme Leader Ali Khamenei of Iran has died.",
            "The United States and Iran signed a memorandum of understanding.",
            "President Donald Trump issued 11 pardons on July 3, 2026.",
            "Over 60 structures were damaged at a military base near Esfahan.",
            "Planet Labs released satellite images of 800 locations in Iran.",
        ]
        for text in real:
            assert not Harvester._is_meta_sentence(text), f"should pass: {text}"


# ── Harvester Groq/llama response shapes (prod 2026-07-06) ───────────────────

class _FakeLLM:
    def __init__(self, response):
        self._response = response

    def call(self, **kwargs):
        return self._response


class TestHarvesterDictShapes:
    def _extract(self, response_json: str):
        from truebrief.models.article import RawArticle, ArticleSource
        h = Harvester(llm_client=_FakeLLM(response_json))
        art = RawArticle(
            url="https://a.com/x", title="t", source_name="Test",
            source_type=ArticleSource.RSS, text="some article text",
            published_at=datetime(2026, 7, 6),
        )
        return h.extract(art, topic_context="iran war")

    def test_error_dict_means_no_facts(self):
        out = self._extract('{"error": "No facts relevant to the topic were found."}')
        assert out == []

    def test_single_bare_fact_object_is_wrapped(self):
        out = self._extract(
            '{"alpha_text": "Iran warned oil tankers in the Strait of Hormuz.",'
            ' "entities": ["Iran"], "event_date": "2026-07-06", "confidence": 0.9}'
        )
        assert len(out) == 1
        assert "Hormuz" in out[0].alpha_text

    def test_wrapped_facts_list_still_works(self):
        out = self._extract(
            '{"facts": [{"alpha_text": "Iran closed the Strait of Hormuz.",'
            ' "entities": ["Iran"], "event_date": "2026-07-06", "confidence": 0.9}]}'
        )
        assert len(out) == 1
