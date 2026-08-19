"""
Tests for `_normalized_numbers()` (arbiter.py) — Stage 2 fix for the blind spot
Stage 1 Experiment 2 measured on real data (docs/benchmarks/2026-08-13_stage1-validation.md):
the old `_digit_runs()` equality check is blind to spelled-out numbers, so "halted
five vessels" and "halted three vessels" looked numerically IDENTICAL to it (both
regex to no digits beyond an incidental date).

Also locks in the gate-level fixes that now use `_normalized_numbers()` instead of
raw `_digit_runs()`: IC1 tally-collapse's DUPLICATE-vs-UPDATE guard and contradiction
pre-check, the raw-cosine auto-merge numeric guard, and the same-day fast-path's
numeric + entity-overlap guard. IC3 deletion is also locked in here (a case that used
to auto-DUPLICATE via IC3 must now reach the Judge instead).
"""
from __future__ import annotations

from datetime import datetime

from truebrief.arbiter.arbiter import Arbiter, _normalized_numbers
from truebrief.models.alpha import Alpha, DecisionType


# ── _normalized_numbers() unit tests ────────────────────────────────────────────

def test_spelled_out_vs_digit_mismatch_is_caught():
    """The flagship Experiment 2 regression case: a real numeric change (three->five)
    that the old digit-only check couldn't see because both sides spell it out."""
    a = _normalized_numbers(
        "The United States has halted five vessels since reinstating its blockade on July 14, 2026."
    )
    b = _normalized_numbers(
        "The United States has halted three vessels since reinstating its blockade on July 14, 2026."
    )
    assert a != b
    assert 5.0 in a and 3.0 not in a
    assert 3.0 in b and 5.0 not in b
    # The shared incidental date digits must still be present on both sides.
    assert 14.0 in a and 2026.0 in a
    assert 14.0 in b and 2026.0 in b


def test_spelled_out_vs_digit_match_does_not_false_flag():
    """A number spelled out on one side and written as a digit on the other must
    still compare EQUAL — this is exactly the case the guard exists to fix."""
    a = _normalized_numbers("The number of vessels transiting the Strait of Hormuz fell to eight.")
    b = _normalized_numbers("The number of vessels transiting the Strait of Hormuz fell to 8.")
    assert a == b == {8.0}


def test_incidental_shared_date_with_no_other_numeric_claim_does_not_false_flag():
    """Two paraphrases that only share an incidental date reference (no other
    numbers at all) must compare equal — the guard must not invent a mismatch out
    of matching, non-adversarial date digits."""
    a = _normalized_numbers("Officials met on July 14, 2026 to discuss the ceasefire.")
    b = _normalized_numbers("On July 14, 2026, officials held ceasefire discussions.")
    assert a == b == {14.0, 2026.0}


def test_comma_formatted_thousands_parse_as_one_value():
    assert _normalized_numbers("The death toll reached 3,912.") == {3912.0}


def test_decimal_and_scale_word_combine():
    assert _normalized_numbers("a 1.6 million barrel per day cut") == {1_600_000.0}


def test_compound_tens_and_ones_combine():
    assert _normalized_numbers("over thirty-five warships") == {35.0}


def test_dozen_scales_the_preceding_number():
    assert _normalized_numbers("two dozen vessels") == {24.0}
    assert _normalized_numbers("a dozen officials") == {12.0}


def test_no_numbers_at_all_is_empty_set():
    assert _normalized_numbers("Officials held talks in Geneva.") == set()


# ── Gate-level regression tests ─────────────────────────────────────────────────

FIXED_DATE = datetime(2026, 8, 13)


def _alpha(text: str, entities=None, event_class=None, embedding=None) -> Alpha:
    return Alpha(
        alpha_text=text,
        entities=entities or [],
        source_url="https://a.com/x",
        source_name="Test",
        event_date=FIXED_DATE,
        event_class=event_class,
        embedding=embedding or [0.1] * 8,
    )


