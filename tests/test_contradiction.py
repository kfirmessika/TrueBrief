"""
Tests for IC4 contradiction detection (architecture §5/§8B).

Locks in the canonical benchmark cases: the Hormuz open/closed flip flags, and a
running tally (3,468 → 3,912 across days) does NOT flag (that's an IC1 update).
The detector is conservative — these tests guard against both misses and false
positives.
"""

from datetime import date, datetime

from truebrief.arbiter.contradiction import detect_contradiction

JUN17 = date(2026, 6, 17)
JUN18 = date(2026, 6, 18)
JUN10 = date(2026, 6, 10)


def test_hormuz_open_vs_closed_flags():
    reason = detect_contradiction(
        "Iran announced it has closed the Strait of Hormuz.", ["Iran", "Strait of Hormuz"], JUN17, "state_change",
        "US CENTCOM says the Strait of Hormuz remains open to traffic.", ["US", "Strait of Hormuz"], JUN17, "state_change",
    )
    assert reason is not None
    assert "open" in reason and "closed" in reason


def test_same_time_value_conflict_flags():
    reason = detect_contradiction(
        "The death toll reached 3,912 according to officials.", ["Iran"], JUN17, "development",
        "Officials put the death toll at 3,468.", ["Iran"], JUN17, "development",
    )
    assert reason is not None
    assert "3912" in reason.replace(",", "") or "3468" in reason.replace(",", "")


def test_running_tally_across_days_does_not_flag():
    # Same metric, monotonic growth over different days + tally class → IC1 update, not contradiction.
    reason = detect_contradiction(
        "The death toll rose to 3,912.", ["Iran"], JUN18, "tally",
        "The death toll rose to 3,468.", ["Iran"], JUN17, "tally",
    )
    assert reason is None


def test_numeric_conflict_requires_same_day():
    # Different numbers but a week apart → not a same-time contradiction.
    reason = detect_contradiction(
        "The death toll reached 3,912.", ["Iran"], JUN17, "development",
        "The death toll was 3,468.", ["Iran"], JUN10, "development",
    )
    assert reason is None


def test_different_entities_does_not_flag():
    reason = detect_contradiction(
        "The port of Aden is closed.", ["Yemen", "Aden"], JUN17, "state_change",
        "The Strait of Hormuz is open.", ["Iran", "Hormuz"], JUN17, "state_change",
    )
    assert reason is None


def test_identical_fact_does_not_flag():
    reason = detect_contradiction(
        "Iran closed the Strait of Hormuz.", ["Iran", "Hormuz"], JUN17, "state_change",
        "Iran closed the Strait of Hormuz.", ["Iran", "Hormuz"], JUN17, "state_change",
    )
    assert reason is None


def test_unrelated_numbers_same_metric_absent_does_not_flag():
    # No shared metric keyword → "4 drones" vs "80 billion" must not collide.
    reason = detect_contradiction(
        "The US intercepted 4 drones near Hormuz.", ["US", "Hormuz"], JUN17, "development",
        "The Pentagon requested 80 in additional funding context.", ["US", "Hormuz"], JUN17, "development",
    )
    assert reason is None


# ── Arbiter integration ───────────────────────────────────────────────────────

def test_arbiter_flags_contradiction_as_new_not_duplicate(monkeypatch):
    """With the flag on, a contradiction must resolve to NEW+flag, NOT IC3 duplicate."""
    from config.settings import settings
    from truebrief.arbiter.arbiter import Arbiter
    from truebrief.models.alpha import Alpha, DecisionType

    # Both flags on so the IC3 duplicate fast-path is also live — IC4 must win.
    monkeypatch.setattr(settings, "V3_CONTRADICTION_FLAG", True)
    monkeypatch.setattr(settings, "V3_ENTITY_DEDUP", True)

    dt = datetime(2026, 6, 17)
    match = Alpha(
        alpha_text="US CENTCOM says the Strait of Hormuz remains open to traffic.",
        entities=["US", "Strait of Hormuz"], source_url="https://b.com", source_name="b.com",
        event_date=dt, event_class="state_change", embedding=[0.1] * 8,
    )
    incoming = Alpha(
        alpha_text="Iran announced it has closed the Strait of Hormuz.",
        entities=["Iran", "Strait of Hormuz"], source_url="https://a.com", source_name="a.com",
        event_date=dt, event_class="state_change", embedding=[0.1] * 8,
    )

    class _LLM:
        def embed(self, text):
            return [0.1] * 8

    class _Store:
        def __init__(self):
            self.llm = _LLM()

        def find_similar(self, embedding, topic_id, limit, threshold):
            return [(match, 0.62)]  # mid-similarity: would be IC3-DUPLICATE without IC4

    arb = Arbiter(vector_store=_Store(), judge=object())
    decision = arb.judge_alpha(incoming, topic_id="t1")

    assert decision.decision == DecisionType.NEW
    assert decision.alpha.contradicts_id == match.id
    assert "open" in (decision.alpha.contradiction_note or "")
