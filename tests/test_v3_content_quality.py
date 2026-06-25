"""
Tests — tests/test_v3_content_quality.py

Locks in the V3 facts-not-opinions content-quality fixes (from the adversarial review):
  - casualty < state_change ranking (a single death never leads over a structural shift)
  - the no-LLM assembler's grounded union lede (a high-salience UPDATE can lead)
  - the §8B is_background / lag gate (evergreen + stale facts dropped at harvest)
  - the verifier generic-entity stop-list (ubiquitous entities don't inflate the count,
    but specific shared entities still corroborate)
  - the honest "(N reports)" corroboration label
"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import patch

from truebrief.models.alpha import Alpha, AlphaDecision, DecisionType
from truebrief.briefer.assembler import assemble_brief, _salience
from truebrief.verifier.verifier import Verifier

NOW = datetime(2026, 6, 25)


def _decision(text, cls, vc=1, dec=DecisionType.NEW, delta=None, bg=False, ed=NOW):
    a = Alpha(alpha_text=text, entities=[], source_url="https://x.com/a", source_name="x.com",
              event_date=ed, event_class=cls, verified_count=vc, is_background=bg)
    return AlphaDecision(alpha=a, decision=dec, delta=delta)


# ── Ranking ──────────────────────────────────────────────────────────────────

def test_casualty_ranks_below_state_change():
    """A single individual death must not outrank a topic-level structural shift."""
    death = _decision("A contractor was killed in Gaza", "casualty")
    ruling = _decision("The ICJ declared the occupation unlawful", "state_change")
    assert _salience(ruling, NOW) > _salience(death, NOW)


def test_bottom_line_unions_new_and_updates():
    """The grounded lede is the highest-salience development across BOTH pools, and an
    UPDATE leads with its delta (what changed)."""
    decisions = [
        _decision("A contractor was killed", "casualty"),
        _decision("Ceasefire signed", "state_change", vc=6, dec=DecisionType.UPDATE,
                  delta="The parties signed a ceasefire on June 25"),
    ]
    brief = assemble_brief(decisions, "Topic")
    head = brief.split("NEW STORIES")[0].lower()
    assert "ceasefire" in head and "contractor" not in head


def test_reports_label_not_sources():
    """Corroboration is labelled '(N reports)', never the unprovable '(N sources)'."""
    brief = assemble_brief([_decision("X happened", "development", vc=4)], "T")
    assert "(4 reports)" in brief
    assert "(4 sources)" not in brief


def test_background_excluded_from_brief():
    """is_background facts never appear (defense-in-depth in the assembler)."""
    decisions = [
        _decision("Hamas attacked an IDF tank", "escalation"),
        _decision("The family has disputed the land since 1991", "development", bg=True),
    ]
    brief = assemble_brief(decisions, "T")
    assert "1991" not in brief
    assert "tank" in brief


# ── §8B lag / background gate at harvest ─────────────────────────────────────

def test_harvester_drops_background_fact():
    """A standing-state/background fact is dropped by the lag gate even when the LLM
    dates it to today (lag≈0)."""
    from config.settings import settings
    from truebrief.harvester.harvester import Harvester
    from truebrief.models.article import RawArticle, ArticleSource

    fake = json.dumps([
        {"alpha_text": "Hamas crossed into Israel and attacked a tank.", "entities": ["Hamas"],
         "event_date": "2026-06-25", "date_basis": "explicit", "is_background": False,
         "context": "", "confidence": 0.9, "event_class": "escalation"},
        {"alpha_text": "The family has been in a land dispute since 1991.", "entities": ["family"],
         "event_date": "2026-06-25", "date_basis": "explicit", "is_background": True,
         "context": "", "confidence": 0.9, "event_class": "development"},
    ])
    art = RawArticle(url="http://x/a", title="t", source_name="x",
                     source_type=ArticleSource.TAVILY, published_at=NOW, text="...")
    h = Harvester()
    with patch.object(settings, "V3_LAG_GATE", True), patch.object(h.llm, "call", return_value=fake):
        alphas = h.extract(art)
    assert len(alphas) == 1
    assert "1991" not in alphas[0].alpha_text


# ── Verifier generic-entity stop-list ────────────────────────────────────────

def _va(text, dom, ents):
    return Alpha(alpha_text=text, entities=ents, source_url=f"https://{dom}/x",
                 source_name=dom, event_date=NOW, event_class="development")


def test_ubiquitous_entity_does_not_inflate_count():
    """8 distinct claims sharing ONLY a ubiquitous entity must not all reach 8."""
    batch = [_va(f"Distinct claim {i}", f"d{i}.com", ["Hamas"]) for i in range(8)]
    Verifier()._cross_source(batch)
    assert max(a.verified_count for a in batch) == 1


def test_specific_shared_entity_still_corroborates():
    """A SPECIFIC shared entity still corroborates within a large batch (no false negative)."""
    batch = [_va(f"noise {i}", f"n{i}.com", ["Hamas"]) for i in range(8)]
    batch += [
        _va("Khalil al-Hayya met mediators", "a.com", ["Hamas", "Khalil al-Hayya"]),
        _va("Khalil al-Hayya met mediators", "b.com", ["Hamas", "Khalil al-Hayya"]),
    ]
    Verifier()._cross_source(batch)
    hayya = [a for a in batch if "Hayya" in a.alpha_text]
    assert all(a.verified_count == 2 for a in hayya)


def test_small_batch_keeps_all_entities():
    """Small batches skip the stop-list, so single-subject corroboration still works."""
    batch = [
        _va("Apple raised $1B", "reuters.com", ["Apple"]),
        _va("Apple raised $1B", "bloomberg.com", ["Apple"]),
    ]
    Verifier()._cross_source(batch)
    assert all(a.verified_count == 2 for a in batch)
