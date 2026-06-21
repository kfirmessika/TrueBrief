"""
Tests for IC2 significance × recency (lede salience).

Locks in the ordering the 2026-06-21 benchmark exposed: the brief must lead with
the most significant CURRENT development — a fresh escalation outranks a stale
state_change, but a fresh state_change still outranks a fresh tally.
"""

from datetime import datetime, timedelta

from truebrief.pipeline.runner import _salience_score

NOW = datetime(2026, 6, 21)


def _days_ago(n):
    return NOW - timedelta(days=n)


def test_significance_breaks_ties_at_same_recency():
    sc = _salience_score("state_change", NOW, NOW)
    tally = _salience_score("tally", NOW, NOW)
    assert sc > tally
    esc = _salience_score("escalation", NOW, NOW)
    assert sc > esc > tally


def test_fresh_escalation_outranks_stale_state_change():
    fresh_esc = _salience_score("escalation", NOW, NOW)
    stale_sc = _salience_score("state_change", _days_ago(7), NOW)
    assert fresh_esc > stale_sc


def test_fresh_state_change_still_outranks_fresh_tally():
    sc = _salience_score("state_change", NOW, NOW)
    tally = _salience_score("tally", NOW, NOW)
    assert sc > tally


def test_recency_is_monotonic_for_same_class():
    today = _salience_score("development", NOW, NOW)
    older = _salience_score("development", _days_ago(3), NOW)
    oldest = _salience_score("development", _days_ago(10), NOW)
    assert today > older > oldest


def test_floor_keeps_significance_relevant_when_old():
    # Even a 30-day-old state_change keeps at least FLOOR × class_weight (0.4 × 1.0).
    old_sc = _salience_score("state_change", _days_ago(30), NOW)
    assert old_sc >= 0.4 * 1.0 - 1e-9


def test_unknown_class_is_neutral():
    assert abs(_salience_score(None, NOW, NOW) - 0.5) < 1e-9


def test_unknown_date_gets_no_recency_penalty():
    # event_date None → treated as current (full recency multiplier = 1.0).
    assert abs(_salience_score("state_change", None, NOW) - 1.0) < 1e-9


def test_iso_string_date_is_parsed():
    s = _salience_score("escalation", "2026-06-21T00:00:00", NOW)
    assert s > 0
