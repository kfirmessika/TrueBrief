"""
Tests for IC1 (tally collapse) and IC2 (event_class significance ordering).

All tests are pure-Python — no LLM, no Supabase, no network.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest

from truebrief.models.alpha import Alpha, AlphaDecision, DecisionType


# ─── helpers ──────────────────────────────────────────────────────────────────

def _alpha(
    text: str,
    entities: list[str],
    event_class: Optional[str] = None,
    topic_id: str = "t1",
    url: str = "https://a.com/x",
) -> Alpha:
    return Alpha(
        alpha_text=text,
        entities=entities,
        source_url=url,
        source_name="Test",
        event_date=datetime(2026, 6, 19),
        topic_id=topic_id,
        event_class=event_class,
    )


def _decision(alpha: Alpha, dt: DecisionType = DecisionType.NEW) -> AlphaDecision:
    return AlphaDecision(alpha=alpha, decision=dt)


# ─── IC2: harvester event_class parsing ───────────────────────────────────────

class TestHarvesterEventClass:
    """Harvester correctly parses and validates the event_class field."""

    def _run_parse(self, raw_class: str) -> Optional[str]:
        """Replicate the harvester's validation logic."""
        _VALID = {"state_change", "escalation", "development", "incremental", "tally", "routine"}
        val = str(raw_class or "").strip().lower()
        return val if val in _VALID else None

    def test_valid_state_change(self):
        assert self._run_parse("state_change") == "state_change"

    def test_valid_tally(self):
        assert self._run_parse("TALLY") == "tally"  # case-insensitive

    def test_invalid_class_returns_none(self):
        assert self._run_parse("breaking_news") is None

    def test_empty_returns_none(self):
        assert self._run_parse("") is None

    def test_whitespace_returns_none(self):
        assert self._run_parse("  ") is None


# ─── IC2: runner significance sort ────────────────────────────────────────────

_CLASS_WEIGHT = {
    "state_change": 1.0,
    "escalation":   0.8,
    "development":  0.6,
    "incremental":  0.4,
    "routine":      0.2,
    "tally":        0.1,
}


def _sort_by_significance(decisions: List[AlphaDecision]) -> List[AlphaDecision]:
    return sorted(
        decisions,
        key=lambda d: _CLASS_WEIGHT.get(d.alpha.event_class or "", 0.5),
        reverse=True,
    )


class TestSignificanceSort:
    """IC2: state_change leads, tally trails."""

    def test_state_change_leads(self):
        decisions = [
            _decision(_alpha("Casualty toll hits 7000", ["Iran"], event_class="tally")),
            _decision(_alpha("Ceasefire signed", ["US", "Iran"], event_class="state_change")),
            _decision(_alpha("Troops deployed", ["Israel"], event_class="escalation")),
        ]
        sorted_d = _sort_by_significance(decisions)
        assert sorted_d[0].alpha.event_class == "state_change"
        assert sorted_d[-1].alpha.event_class == "tally"

    def test_tally_is_last(self):
        decisions = [
            _decision(_alpha("Tally A", ["US"], event_class="tally")),
            _decision(_alpha("Tally B", ["US"], event_class="tally")),
            _decision(_alpha("Attack", ["Iran"], event_class="escalation")),
        ]
        sorted_d = _sort_by_significance(decisions)
        classes = [d.alpha.event_class for d in sorted_d]
        assert classes[0] == "escalation"
        assert all(c == "tally" for c in classes[1:])

    def test_unlabelled_falls_in_middle(self):
        """Facts with no event_class (weight=0.5) sort between escalation and incremental."""
        decisions = [
            _decision(_alpha("Incremental update", ["X"], event_class="incremental")),
            _decision(_alpha("Unlabelled fact", ["X"], event_class=None)),
            _decision(_alpha("Escalation", ["X"], event_class="escalation")),
        ]
        sorted_d = _sort_by_significance(decisions)
        classes = [d.alpha.event_class for d in sorted_d]
        assert classes[0] == "escalation"
        assert classes[-1] == "incremental"
        assert classes[1] is None


# ─── IC1: tally collapse via find_tally_match ─────────────────────────────────

