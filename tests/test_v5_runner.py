"""
Tests for the V5 pipeline runner (pipeline/v5_runner.py) — Gemini Search collector ->
Arbiter -> stored facts -> brief. All components mocked; no network, no real DB writes.
"""
from __future__ import annotations

from datetime import datetime

from truebrief.models.alpha import Alpha, AlphaDecision, DecisionType
from truebrief.pipeline.v5_runner import GeminiSearchRunner


def make_alpha(text: str) -> Alpha:
    return Alpha(
        alpha_text=text,
        entities=["Test"],
        source_url="https://example.com/a",
        source_name="Example",
        event_date=datetime(2026, 7, 22),
    )


class FakeCollector:
    def __init__(self, alphas):
        self._alphas = alphas
        self.calls = []

    def collect(self, topic_name, last_run_date=None, topic_id=None):
        self.calls.append((topic_name, last_run_date, topic_id))
        return self._alphas


class FakeArbiter:
    def __init__(self, decisions):
        self._decisions = decisions
        self.calls = []

    def judge_alphas(self, alphas, topic_id=None):
        self.calls.append((alphas, topic_id))
        return self._decisions


class FakeVectorStore:
    def __init__(self):
        self.saved = []

    def add_fact(self, alpha):
        self.saved.append(alpha)
        return alpha


class FakeBriefer:
    def __init__(self, text="BRIEF TEXT"):
        self._text = text
        self.calls = []

    def generate(self, decisions, topic_name, situation=None):
        self.calls.append((decisions, topic_name))
        return self._text


def _make_runner(alphas, decisions, brief_text="BRIEF TEXT"):
    runner = GeminiSearchRunner.__new__(GeminiSearchRunner)  # skip __init__'s real construction
    runner.collector = FakeCollector(alphas)
    runner.arbiter = FakeArbiter(decisions)
    runner.vector_store = FakeVectorStore()
    runner.briefer = FakeBriefer(brief_text)
    runner.last_run_stats = {}
    return runner


class TestGeminiSearchRunner:
    def test_new_and_update_facts_get_saved_duplicate_does_not(self):
        a1, a2, a3 = make_alpha("Fact one."), make_alpha("Fact two."), make_alpha("Fact three.")
        decisions = [
            AlphaDecision(alpha=a1, decision=DecisionType.NEW),
            AlphaDecision(alpha=a2, decision=DecisionType.UPDATE, delta="what changed"),
            AlphaDecision(alpha=a3, decision=DecisionType.DUPLICATE),
        ]
        runner = _make_runner([a1, a2, a3], decisions)

        brief = runner.run("Test Topic", topic_id="t1")

        assert brief == "BRIEF TEXT"
        assert runner.vector_store.saved == [a1, a2]  # NEW + UPDATE only, not the duplicate
        assert runner.last_run_stats == {
            "alphas_extracted": 3, "decisions_new": 1, "decisions_update": 1, "decisions_duplicate": 1,
        }

    def test_no_alphas_returns_empty_brief_without_judging(self):
        runner = _make_runner([], decisions=[])
        brief = runner.run("Quiet Topic", topic_id="t1")
        assert brief == ""
        assert runner.arbiter.calls == []  # never judges an empty candidate set

    def test_all_duplicates_still_calls_briefer_which_returns_empty(self):
        """Briefer.generate already returns '' when nothing is NEW/UPDATE — runner
        doesn't need its own separate check, it trusts the existing contract."""
        a1 = make_alpha("Already known fact.")
        decisions = [AlphaDecision(alpha=a1, decision=DecisionType.DUPLICATE)]
        runner = _make_runner([a1], decisions, brief_text="")

        brief = runner.run("Test Topic", topic_id="t1")

        assert brief == ""
        assert runner.vector_store.saved == []

    def test_save_failure_does_not_crash_the_run(self):
        a1 = make_alpha("Fact.")
        decisions = [AlphaDecision(alpha=a1, decision=DecisionType.NEW)]
        runner = _make_runner([a1], decisions)

        def _raise(alpha):
            raise RuntimeError("DB down")

        runner.vector_store.add_fact = _raise

        brief = runner.run("Test Topic", topic_id="t1")  # must not raise
        assert brief == "BRIEF TEXT"

    def test_collector_receives_topic_and_id(self):
        runner = _make_runner([], decisions=[])
        runner.run("My Topic", topic_id="abc-123")
        assert runner.collector.calls == [("My Topic", None, "abc-123")]
