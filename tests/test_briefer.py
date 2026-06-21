"""
Tests for the IC5/IC6 briefer prompt (signal-to-noise rewrite).

These test the prompt-construction logic (`_get_prompt`) directly — no LLM call —
so they're fast and deterministic. They lock in the behaviour the 2026-06-20
benchmark exposed: no rigid WHAT'S NEW/FULL CONTEXT labels, a bottom-line lede,
significance ordering, and one-chip-per-outlet guidance.
"""

from truebrief.briefer.briefer import Briefer
from truebrief.models.alpha import Alpha, AlphaDecision, DecisionType


def _alpha(text, *, event_class=None, context=None, verified_count=0,
           source_name="cnn.com", source_url="https://cnn.com/a"):
    return Alpha(
        alpha_text=text,
        entities=["Iran", "US"],
        source_url=source_url,
        source_name=source_name,
        context=context,
        event_class=event_class,
        verified_count=verified_count,
    )


def test_prompt_drops_rigid_labels():
    """IC5: the briefer must NOT instruct the old WHAT'S NEW / FULL CONTEXT labels."""
    b = Briefer(llm_client=object())  # llm never called by _get_prompt
    d = AlphaDecision(alpha=_alpha("US and Iran signed a deal."), decision=DecisionType.NEW)
    prompt = b._get_prompt([d], "Iran War")
    assert "WHAT'S NEW:" not in prompt
    assert "FULL CONTEXT:" not in prompt
    assert "weave" in prompt.lower() or "woven" in prompt.lower()


def test_prompt_has_bottom_line_lede():
    """IC6/IC7-lite: the brief must open with a one-line bottom-line synthesis."""
    b = Briefer(llm_client=object())
    d = AlphaDecision(alpha=_alpha("US and Iran signed a deal."), decision=DecisionType.NEW)
    prompt = b._get_prompt([d], "Iran War")
    assert "Bottom line" in prompt


def test_payload_includes_significance_and_corroboration():
    """IC6: significance + corroboration must reach the model so it can rank/collapse."""
    b = Briefer(llm_client=object())
    d = AlphaDecision(
        alpha=_alpha("Iran closed Hormuz.", event_class="state_change", verified_count=3),
        decision=DecisionType.NEW,
    )
    prompt = b._get_prompt([d], "Iran War")
    assert '"significance": "state_change"' in prompt
    assert '"corroborating_sources": 3' in prompt


def test_update_carries_delta_as_whats_new():
    """UPDATES must surface the delta (what changed) in the payload."""
    b = Briefer(llm_client=object())
    d = AlphaDecision(
        alpha=_alpha("Casualty toll rose to 3,912.", event_class="tally"),
        decision=DecisionType.UPDATE,
        delta="Toll rose from 3,468 to 3,912.",
    )
    prompt = b._get_prompt([d], "Iran War")
    assert "Toll rose from 3,468 to 3,912." in prompt


def test_significance_defaults_when_unlabelled():
    """A fact with no event_class still gets a usable significance value."""
    b = Briefer(llm_client=object())
    d = AlphaDecision(alpha=_alpha("Some fact."), decision=DecisionType.NEW)
    prompt = b._get_prompt([d], "Iran War")
    assert '"significance": "development"' in prompt


def test_one_chip_per_outlet_instruction_present():
    """IC5: the prompt must tell the model to cite each outlet once."""
    b = Briefer(llm_client=object())
    d = AlphaDecision(alpha=_alpha("Some fact."), decision=DecisionType.NEW)
    prompt = b._get_prompt([d], "Iran War")
    assert "ONE chip per OUTLET" in prompt
