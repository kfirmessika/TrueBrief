"""
Verifier - verifier/verifier.py

Pillar 2.5: Trust Layer.

Sits between Harvester and Arbiter/Ledger. Annotates alphas with
cross-source confirmation counts and quality flags. Zero LLM calls —
pure bookkeeping. Does NOT drop alphas; only annotates them so
downstream consumers (Arbiter, Briefer, API) can use the signal.

Three checks:
  1. Entity grounding  — strip entities that don't appear in the source
                         article text; flag the alpha as "ungrounded" if
                         none survive.
  2. Cross-source      — same entity ∩ close event_date from ≥2 distinct
                         source domains → verified_count = N domains.
                         Adds "cross_source_confirmed" flag when N ≥ 2.
  3. Date sanity       — flag events dated >90 days ago as "retrospective"
                         and events >7 days in the future as "future_date".
                         Soft flags only; nothing is dropped here (the
                         Harvester already enforces the hard 365-day limit).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List

from truebrief.models.alpha import Alpha

logger = logging.getLogger(__name__)

# How close two event_dates must be for cross-source confirmation (days)
CROSS_SOURCE_DATE_WINDOW_DAYS = 7

# Generic-entity stop-list (cross-source corroboration): only apply it to batches of at
# least this many alphas, and treat an entity as "generic" (too ubiquitous to corroborate)
# when it appears in more than this fraction of the batch. Small batches keep all entities.
_STOPLIST_MIN_BATCH = 8
_GENERIC_ENTITY_FRACTION = 0.5

# How old an event_date can be before we flag it "retrospective"
RETROSPECTIVE_THRESHOLD_DAYS = 90

# How far in the future an event_date can be before we flag "future_date"
FUTURE_THRESHOLD_DAYS = 7


class Verifier:
    """
    Annotates a batch of Alphas with trust signals.

    Usage:
        verifier = Verifier()
        alphas = verifier.verify_batch(alphas, article_texts)
    """

    def verify_batch(
        self,
        alphas: List[Alpha],
        article_texts: Dict[str, str],
    ) -> List[Alpha]:
        """
        Run all three verification passes on the current batch.

        Args:
            alphas:        All Alphas harvested in this pipeline run.
            article_texts: Mapping of source_url → full article text.
                           Used for entity grounding.

        Returns:
            The same list with verified_count and verifier_flags populated.
        """
        if not alphas:
            return alphas

        # Pass 1: entity grounding (per-alpha, uses article text)
        alphas = [self._ground_entities(a, article_texts) for a in alphas]

        # Pass 2: cross-source confirmation (batch, compares all pairs)
        alphas = self._cross_source(alphas)

        # Pass 3: date sanity (per-alpha, purely temporal)
        now = datetime.utcnow()
        alphas = [self._date_sanity(a, now) for a in alphas]

        total = len(alphas)
        confirmed = sum(1 for a in alphas if a.verified_count >= 2)
        flagged   = sum(1 for a in alphas if a.verifier_flags)
        logger.info(
            f"[VERIFIER] {total} alphas — {confirmed} cross-source confirmed, "
            f"{flagged} flagged"
        )
        return alphas

    # ──────────────────────────────────────────────────────────────────────────
    # Pass 1: Entity grounding
    # ──────────────────────────────────────────────────────────────────────────

    def _ground_entities(self, alpha: Alpha, article_texts: Dict[str, str]) -> Alpha:
        """
        Remove entities that don't literally appear in the source article text.
        If all entities are hallucinated, flag the alpha as 'ungrounded'.
        """
        text = article_texts.get(alpha.source_url, "")
        if not text or not alpha.entities:
            return alpha

        text_lower = text.lower()
        grounded = [e for e in alpha.entities if e.lower() in text_lower]

        if len(grounded) < len(alpha.entities):
            dropped = [e for e in alpha.entities if e.lower() not in text_lower]
            logger.debug(
                f"[VERIFIER] Entity grounding removed {dropped} from "
                f"'{alpha.alpha_text[:60]}'"
            )

        if not grounded and alpha.entities:
            # All entities were hallucinated
            alpha.verifier_flags = list(alpha.verifier_flags) + ["ungrounded"]
            alpha.entities = []
        else:
            alpha.entities = grounded

        return alpha

    # ──────────────────────────────────────────────────────────────────────────
    # Pass 2: Cross-source confirmation
    # ──────────────────────────────────────────────────────────────────────────

    def _cross_source(self, alphas: List[Alpha]) -> List[Alpha]:
        """
        For each alpha, count how many DISTINCT source domains reported a
        fact sharing ≥1 SPECIFIC entity within CROSS_SOURCE_DATE_WINDOW_DAYS days.

        verified_count starts at 1 (the alpha's own source). Any additional
        confirming domain increments it. Adds "cross_source_confirmed" flag
        when verified_count ≥ 2.

        Generic-entity stop-list: an entity present in a large fraction of a sizeable
        batch (e.g. "Israel"/"Hamas"/"IDF" in a Middle-East scan) is too ubiquitous to
        corroborate a specific claim — it would hand almost every fact 6–7 free
        "confirmations". Such entities are excluded from the match so the count reflects
        shared SPECIFIC subjects, not topic co-occurrence. (Small batches keep all
        entities, so single-subject corroboration still works.)
        """
        generic: set[str] = set()
        if len(alphas) >= _STOPLIST_MIN_BATCH:
            from collections import Counter
            ent_docs: Counter = Counter()
            for a in alphas:
                for e in {x.lower() for x in a.entities}:
                    ent_docs[e] += 1
            threshold = len(alphas) * _GENERIC_ENTITY_FRACTION
            generic = {e for e, c in ent_docs.items() if c > threshold}
            if generic:
                logger.debug("[VERIFIER] generic entities excluded from corroboration: %s", sorted(generic))

        # Build entity → alpha indices map over SPECIFIC (non-generic) entities only.
        entity_index: Dict[str, List[int]] = {}
        for i, alpha in enumerate(alphas):
            for entity in alpha.entities:
                key = entity.lower()
                if key in generic:
                    continue
                entity_index.setdefault(key, []).append(i)

        # For each alpha, find all other alphas that share ≥1 specific entity
        # and have a close event_date, from a different source domain
        for i, alpha in enumerate(alphas):
            alpha.verified_count = 1  # always counts its own source
            confirming_domains: set[str] = {_domain(alpha.source_url)}

            candidate_indices: set[int] = set()
            for entity in alpha.entities:
                key = entity.lower()
                if key in generic:
                    continue
                for j in entity_index.get(key, []):
                    if j != i:
                        candidate_indices.add(j)

            for j in candidate_indices:
                other = alphas[j]
                other_domain = _domain(other.source_url)
                if other_domain in confirming_domains:
                    continue  # same domain doesn't count as independent
                if not _dates_close(alpha.event_date, other.event_date):
                    continue
                confirming_domains.add(other_domain)

            alpha.verified_count = len(confirming_domains)
            if alpha.verified_count >= 2:
                if "cross_source_confirmed" not in alpha.verifier_flags:
                    alpha.verifier_flags = list(alpha.verifier_flags) + ["cross_source_confirmed"]

        return alphas

    # ──────────────────────────────────────────────────────────────────────────
    # Pass 3: Date sanity (soft flags only)
    # ──────────────────────────────────────────────────────────────────────────

    def _date_sanity(self, alpha: Alpha, now: datetime) -> Alpha:
        if not alpha.event_date:
            return alpha
        ed = alpha.event_date
        if ed.tzinfo is not None:
            ed = ed.replace(tzinfo=None)
        if ed < now - timedelta(days=RETROSPECTIVE_THRESHOLD_DAYS):
            if "retrospective" not in alpha.verifier_flags:
                alpha.verifier_flags = list(alpha.verifier_flags) + ["retrospective"]
        if ed > now + timedelta(days=FUTURE_THRESHOLD_DAYS):
            if "future_date" not in alpha.verifier_flags:
                alpha.verifier_flags = list(alpha.verifier_flags) + ["future_date"]
        return alpha


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

_DOMAIN_RE = re.compile(r"https?://(?:www\.)?([^/]+)")


def _domain(url: str) -> str:
    m = _DOMAIN_RE.match(url or "")
    return m.group(1) if m else url


def _dates_close(d1, d2) -> bool:
    if d1 is None or d2 is None:
        return False
    a = d1.replace(tzinfo=None) if d1.tzinfo else d1
    b = d2.replace(tzinfo=None) if d2.tzinfo else d2
    return abs((a - b).days) <= CROSS_SOURCE_DATE_WINDOW_DAYS
