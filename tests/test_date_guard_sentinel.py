"""
Test the date-guard sentinel fix (real failure found 2026-06-21 on live data).

An LLM that returns a null/epoch date (1970-01-01) for an "overnight" breaking
fact used to be "year-corrected" into a fabricated 2026-01-01 that polluted
recency/salience. It must instead anchor to the article date (today when the
article has no published_at).
"""

import json
from datetime import datetime
from unittest.mock import patch

from truebrief.harvester.harvester import Harvester
from truebrief.models.article import ArticleSource, RawArticle


class _LLM:
    def __init__(self, payload):
        self._payload = payload

    def call(self, **kwargs):
        return json.dumps(self._payload)


def _article(published_at=None):
    return RawArticle(
        url="https://news.google.com/x",
        title="Iran strike on Kuwait airport",
        source_name="Google News",
        source_type=ArticleSource.GOOGLE_NEWS,
        published_at=published_at,
        text="Iran launched a military strike on Kuwait International Airport overnight.",
    )


def _harvest_one(event_date_str, published_at=None):
    payload = [{
        "alpha_text": "Iran launched a military strike on Kuwait International Airport.",
        "entities": ["Iran", "Kuwait"],
        "event_date": event_date_str,
        "confidence": 0.95,
    }]
    h = Harvester(llm_client=_LLM(payload))
    with patch("config.settings.settings.V3_DATE_GUARD", True):
        return h.extract(_article(published_at), topic_id="t1", topic_context="Iran War")


def test_epoch_date_anchors_to_today_not_jan_first():
    today = datetime.now().replace(tzinfo=None)
    alphas = _harvest_one("1970-01-01")
    assert len(alphas) == 1
    ed = alphas[0].event_date
    # Must NOT be the fabricated 2026-01-01; must be anchored to ~today.
    assert not (ed.month == 1 and ed.day == 1 and ed.year == today.year)
    assert abs((today - ed).days) <= 1


def test_epoch_date_anchors_to_published_at_when_present():
    pub = datetime(2026, 6, 20)
    alphas = _harvest_one("1970-01-01", published_at=pub)
    assert len(alphas) == 1
    assert alphas[0].event_date.date() == pub.date()


def test_real_recent_date_is_preserved():
    alphas = _harvest_one("2026-06-21", published_at=datetime(2026, 6, 21))
    assert len(alphas) == 1
    assert alphas[0].event_date.date() == datetime(2026, 6, 21).date()