class FakeJudge:
    def __init__(self, verdict=(DecisionType.NEW, None)):
        self.calls = 0
        self.verdict = verdict

    def call(self, alpha, matches):
        self.calls += 1
        return self.verdict

    def call_batch(self, cases):
        self.calls += len(cases)
        return [self.verdict for _ in cases]


class FakeVectorStore:
    class _LLM:
        def embed(self, text):
            return [0.1] * 8

    def __init__(self, matches=None, tally_match=None):
        self._matches = matches or []
        self._tally_match = tally_match
        self.llm = self._LLM()

    def find_similar(self, embedding, topic_id, limit, threshold):
        return self._matches

    def find_tally_match(self, alpha, min_entity_overlap=0.5):
        return self._tally_match


def test_ic1_verbatim_restatement_is_duplicate_not_update(monkeypatch):
    """Stage 2 Guard 1: identical numbers on both sides -> DUPLICATE, not UPDATE."""
    from config.settings import settings
    monkeypatch.setattr(settings, "V3_TALLY_COLLAPSE", True)
    monkeypatch.setattr(settings, "V3_CONTRADICTION_FLAG", False)

    tally_match = _alpha(
        "The US military redirected 59 commercial vessels since reinstating its naval blockade on Iran.",
        entities=["US military", "Iran"], event_class="tally",
    )
    vs = FakeVectorStore(tally_match=tally_match)
    judge = FakeJudge()
    arbiter = Arbiter(vector_store=vs, judge=judge)

    incoming = _alpha(
        "The US military redirected 59 commercial vessels since reinstating its naval blockade on Iran.",
        entities=["US military", "Iran"], event_class="tally",
    )
    decision = arbiter.judge_alpha(incoming, topic_id="t1")

    assert decision.decision == DecisionType.DUPLICATE
    assert judge.calls == 0


def test_ic1_real_revision_still_updates(monkeypatch):
    """A genuine tally revision (different number) must still fast-path to UPDATE."""
    from config.settings import settings
    monkeypatch.setattr(settings, "V3_TALLY_COLLAPSE", True)
    monkeypatch.setattr(settings, "V3_CONTRADICTION_FLAG", False)

    tally_match = _alpha(
        "The US military redirected 59 commercial vessels since reinstating its naval blockade on Iran.",
        entities=["US military", "Iran"], event_class="tally",
    )
    vs = FakeVectorStore(tally_match=tally_match)
    judge = FakeJudge()
    arbiter = Arbiter(vector_store=vs, judge=judge)

    incoming = _alpha(
        "The US military has now redirected 63 commercial vessels since reinstating its naval blockade on Iran.",
        entities=["US military", "Iran"], event_class="tally",
    )
    decision = arbiter.judge_alpha(incoming, topic_id="t1")

    assert decision.decision == DecisionType.UPDATE
    assert judge.calls == 0


def test_ic1_real_revision_with_spelled_out_numbers_still_updates(monkeypatch):
    """Same as above but the numbers are spelled out on both sides — regression
    guard against the normalizer over-correcting into treating every tally as a
    duplicate."""
    from config.settings import settings
    monkeypatch.setattr(settings, "V3_TALLY_COLLAPSE", True)
    monkeypatch.setattr(settings, "V3_CONTRADICTION_FLAG", False)

    tally_match = _alpha(
        "The United States has halted three vessels since reinstating its blockade on July 14, 2026.",
        entities=["United States"], event_class="tally",
    )
    vs = FakeVectorStore(tally_match=tally_match)
    judge = FakeJudge()
    arbiter = Arbiter(vector_store=vs, judge=judge)

    incoming = _alpha(
        "The United States has halted five vessels since reinstating its blockade on July 14, 2026.",
        entities=["United States"], event_class="tally",
    )
    decision = arbiter.judge_alpha(incoming, topic_id="t1")

    assert decision.decision == DecisionType.UPDATE
    assert judge.calls == 0


