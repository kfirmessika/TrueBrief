"""Tests for the V3 batch grey-zone judge (1b.1).

Covers:
  - JudgeLLM.call_batch: one LLM call parses into N ordered decisions
  - call_batch fallback to per-case .call() on count mismatch / bad output
  - Arbiter.judge_alphas: batches grey-zone cases only when V3_BATCH_JUDGE is on,
    fast-paths resolve without any LLM call, order is preserved
"""

from __future__ import annotations

from datetime import datetime

import pytest

from truebrief.arbiter.arbiter import Arbiter
from truebrief.arbiter.judge import JudgeLLM
from truebrief.models.alpha import Alpha, DecisionType

FIXED_DATE = datetime(2026, 6, 1)


def make_alpha(text: str, entities=None) -> Alpha:
    return Alpha(
        alpha_text=text,
        entities=entities or [],
        source_url="https://example.com/a",
        source_name="example.com",
        event_date=FIXED_DATE,
        embedding=[0.1] * 8,  # pre-set so _ensure_embedding is a no-op
    )


# ── Fakes ───────────────────────────────────────────────────────────────────

class QueueLLM:
    """Returns canned responses in order; records every call."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def call(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class FakeJudge:
    """Stand-in for JudgeLLM that records batch vs single dispatch."""

    def __init__(self):
        self.batch_calls = 0
        self.single_calls = 0

    def call_batch(self, cases):
        self.batch_calls += 1
        return [(DecisionType.UPDATE, "delta") for _ in cases]

    def call(self, alpha, matches):
        self.single_calls += 1
        return (DecisionType.NEW, None)


class FakeVectorStore:
    """Returns fixed matches; exposes a .llm with embed()."""

    class _LLM:
        def embed(self, text):
            return [0.1] * 8

    def __init__(self, matches):
        self._matches = matches
        self.llm = self._LLM()

    def find_similar(self, embedding, topic_id, limit, threshold):
        return self._matches


# ── JudgeLLM.call_batch ───────────────────────────────────────────────────────

def test_call_batch_parses_ordered_decisions_in_one_call():
    llm = QueueLLM([
        '[{"case": 1, "decision": "MERGE"}, '
        '{"case": 2, "decision": "UPDATE", "delta": "price changed"}, '
        '{"case": 3, "decision": "NEW"}]'
    ])
    judge = JudgeLLM(llm=llm)
    cases = [
        (make_alpha("fact A"), [(make_alpha("known A"), 0.8)]),
        (make_alpha("fact B"), [(make_alpha("known B"), 0.82)]),
        (make_alpha("fact C"), [(make_alpha("known C"), 0.79)]),
    ]
    out = judge.call_batch(cases)
    assert out == [
        (DecisionType.DUPLICATE, None),
        (DecisionType.UPDATE, "price changed"),
        (DecisionType.NEW, None),
    ]
    assert len(llm.calls) == 1  # exactly one batched call


def test_call_batch_reorders_by_case_index():
    llm = QueueLLM([
        '[{"case": 2, "decision": "NEW"}, {"case": 1, "decision": "MERGE"}]'
    ])
    judge = JudgeLLM(llm=llm)
    cases = [
        (make_alpha("fact 1"), [(make_alpha("k1"), 0.8)]),
        (make_alpha("fact 2"), [(make_alpha("k2"), 0.8)]),
    ]
    out = judge.call_batch(cases)
    assert out == [(DecisionType.DUPLICATE, None), (DecisionType.NEW, None)]


def test_call_batch_falls_back_to_per_case_on_count_mismatch():
    # Batch returns 1 object for 2 cases → distrust → fall back to single calls.
    llm = QueueLLM([
        '[{"case": 1, "decision": "MERGE"}]',  # bad: only 1 of 2
        '{"decision": "NEW"}',                  # case 1 fallback
        '{"decision": "MERGE"}',                # case 2 fallback
    ])
    judge = JudgeLLM(llm=llm)
    cases = [
        (make_alpha("fact 1"), [(make_alpha("k1"), 0.8)]),
        (make_alpha("fact 2"), [(make_alpha("k2"), 0.8)]),
    ]
    out = judge.call_batch(cases)
    assert out == [(DecisionType.NEW, None), (DecisionType.DUPLICATE, None)]
    assert len(llm.calls) == 3  # 1 failed batch + 2 fallbacks


def test_call_batch_single_case_uses_single_call():
    llm = QueueLLM(['{"decision": "NEW"}'])
    judge = JudgeLLM(llm=llm)
    out = judge.call_batch([(make_alpha("solo"), [(make_alpha("k"), 0.8)])])
    assert out == [(DecisionType.NEW, None)]


# ── Arbiter.judge_alphas routing ──────────────────────────────────────────────

def test_judge_alphas_batches_grey_zone_when_flag_on(monkeypatch):
    from config.settings import settings
    monkeypatch.setattr(settings, "V3_BATCH_JUDGE", True)
    monkeypatch.setattr(settings, "V3_ENTITY_DEDUP", False)

    # Two facts whose top match lands in the grey zone (0.75 <= score < 0.97).
    vs = FakeVectorStore(matches=[(make_alpha("known"), 0.85)])
    fake_judge = FakeJudge()
    arbiter = Arbiter(vector_store=vs, judge=fake_judge)

    out = arbiter.judge_alphas([make_alpha("fact 1"), make_alpha("fact 2")], topic_id="t1")

    assert len(out) == 2
    assert fake_judge.batch_calls == 1
    assert fake_judge.single_calls == 0
    assert all(d.decision == DecisionType.UPDATE for d in out)


def test_judge_alphas_per_case_when_flag_off(monkeypatch):
    from config.settings import settings
    monkeypatch.setattr(settings, "V3_BATCH_JUDGE", False)
    monkeypatch.setattr(settings, "V3_ENTITY_DEDUP", False)

    vs = FakeVectorStore(matches=[(make_alpha("known"), 0.85)])
    fake_judge = FakeJudge()
    arbiter = Arbiter(vector_store=vs, judge=fake_judge)

    out = arbiter.judge_alphas([make_alpha("a"), make_alpha("b")], topic_id="t1")

    assert len(out) == 2
    assert fake_judge.batch_calls == 0
    assert fake_judge.single_calls == 2


def test_judge_alphas_fastpaths_need_no_llm(monkeypatch):
    from config.settings import settings
    monkeypatch.setattr(settings, "V3_BATCH_JUDGE", True)
    monkeypatch.setattr(settings, "V3_ENTITY_DEDUP", False)

    # Zero matches → AUTO-NEW fast path; the judge must never be called.
    vs = FakeVectorStore(matches=[])
    fake_judge = FakeJudge()
    arbiter = Arbiter(vector_store=vs, judge=fake_judge)

    out = arbiter.judge_alphas([make_alpha("x"), make_alpha("y")], topic_id="t1")

    assert [d.decision for d in out] == [DecisionType.NEW, DecisionType.NEW]
    assert fake_judge.batch_calls == 0
    assert fake_judge.single_calls == 0
