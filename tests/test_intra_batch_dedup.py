"""Regression test for the intra-batch dedup fix (2026-08-13).

Root cause fixed: Arbiter.judge_alphas() judged every alpha in a batch against
ONLY the DB-stored ledger (VectorStore.find_similar()) — writes (add_fact())
happen afterward, in the caller, only once the WHOLE batch has been judged. Two
near-duplicate alphas extracted from the SAME single collect() call therefore
never saw each other: both got zero DB matches, both fast-pathed to AUTO-NEW,
both got stored as separate rows.

Live-DB audit (2026-08-13): 134 confirmed same-topic pairs at cosine 0.75-0.96,
every one inserted within 0.4-7.3 SECONDS of its partner — i.e. genuinely the
same collect()-batch, not a same-day rescan across two separate runs.

Fix: judge_alphas() now builds an in-memory `batch_pool` as it resolves each
alpha's fast path, and _prepare() folds that pool into the SAME candidate list
as the DB matches (contradiction check, raw-cosine auto-merge, IC3, same-day,
auto-merge/grey-zone thresholding all apply to it identically) — see arbiter.py
_prepare()'s `extra_pool` param and judge_alphas()'s docstring.
"""

from __future__ import annotations

from datetime import datetime

from truebrief.arbiter.arbiter import Arbiter
from truebrief.models.alpha import Alpha, DecisionType

FIXED_DATE = datetime(2026, 8, 13)

