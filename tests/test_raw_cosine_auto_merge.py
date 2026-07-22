"""
Regression test for the bug found 2026-07-22 on live data (see architecture_v5.md §4):
AUTO_MERGE_THRESHOLD was tested against the TEMPORALLY-ADJUSTED score, so two copies of
the identical fact with a drifted event_date (extraction noise, not a real time gap)
fell below threshold and were admitted as separate facts.

Live example this reproduces: "Twelve IDF soldiers and 23 civilians have been killed in
ballistic missile attacks since February 28." was stored twice, verbatim (raw cosine 1.0),
with event_date 24 days apart (2026-04-13 vs 2026-05-07).

All tests are pure-Python — no LLM, no Supabase, no network.
"""
from __future__ import annotations

from datetime import datetime

from truebrief.arbiter.arbiter import Arbiter, AUTO_MERGE_THRESHOLD
from truebrief.models.alpha import Alpha, DecisionType


def make_alpha(text: str, event_date: datetime) -> Alpha:
    return Alpha(
        alpha_text=text,
        entities=["IDF"],
        source_url="https://a.com/x",
        source_name="Test",
        event_date=event_date,
        topic_id="t1",
        embedding=[0.1] * 8,
    )


class FakeJudge:
    def __init__(self):
        self.calls = 0

    def call(self, alpha, matches):
        self.calls += 1
        return (DecisionType.UPDATE, "some delta")

    def call_batch(self, cases):
        self.calls += len(cases)
        return [(DecisionType.UPDATE, "some delta") for _ in cases]


class FakeVectorStore:
    class _LLM:
        def embed(self, text):
            return [0.1] * 8

    def __init__(self, matches):
        self._matches = matches
        self.llm = self._LLM()

    def find_similar(self, embedding, topic_id, limit, threshold):
        return self._matches


class TestRawCosineAutoMerge:
    def test_identical_text_with_drifted_date_still_merges(self, monkeypatch):
        """The exact live bug: verbatim duplicate, event_date 24 days apart."""
        monkeypatch.setattr("truebrief.arbiter.arbiter.settings.V3_CONTRADICTION_FLAG", False)
        monkeypatch.setattr("truebrief.arbiter.arbiter.settings.V3_ENTITY_DEDUP", False)

        text = (
            "Twelve IDF soldiers and 23 civilians have been killed in ballistic "
            "missile attacks since February 28."
        )
        known = make_alpha(text, event_date=datetime(2026, 4, 13))
        incoming = make_alpha(text, event_date=datetime(2026, 5, 7))  # 24 days later

        vs = FakeVectorStore(matches=[(known, 1.0)])  # raw cosine = 1.0 (verbatim)
        judge = FakeJudge()
        arbiter = Arbiter(vector_store=vs, judge=judge)

        decision = arbiter.judge_alpha(incoming, topic_id="t1")

        assert decision.decision == DecisionType.DUPLICATE
        assert judge.calls == 0  # never reaches the judge, which would have said UPDATE
        assert decision.matched_alpha_id == known.id

    def test_below_raw_threshold_still_uses_temporal_adjustment(self, monkeypatch):
        """Raw cosine just under the bar must NOT bypass temporal adjustment —
        this fast-path is only for near-certain (>=0.97) matches."""
        monkeypatch.setattr("truebrief.arbiter.arbiter.settings.V3_CONTRADICTION_FLAG", False)
        monkeypatch.setattr("truebrief.arbiter.arbiter.settings.V3_ENTITY_DEDUP", False)

        known = make_alpha("Some fact about troop movements.", event_date=datetime(2026, 4, 13))
        incoming = make_alpha("A related fact about troop movements.", event_date=datetime(2026, 5, 7))

        raw_score = AUTO_MERGE_THRESHOLD - 0.05
        vs = FakeVectorStore(matches=[(known, raw_score)])
        judge = FakeJudge()
        arbiter = Arbiter(vector_store=vs, judge=judge)

        decision = arbiter.judge_alpha(incoming, topic_id="t1")

        # Should NOT auto-merge via the raw-cosine fast-path; falls through to
        # temporal adjustment / grey zone / judge as before this fix.
        assert judge.calls >= 0  # may or may not reach judge depending on adjusted score,
        # the key assertion is it did NOT take the raw-cosine DUPLICATE shortcut:
        assert not (
            decision.decision == DecisionType.DUPLICATE
            and decision.reasoning
            and "Raw-cosine auto-merge" in decision.reasoning
        )