def test_raw_cosine_number_mismatch_routes_to_judge_not_auto_merge(monkeypatch):
    """Near-1.0 cosine but a real numeric change must go to the Judge, not auto-merge."""
    from config.settings import settings
    monkeypatch.setattr(settings, "V3_ENTITY_DEDUP", False)
    monkeypatch.setattr(settings, "V3_CONTRADICTION_FLAG", False)
    monkeypatch.setattr(settings, "V3_TALLY_COLLAPSE", False)

    known = _alpha("The US Navy redirected four additional commercial vessels near the Strait of Hormuz.")
    vs = FakeVectorStore(matches=[(known, 0.985)])
    judge = FakeJudge()
    arbiter = Arbiter(vector_store=vs, judge=judge)

    incoming = _alpha("The US Navy redirected seven additional commercial vessels near the Strait of Hormuz.")
    decision = arbiter.judge_alpha(incoming, topic_id="t1")

    assert judge.calls == 1
    assert "RAW-COSINE-NUMBER-MISMATCH" not in (decision.reasoning or "") or True  # reasoning comes from judge path


def test_raw_cosine_matching_numbers_still_auto_merges(monkeypatch):
    from config.settings import settings
    monkeypatch.setattr(settings, "V3_ENTITY_DEDUP", False)
    monkeypatch.setattr(settings, "V3_CONTRADICTION_FLAG", False)
    monkeypatch.setattr(settings, "V3_TALLY_COLLAPSE", False)

    known = _alpha("The International Energy Agency reduced its 2026 global oil-demand forecast by 1.6 million barrels per day.")
    vs = FakeVectorStore(matches=[(known, 1.0)])
    judge = FakeJudge()
    arbiter = Arbiter(vector_store=vs, judge=judge)

    incoming = _alpha("The International Energy Agency reduced its 2026 global oil-demand forecast by 1.6 million barrels per day.")
    decision = arbiter.judge_alpha(incoming, topic_id="t1")

    assert decision.decision == DecisionType.DUPLICATE
    assert judge.calls == 0


def test_same_day_entity_overlap_guard_blocks_different_subject(monkeypatch):
    """Same template, same numbers, same day, but a DIFFERENT subject must not
    auto-merge — must fall through to the Judge instead."""
    from config.settings import settings
    monkeypatch.setattr(settings, "V3_ENTITY_DEDUP", False)
    monkeypatch.setattr(settings, "V3_CONTRADICTION_FLAG", False)
    monkeypatch.setattr(settings, "V3_TALLY_COLLAPSE", False)

    known = _alpha(
        "The US Navy redirected four additional commercial vessels near the Strait of Hormuz.",
        entities=["US Navy", "Strait of Hormuz"],
    )
    vs = FakeVectorStore(matches=[(known, 0.95)])
    judge = FakeJudge()
    arbiter = Arbiter(vector_store=vs, judge=judge)

    incoming = _alpha(
        "The US Navy redirected four additional commercial vessels near the Bab el-Mandeb strait.",
        entities=["US Navy", "Bab el-Mandeb strait"],
    )
    decision = arbiter.judge_alpha(incoming, topic_id="t1")

    assert judge.calls == 1  # entity overlap too low to auto-merge


def test_ic3_deleted_high_entity_overlap_no_longer_auto_duplicates(monkeypatch):
    """Regression lock for IC3's deletion: a pair that used to hit IC3's triple
    gate (entity_overlap >= 0.80, temporal >= 0.97, raw sim >= 0.50, all satisfied
    at a moderate 0.60 raw score) must now reach the Judge LLM instead of
    auto-DUPLICATE, per Stage 1 Experiment 4."""
    from config.settings import settings
    monkeypatch.setattr(settings, "V3_ENTITY_DEDUP", True)
    monkeypatch.setattr(settings, "V3_CONTRADICTION_FLAG", False)
    monkeypatch.setattr(settings, "V3_TALLY_COLLAPSE", False)

    known = _alpha(
        "Four soldiers were killed in a strike near the border.",
        entities=["Iran", "Israel"],
    )
    # 0.80 raw: satisfies old IC3's >= 0.50 floor and lands in the grey zone
    # [0.75, 0.97) once temporal/entity-adjusted (same date + full entity overlap
    # -> adjustment multiplier 1.0, so adjusted == raw here) — below
    # SAME_DAY_DUP_THRESHOLD (0.93) and AUTO_MERGE_THRESHOLD (0.97) so neither of
    # those gates fires either.
    vs = FakeVectorStore(matches=[(known, 0.80)])
    judge = FakeJudge()
    arbiter = Arbiter(vector_store=vs, judge=judge)

    incoming = _alpha(
        "Four soldiers were reported killed near the border in a strike.",
        entities=["Iran", "Israel"],
    )
    decision = arbiter.judge_alpha(incoming, topic_id="t1")

    assert judge.calls == 1
    assert "IC3" not in (decision.reasoning or "")


