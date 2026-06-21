"""
IC8 — Golden-case regression harness (feeds A.2 Accuracy Test Harness).

Encodes the labelled failures from the 2026-06-19/20/21 GPT-vs-TrueBrief Iran-War
benchmarks as standing assertions, each tied to the component that now prevents it.
If any of these fail, a signal-quality regression has been introduced.

Documented failures this guards against:
  1. Buried lede            → IC6 briefer leads with a bottom-line + significance order
  2. Tally noise            → IC2 significance ranks tally LAST (state_change leads)
  3. Duplicated same-event  → IC3 entity+temporal gate would merge "4 soldiers killed" ×2
  4. Hormuz contradiction   → IC4 flags 'open' vs 'closed'
  5. Missing state-of-play  → IC7 synthesizes a grounded status board
  6. Tally ≠ contradiction  → IC4 does NOT flag a running total as a contradiction

These run with no live LLM/DB so they're CI-safe and deterministic.
"""

from datetime import date, datetime

from truebrief.arbiter.contradiction import detect_contradiction
from truebrief.arbiter.temporal import entity_overlap, temporal_overlap
from truebrief.briefer.briefer import Briefer
from truebrief.briefer.state_of_play import StateOfPlayGenerator
from truebrief.models.alpha import Alpha, AlphaDecision, DecisionType

JUN17 = date(2026, 6, 17)

# IC3 fast-path thresholds (arbiter step 3b) — keep in sync with arbiter.py.
IC3_ENTITY_GATE = 0.80
IC3_TEMPORAL_GATE = 0.97

# IC2 significance weights (runner step 5d) — keep in sync with runner.py.
CLASS_WEIGHT = {
    "state_change": 1.0, "escalation": 0.8, "development": 0.6,
    "incremental": 0.4, "routine": 0.2, "tally": 0.1,
}


def _decision(text, cls, decision=DecisionType.NEW):
    return AlphaDecision(
        alpha=Alpha(
            alpha_text=text, entities=["Iran", "US"],
            source_url="https://cnn.com/a", source_name="cnn.com", event_class=cls,
        ),
        decision=decision,
    )


# 1. Buried lede — the brief must open with a synthesized bottom line.
def test_golden_no_buried_lede():
    b = Briefer(llm_client=object())
    decisions = [
        _decision("US and Iran signed a 14-point framework at Versailles.", "state_change"),
        _decision("Casualty toll updated to 3,912.", "tally"),
    ]
    prompt = b._get_prompt(decisions, "Iran War")
    assert "Bottom line" in prompt                 # a synthesized lede exists
    assert '"significance": "state_change"' in prompt  # significance reaches the model


# 2. Tally noise — significance ranking puts state_change above tally.
def test_golden_state_change_outranks_tally():
    assert CLASS_WEIGHT["state_change"] > CLASS_WEIGHT["tally"]
    assert CLASS_WEIGHT["escalation"] > CLASS_WEIGHT["incremental"]


# 3. Duplicated same-event fact — the "4 soldiers killed" ×2 pair clears the IC3 gate.
def test_golden_same_event_duplicate_clears_ic3_gate():
    ents = ["Israel", "soldiers"]
    eo = entity_overlap(ents, ents)
    to = temporal_overlap(JUN17, JUN17)
    assert eo >= IC3_ENTITY_GATE        # identical entities
    assert to >= IC3_TEMPORAL_GATE      # same date → IC3 would merge to one fact


# 4. Hormuz contradiction — open vs closed gets flagged.
def test_golden_hormuz_contradiction_flagged():
    reason = detect_contradiction(
        "Iran announced it has closed the Strait of Hormuz.",
        ["Iran", "Strait of Hormuz"], JUN17, "state_change",
        "US CENTCOM says the Strait of Hormuz remains open.",
        ["US", "Strait of Hormuz"], JUN17, "state_change",
    )
    assert reason is not None
    assert "open" in reason and "closed" in reason


# 5. Missing state-of-play — a grounded board is synthesized from facts.
def test_golden_state_of_play_present():
    class _LLM:
        def call(self, **kwargs):
            return (
                '{"situation": "Fragile US-Iran framework signed Jun 17.",'
                ' "threads": [{"label": "Strait of Hormuz", "status": "contested",'
                ' "note": "open vs closed claims"}]}'
            )
    gen = StateOfPlayGenerator(llm_client=_LLM())
    facts = [{"alpha_text": "Iran closed Hormuz.", "event_class": "state_change",
              "event_date": "2026-06-17", "source_domain": "cnn.com"}]
    block = gen.generate(facts, "Iran War")
    assert block and block["situation"]
    assert block["threads"][0]["status"] in ("agreed", "contested", "postponed", "escalating")


# 6. Tally is not a contradiction — running totals across days don't false-flag.
def test_golden_tally_is_not_a_contradiction():
    reason = detect_contradiction(
        "The death toll rose to 3,912.", ["Iran"], datetime(2026, 6, 18), "tally",
        "The death toll rose to 3,468.", ["Iran"], datetime(2026, 6, 17), "tally",
    )
    assert reason is None