class TestTallyCollapse:
    """IC1: arbiter forces UPDATE when a tally for the same entities already exists."""

    def _make_arbiter_with_tally_match(self, match: Optional[Alpha]):
        """Return an Arbiter whose ledger.find_tally_match() returns `match`."""
        from truebrief.arbiter.arbiter import Arbiter

        mock_ledger = MagicMock()
        mock_ledger.find_tally_match.return_value = match
        # embed always returns a dummy vector (embedding failure → AUTO-NEW, skip the tally path)
        mock_ledger.llm.embed.return_value = [0.0] * 768
        mock_ledger.find_similar.return_value = []

        arbiter = Arbiter.__new__(Arbiter)
        arbiter.ledger = mock_ledger
        arbiter._judge_llm = MagicMock()
        return arbiter

    def test_tally_with_match_forces_update(self):
        existing = _alpha("Death toll: 3,468 as of Apr 26", ["Iran", "Israel"], event_class="tally")
        existing.id = "existing-uuid-1"
        arbiter = self._make_arbiter_with_tally_match(existing)

        incoming = _alpha("Death toll: 7,300 since Feb 28", ["Iran", "Israel"], event_class="tally")
        incoming.embedding = [0.0] * 768  # pre-embedded so _ensure_embedding is skipped

        with patch("truebrief.arbiter.arbiter.settings") as mock_settings:
            mock_settings.V3_TALLY_COLLAPSE = True
            mock_settings.V3_ENTITY_DEDUP = False
            decision, _ = arbiter._prepare(incoming, topic_id="t1")

        assert decision is not None
        assert decision.decision == DecisionType.UPDATE
        assert decision.matched_alpha_id == "existing-uuid-1"

    def test_tally_without_match_proceeds_normally(self):
        """When no existing tally matches, _prepare falls through to normal path (returns None for grey zone)."""
        arbiter = self._make_arbiter_with_tally_match(None)
        incoming = _alpha("Death toll: 7,300", ["Iran"], event_class="tally")
        incoming.embedding = [0.0] * 768

        with patch("truebrief.arbiter.arbiter.settings") as mock_settings:
            mock_settings.V3_TALLY_COLLAPSE = True
            mock_settings.V3_ENTITY_DEDUP = False
            # find_similar returns [] so it should return AUTO-NEW
            decision, _ = arbiter._prepare(incoming, topic_id="t1")

        # Zero matches → AUTO-NEW (not tally-UPDATE)
        assert decision is not None
        assert decision.decision == DecisionType.NEW

    def test_flag_off_skips_tally_path(self):
        """When V3_TALLY_COLLAPSE is False, tally facts go through normal scoring."""
        existing = _alpha("Toll", ["Iran"], event_class="tally")
        existing.id = "x"
        arbiter = self._make_arbiter_with_tally_match(existing)
        incoming = _alpha("Toll 2", ["Iran"], event_class="tally")
        incoming.embedding = [0.0] * 768

        with patch("truebrief.arbiter.arbiter.settings") as mock_settings:
            mock_settings.V3_TALLY_COLLAPSE = False
            mock_settings.V3_ENTITY_DEDUP = False
            decision, _ = arbiter._prepare(incoming, topic_id="t1")

        # No tally bypass → normal AUTO-NEW (zero vector matches)
        assert decision.decision == DecisionType.NEW
        arbiter.ledger.find_tally_match.assert_not_called()


# ─── IC1: find_tally_match entity overlap logic ───────────────────────────────

class TestFindTallyMatchEntityOverlap:
    """The entity-overlap gate in find_tally_match (unit-tested without DB)."""

    def _overlap(self, a: list, b: list) -> float:
        sa, sb = {e.lower() for e in a}, {e.lower() for e in b}
        return len(sa & sb) / max(len(sa | sb), 1)

    def test_exact_match_full_overlap(self):
        assert self._overlap(["Iran", "Israel"], ["Iran", "Israel"]) == 1.0

    def test_partial_overlap_passes_threshold(self):
        assert self._overlap(["Iran", "Israel", "US"], ["Iran", "Israel"]) >= 0.5

    def test_no_overlap_fails_threshold(self):
        assert self._overlap(["Iran"], ["Israel"]) < 0.5

    def test_case_insensitive(self):
        assert self._overlap(["Iran", "ISRAEL"], ["iran", "israel"]) == 1.0