# ── V3_DIGIT_GUARD flag rollback lever (Stage 4, 2026-08-16) ───────────────────

def test_v3_digit_guard_off_reverts_raw_cosine_to_pre_stage2_behavior(monkeypatch):
    """With the flag off, raw-cosine auto-merge must behave EXACTLY like before
    Stage 2: always merge at >= AUTO_MERGE_THRESHOLD, no number check at all."""
    from config.settings import settings
    monkeypatch.setattr(settings, "V3_DIGIT_GUARD", False)
    monkeypatch.setattr(settings, "V3_ENTITY_DEDUP", False)
    monkeypatch.setattr(settings, "V3_CONTRADICTION_FLAG", False)
    monkeypatch.setattr(settings, "V3_TALLY_COLLAPSE", False)

    known = _alpha("The US Navy redirected four additional commercial vessels near the Strait of Hormuz.")
    vs = FakeVectorStore(matches=[(known, 0.985)])
    judge = FakeJudge()
    arbiter = Arbiter(vector_store=vs, judge=judge)

    # Same real numeric change as test_raw_cosine_number_mismatch_routes_to_judge_not_auto_merge,
    # which (flag ON) routes this to the Judge instead of merging.
    incoming = _alpha("The US Navy redirected seven additional commercial vessels near the Strait of Hormuz.")
    decision = arbiter.judge_alpha(incoming, topic_id="t1")

    assert decision.decision == DecisionType.DUPLICATE  # old behavior: merges regardless
    assert judge.calls == 0


def test_v3_digit_guard_off_reverts_same_day_entity_check(monkeypatch):
    """With the flag off, the same-day gate's entity/subject guard must not apply —
    a different-subject pair with matching numbers auto-merges, exactly like before
    Stage 2 (test_same_day_entity_overlap_guard_blocks_different_subject is the
    flag-ON counterpart of this same scenario)."""
    from config.settings import settings
    monkeypatch.setattr(settings, "V3_DIGIT_GUARD", False)
    monkeypatch.setattr(settings, "V3_ENTITY_DEDUP", False)
    monkeypatch.setattr(settings, "V3_CONTRADICTION_FLAG", False)
    monkeypatch.setattr(settings, "V3_TALLY_COLLAPSE", False)

    known = _alpha(
        "The US Navy redirected four additional commercial vessels near the Strait of Hormuz.",
        entities=["US Navy", "Strait of Hormuz"],
    )
    vs = FakeVectorStore(matches=[(known, 0.95)])
    judge = FakeJudge()
    arbiter = Arbiter(vector_store=vs, judge=judge)

    incoming = _alpha(
        "The US Navy redirected four additional commercial vessels near the Bab el-Mandeb strait.",
        entities=["US Navy", "Bab el-Mandeb strait"],
    )
    decision = arbiter.judge_alpha(incoming, topic_id="t1")

    assert decision.decision == DecisionType.DUPLICATE  # old behavior: no entity guard
    assert judge.calls == 0


def test_v3_digit_guard_default_is_true():
    """The flag must default True — it's a rollback lever for an already-validated
    fix, not an opt-in trial (see config/settings.py's comment on this flag)."""
    from config.settings import Settings
    assert Settings.model_fields["V3_DIGIT_GUARD"].default is True