# Two vectors with cosine similarity exactly 0.85 (grey zone: 0.75 <= x < 0.97) —
# same construction as u=[1,0], v=[0.85, sqrt(1-0.85^2)], zero-padded to 8 dims.
_EMB_A = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
_EMB_A_NEAR_DUP = [0.85, 0.5268, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
# Orthogonal to both of the above (cosine 0.0) — a genuinely unrelated fact.
_EMB_UNRELATED = [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]


def _alpha(text: str, embedding: list) -> Alpha:
    return Alpha(
        alpha_text=text,
        entities=[],
        source_url="https://example.com/a",
        source_name="example.com",
        event_date=FIXED_DATE,
        embedding=embedding,
    )


class FakeJudge:
    """Records every case it's asked to judge; always returns DUPLICATE (MERGE)."""

    def __init__(self):
        self.batch_calls = 0
        self.single_calls = 0
        self.seen_cases = []  # list of (new_alpha.alpha_text, [match texts])

    def call_batch(self, cases):
        self.batch_calls += 1
        for new_alpha, matches in cases:
            self.seen_cases.append((new_alpha.alpha_text, [m.alpha_text for m, _ in matches]))
        return [(DecisionType.DUPLICATE, None) for _ in cases]

    def call(self, new_alpha, matches):
        self.single_calls += 1
        self.seen_cases.append((new_alpha.alpha_text, [m.alpha_text for m, _ in matches]))
        return (DecisionType.DUPLICATE, None)


class EmptyLedger:
    """Simulates a fresh topic / first-ever scan: the DB has nothing yet, for any query."""

    class _LLM:
        def embed(self, text):
            raise AssertionError("embedding should already be pre-set on test alphas")

    def __init__(self):
        self.llm = self._LLM()

    def find_similar(self, embedding, topic_id, limit, threshold):
        return []  # nothing stored yet — exactly the same-batch-first-scan scenario


def _arbiter(monkeypatch, batch_judge: bool):
    from config.settings import settings
    monkeypatch.setattr(settings, "V3_BATCH_JUDGE", batch_judge)
    monkeypatch.setattr(settings, "V3_ENTITY_DEDUP", False)
    monkeypatch.setattr(settings, "V3_CONTRADICTION_FLAG", False)
    monkeypatch.setattr(settings, "V3_TALLY_COLLAPSE", False)
    fake_judge = FakeJudge()
    arbiter = Arbiter(vector_store=EmptyLedger(), judge=fake_judge)
    return arbiter, fake_judge


def test_same_batch_near_duplicate_is_caught_via_judge_llm(monkeypatch):
    """The bug, reproduced: two near-dup alphas from one collect() call, DB empty.

    Before the fix: both hit "zero ledger matches" independently -> both AUTO-NEW,
    both stored as separate rows (the exact live pattern: 134 pairs, 0.4-7.3s apart).
    After the fix: the second one sees the first (already fast-pathed NEW) via the
    in-batch pool, lands in the grey zone, and gets a real Judge LLM verdict instead
    of silently duplicating.
    """
    arbiter, fake_judge = _arbiter(monkeypatch, batch_judge=True)

    a1 = _alpha("CENTCOM boarded two merchant ships in the Strait of Hormuz.", _EMB_A)
    a2 = _alpha("CENTCOM disabled two merchant ships in the Strait of Hormuz.", _EMB_A_NEAR_DUP)

    out = arbiter.judge_alphas([a1, a2], topic_id="t1")

    assert len(out) == 2
    # First one: nothing before it in the batch, nothing in the DB -> fast-path NEW.
    assert out[0].decision == DecisionType.NEW
    # Second one: fast path alone still finds zero DB matches, but the in-batch pool
    # now contains a1 -> lands in the grey zone -> the Judge LLM is actually consulted
    # (and, per FakeJudge, returns DUPLICATE) instead of silently becoming a second NEW row.
    assert out[1].decision == DecisionType.DUPLICATE
    assert fake_judge.batch_calls == 1 or fake_judge.single_calls == 1
    # The Judge LLM must have been shown a1 as a2's candidate match — proof the pool
    # actually reached the judge, not just the fast-path thresholding.
    assert len(fake_judge.seen_cases) == 1
    seen_text, seen_match_texts = fake_judge.seen_cases[0]
    assert seen_text == a2.alpha_text
    assert any("CENTCOM boarded" in m for m in seen_match_texts)


def test_same_batch_near_duplicate_caught_without_batch_judge_flag(monkeypatch):
    """Same scenario with V3_BATCH_JUDGE off (per-case Judge LLM calls) — the fix
    must not depend on the batching flag."""
    arbiter, fake_judge = _arbiter(monkeypatch, batch_judge=False)

    a1 = _alpha("CENTCOM boarded two merchant ships in the Strait of Hormuz.", _EMB_A)
    a2 = _alpha("CENTCOM disabled two merchant ships in the Strait of Hormuz.", _EMB_A_NEAR_DUP)

    out = arbiter.judge_alphas([a1, a2], topic_id="t1")

    assert out[0].decision == DecisionType.NEW
    assert out[1].decision == DecisionType.DUPLICATE
    assert fake_judge.single_calls == 1
    assert fake_judge.batch_calls == 0


def test_same_batch_unrelated_facts_both_stay_new(monkeypatch):
    """Sanity check: the pool must not create false positives. Two genuinely
    unrelated facts in the same batch (DB empty) both stay independently NEW."""
    arbiter, fake_judge = _arbiter(monkeypatch, batch_judge=True)

    a1 = _alpha("CENTCOM boarded two merchant ships in the Strait of Hormuz.", _EMB_A)
    a2 = _alpha("The Fed held interest rates steady on Wednesday.", _EMB_UNRELATED)

    out = arbiter.judge_alphas([a1, a2], topic_id="t1")

    assert [d.decision for d in out] == [DecisionType.NEW, DecisionType.NEW]
    # Zero similarity -> no candidate ever crosses LEDGER_FETCH_THRESHOLD -> the
    # Judge LLM is never consulted for either fact.
    assert fake_judge.batch_calls == 0
    assert fake_judge.single_calls == 0


def test_three_way_batch_second_and_third_both_match_first(monkeypatch):
    """A near-dup reported a 3rd time in the same batch must also collapse against
    the FIRST occurrence (not require the exact-previous item)."""
    arbiter, fake_judge = _arbiter(monkeypatch, batch_judge=True)

    a1 = _alpha("CENTCOM boarded two merchant ships in the Strait of Hormuz.", _EMB_A)
    a2 = _alpha("The Fed held interest rates steady on Wednesday.", _EMB_UNRELATED)
    a3 = _alpha("CENTCOM disabled two merchant ships in the Strait of Hormuz.", _EMB_A_NEAR_DUP)

    out = arbiter.judge_alphas([a1, a2, a3], topic_id="t1")

    assert out[0].decision == DecisionType.NEW       # a1: nothing before it
    assert out[1].decision == DecisionType.NEW       # a2: unrelated to a1
    assert out[2].decision == DecisionType.DUPLICATE  # a3: matches a1 via the batch pool
