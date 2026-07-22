"""
Tests for ledger/alarm_schedule.py — pure date-math for V5 manual scheduling
(docs/core/architecture_v5.md §7). No DB, no network.
"""
from __future__ import annotations

from datetime import datetime

from truebrief.ledger.alarm_schedule import (
    DEFAULT_HOUR,
    DEFAULT_MINUTE,
    compute_next_run,
    min_spacing_hours_ok,
)


class TestComputeNextRun:
    def test_empty_list_uses_default_time_today_if_not_passed(self):
        now = datetime(2026, 7, 22, 6, 0)  # before the 09:00 default
        result = compute_next_run([], now)
        assert result == datetime(2026, 7, 22, DEFAULT_HOUR, DEFAULT_MINUTE)

    def test_empty_list_uses_default_time_tomorrow_if_already_passed(self):
        now = datetime(2026, 7, 22, 12, 0)  # after the 09:00 default
        result = compute_next_run([], now)
        assert result == datetime(2026, 7, 23, DEFAULT_HOUR, DEFAULT_MINUTE)

    def test_picks_soonest_of_multiple_times(self):
        now = datetime(2026, 7, 22, 10, 0)
        result = compute_next_run([(9, 0), (12, 0), (20, 0)], now)
        assert result == datetime(2026, 7, 22, 12, 0)

    def test_wraps_to_tomorrow_when_all_times_passed(self):
        now = datetime(2026, 7, 22, 21, 0)
        result = compute_next_run([(9, 0), (12, 0), (20, 0)], now)
        assert result == datetime(2026, 7, 23, 9, 0)

    def test_exact_match_at_now_rolls_to_tomorrow(self):
        """Guards against the double-fire risk the scheduler relies on — an exact
        match is treated as 'already fired', not 'fire again right now'."""
        now = datetime(2026, 7, 22, 9, 0)
        result = compute_next_run([(9, 0)], now)
        assert result == datetime(2026, 7, 23, 9, 0)

    def test_single_time_far_in_future_same_day(self):
        now = datetime(2026, 7, 22, 0, 1)
        result = compute_next_run([(23, 59)], now)
        assert result == datetime(2026, 7, 22, 23, 59)


class TestMinSpacingHoursOk:
    def test_single_time_always_ok(self):
        assert min_spacing_hours_ok([(9, 0)], min_interval_hours=24.0) is True

    def test_zero_or_negative_floor_always_ok(self):
        assert min_spacing_hours_ok([(9, 0), (9, 30)], min_interval_hours=0) is True

    def test_free_tier_floor_rejects_two_times_same_day(self):
        # free tier: min_interval_hours=24 — two times in one day can never be 24h apart
        assert min_spacing_hours_ok([(9, 0), (20, 0)], min_interval_hours=24.0) is False

    def test_pro_tier_floor_accepts_hourly_spaced_times(self):
        # pro tier: min_interval_hours=1 — times spaced >=1h apart are fine
        assert min_spacing_hours_ok([(9, 0), (12, 0), (20, 0)], min_interval_hours=1.0) is True

    def test_pro_tier_floor_rejects_times_too_close(self):
        assert min_spacing_hours_ok([(9, 0), (9, 30)], min_interval_hours=1.0) is False

    def test_wraps_across_midnight(self):
        # 23:00 -> 01:00 is only a 2h gap the "short way" around midnight
        assert min_spacing_hours_ok([(23, 0), (1, 0)], min_interval_hours=1.0) is True
        assert min_spacing_hours_ok([(23, 0), (1, 0)], min_interval_hours=3.0) is False
