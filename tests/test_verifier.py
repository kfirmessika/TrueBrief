"""
Tests for the Verifier trust layer.
"""

from datetime import datetime, timedelta

import pytest

from truebrief.models.alpha import Alpha
from truebrief.verifier.verifier import Verifier


def make_alpha(
    text: str,
    entities: list[str],
    source_url: str,
    event_date: datetime | None = None,
) -> Alpha:
    return Alpha(
        alpha_text=text,
        entities=entities,
        source_url=source_url,
        source_name="test",
        event_date=event_date or datetime(2026, 6, 1),
    )


VERIFIER = Verifier()


# ── Entity grounding ──────────────────────────────────────────────────────────

class TestEntityGrounding:
    def test_keeps_entities_present_in_text(self):
        alpha = make_alpha("Apple released new chips.", ["Apple", "TSMC"], "https://a.com/1")
        result = VERIFIER.verify_batch([alpha], {"https://a.com/1": "Apple announced new silicon chips today."})
        assert "Apple" in result[0].entities
        assert "TSMC" not in result[0].entities  # not in article

    def test_flags_ungrounded_when_no_entities_survive(self):
        alpha = make_alpha("Something happened.", ["Ghost Corp"], "https://a.com/1")
        result = VERIFIER.verify_batch([alpha], {"https://a.com/1": "Nothing relevant here."})
        assert "ungrounded" in result[0].verifier_flags
        assert result[0].entities == []

    def test_no_penalty_when_no_article_text(self):
        alpha = make_alpha("Apple does something.", ["Apple"], "https://a.com/1")
        # Empty article_texts — verifier should skip grounding safely
        result = VERIFIER.verify_batch([alpha], {})
        assert result[0].entities == ["Apple"]
        assert "ungrounded" not in result[0].verifier_flags


# ── Cross-source confirmation ─────────────────────────────────────────────────

class TestCrossSource:
    def test_confirmed_by_two_domains(self):
        date = datetime(2026, 6, 1)
        a1 = make_alpha("Apple raises $1B.", ["Apple"], "https://nytimes.com/1", date)
        a2 = make_alpha("Apple secures 1 billion.", ["Apple"], "https://reuters.com/1", date)
        results = VERIFIER.verify_batch([a1, a2], {})
        assert results[0].verified_count == 2
        assert results[1].verified_count == 2
        assert "cross_source_confirmed" in results[0].verifier_flags

    def test_same_domain_does_not_double_count(self):
        date = datetime(2026, 6, 1)
        a1 = make_alpha("Apple raises $1B.", ["Apple"], "https://nytimes.com/1", date)
        a2 = make_alpha("Apple raises billion dollars.", ["Apple"], "https://nytimes.com/2", date)
        results = VERIFIER.verify_batch([a1, a2], {})
        assert results[0].verified_count == 1  # same domain, no cross-source bonus
        assert "cross_source_confirmed" not in results[0].verifier_flags

    def test_dates_too_far_apart_no_confirmation(self):
        a1 = make_alpha("Apple raises $1B.", ["Apple"], "https://nytimes.com/1", datetime(2026, 6, 1))
        a2 = make_alpha("Apple raises funds.", ["Apple"], "https://reuters.com/1", datetime(2026, 1, 1))
        results = VERIFIER.verify_batch([a1, a2], {})
        assert results[0].verified_count == 1


# ── Date sanity ───────────────────────────────────────────────────────────────

class TestDateSanity:
    def test_retrospective_flag(self):
        old_date = datetime.utcnow() - timedelta(days=100)
        alpha = make_alpha("Old event.", ["Corp"], "https://a.com/1", old_date)
        result = VERIFIER.verify_batch([alpha], {})
        assert "retrospective" in result[0].verifier_flags

    def test_future_date_flag(self):
        future_date = datetime.utcnow() + timedelta(days=10)
        alpha = make_alpha("Future event.", ["Corp"], "https://a.com/1", future_date)
        result = VERIFIER.verify_batch([alpha], {})
        assert "future_date" in result[0].verifier_flags

    def test_normal_date_no_flags(self):
        normal_date = datetime.utcnow() - timedelta(days=5)
        alpha = make_alpha("Recent event.", ["Corp"], "https://a.com/1", normal_date)
        result = VERIFIER.verify_batch([alpha], {})
        assert "retrospective" not in result[0].verifier_flags
        assert "future_date" not in result[0].verifier_flags

    def test_no_date_no_flags(self):
        alpha = Alpha(
            alpha_text="Something.", entities=[], source_url="https://a.com/1",
            source_name="test", event_date=None,
        )
        result = VERIFIER.verify_batch([alpha], {})
        assert result[0].verifier_flags == []

    def test_empty_batch(self):
        assert VERIFIER.verify_batch([], {}) == []
