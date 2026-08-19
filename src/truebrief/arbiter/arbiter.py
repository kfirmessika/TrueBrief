"""
Arbiter - arbiter/arbiter.py

Pillar 4: Judge.

Determines whether each incoming Alpha is:
  NEW      - Not seen before. Store and include in brief.
  UPDATE   - New information that extends a known fact. Store with delta. Include in brief.
  DUPLICATE- Same fact already known. Skip. Log for source quality tracking.

Phase 2 Fast-Path Logic (saves ~50% of Judge LLM calls):
  Score > AUTO_MERGE_THRESHOLD  → AUTO-DUPLICATE  (no LLM, obvious duplicate)
  Score in GREY ZONE            → Judge LLM        (ambiguous, need reasoning)
  Score < GREY_ZONE_MIN or 0 matches → AUTO-NEW   (no LLM, obviously new)

Temporal overlap adjusts every score before thresholding, so facts from
different time periods can't be wrongly merged even at high vector similarity.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional, Tuple

from config.settings import (
    SIMILARITY_THRESHOLD_DUPLICATE,
    SIMILARITY_THRESHOLD_UPDATE,
    settings,
)
from truebrief.arbiter.contradiction import detect_contradiction
from truebrief.arbiter.judge import JudgeLLM
from truebrief.arbiter.temporal import adjusted_similarity, entity_overlap, temporal_overlap
from truebrief.ledger.vector_store import VectorStore
from truebrief.models.alpha import Alpha, AlphaDecision, DecisionType

logger = logging.getLogger(__name__)

# ── Threshold constants ────────────────────────────────────────────────────────
# Auto-merge (DUPLICATE) if adjusted score exceeds this. No LLM call needed.
AUTO_MERGE_THRESHOLD: float = 0.97

# Grey zone: [GREY_ZONE_MIN, AUTO_MERGE_THRESHOLD) → send to Judge LLM.
# Below GREY_ZONE_MIN and when there are zero matches → AUTO-NEW.
GREY_ZONE_MIN: float = SIMILARITY_THRESHOLD_UPDATE   # 0.75 from settings

# How many matches to retrieve from the ledger for each judgment.
# 1 is enough for fast-path; we fetch up to 3 so the Judge LLM has context.
LEDGER_FETCH_LIMIT: int = 3

# Low-threshold fetch: cast a wider net so we don't miss the best match.
# The actual thresholding is done in Python after retrieval.
LEDGER_FETCH_THRESHOLD: float = 0.50

# Same-day near-identical fast-path: raw cosine at/above this + same event_date +
# identical numbers → auto-DUPLICATE without the Judge LLM (see Step 3c).
SAME_DAY_DUP_THRESHOLD: float = 0.93


def _digit_runs(text: str) -> list:
    """All digit runs in the text, in order — a cheap numeric fingerprint."""
    return re.findall(r"\d+", text)


# Compact word→number map for _normalized_numbers() — NOT a full NLP number parser
# (simplicity over cleverness, per project philosophy). Covers one..nineteen, the
# tens, hundred/thousand/million/billion, and dozen/half, which is enough to close
# the specific blind spot Stage 1 Experiment 2 measured on real data (2026-08-16,
# docs/benchmarks/2026-08-13_stage1-validation.md): a digit-only comparison sees
# "halted five vessels" and "halted three vessels" as having NO numeric
# difference at all, because neither "five" nor "three" is a digit run.
_NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_SCALE_WORDS = {"hundred": 100, "thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}
_UNIT_WORDS = {"dozen": 12, "dozens": 12, "half": 0.5}

_NUMBER_TOKEN_RE = re.compile(r"\d[\d,]*\.?\d*|[a-zA-Z]+")

# Attached scale-letter suffixes ("1.8M", "$500K", "2B") never reached the word→scale
# map below because the digit-token regex above stops at the letter and "m"/"k"/"b"
# alone aren't in _SCALE_WORDS. Expanded to their spelled-out form before tokenizing
# so the existing combine logic handles them unchanged. Requires the letter directly
# against a digit (no space) so unrelated units glued to a number aren't misread —
# and specifically NOT matched when a second letter follows (guards "50km"/"5kg":
# the trailing \b fails between two letters, so "k" in "50km" is left alone).
_SCALE_SUFFIX_RE = re.compile(r"(?<=\d)([kKmMbB])\b")
_SCALE_SUFFIX_EXPAND = {"k": " thousand", "m": " million", "b": " billion"}

# Fillers that never carry numeric meaning but sit between number words in normal
# English ("half A million", "twenty AND five") — skipped rather than treated as a
# run-breaking word, so the surrounding number tokens still combine.
_FILLER_WORDS = {"a", "an", "and"}


def _normalized_numbers(text: str) -> set:
    """
    Canonical set of numeric values mentioned in `text`, covering both digit runs
    ("59", "3,912", "1.6") AND common spelled-out numbers ("five", "twelve", "two
    dozen", "a hundred", "1.6 million", "1.8M"). Used in place of raw
    ``_digit_runs()`` equality by the fast-path gates below, so a value that only
    differs because one side spelled it out is no longer invisible to the guard.

    Adjacent number tokens combine the way they're normally read ("twenty" +
    "five" -> 25, "1.6" + "million" -> 1_600_000, "half" + "a" + "million" ->
    500_000 — "a"/"an"/"and" are skipped, not run-breaking); any other non-number
    word breaks the run. Deliberately conservative: it will under-parse an unusual
    phrasing ("a couple dozen") rather than guess, which is the safe failure
    direction — the guard simply won't fire (same as today), it won't invent a
    false match.
    """
    text = _SCALE_SUFFIX_RE.sub(lambda m: _SCALE_SUFFIX_EXPAND[m.group(1).lower()], text)
    tokens = _NUMBER_TOKEN_RE.findall(text.lower())
    values: set = set()
    current = 0.0
    have_current = False

    def _flush():
        nonlocal current, have_current
        if have_current:
            values.add(current)
        current = 0.0
        have_current = False

    for tok in tokens:
        if tok[0].isdigit():
            _flush()
            try:
                current = float(tok.replace(",", ""))
                have_current = True
            except ValueError:
                pass
            continue
        if tok in _NUMBER_WORDS:
            current = current + _NUMBER_WORDS[tok] if have_current else float(_NUMBER_WORDS[tok])
            have_current = True
            continue
        if tok in _SCALE_WORDS or tok in _UNIT_WORDS:
            scale = _SCALE_WORDS.get(tok, _UNIT_WORDS.get(tok))
            base = current if have_current else 1.0
            current = base * scale
            have_current = True
            continue
        if tok in _FILLER_WORDS and have_current:
            continue  # "half A million" — don't let the article sever the run
        _flush()

    _flush()
    return values


# Purpose-built for the same-day-near-identical gate's specific blind spot: a
# magnitude-preserving directional reversal ("increased by 5%" vs "dropped by 5%")
# passes the gate's number-equality check untouched (5 == 5), and these particular
# direction words are deliberately absent from contradiction.py's general
# ANTONYM_PAIRS by design ("rose/fell/up/down... prone to false positives" — a tally
# genuinely rising then falling over time is normal, not a contradiction). This list
# is intentionally NOT merged into ANTONYM_PAIRS: it only matters when the numbers
# already match, which narrows it to exactly the shape IC4's general check can't
# safely make a blanket rule for. Do not expand this ad hoc for unrelated antonyms —
# it exists to catch same-value/opposite-direction, nothing else.
_DIRECTION_PAIRS = [
    ("increased", "decreased"), ("increased", "dropped"), ("increased", "fell"),
    ("rose", "fell"), ("rose", "dropped"), ("rose", "declined"),
    ("climbed", "fell"), ("climbed", "dropped"), ("gained", "lost"),
    ("grew", "shrank"), ("surged", "plunged"), ("up", "down"), ("higher", "lower"),
]
_WORD_RE = re.compile(r"[a-z]+")


def _direction_conflict(text_a: str, text_b: str) -> bool:
    """True if the two texts use opposite direction words from _DIRECTION_PAIRS."""
    wa = set(_WORD_RE.findall(text_a.lower()))
    wb = set(_WORD_RE.findall(text_b.lower()))
    return any((x in wa and y in wb) or (y in wa and x in wb) for x, y in _DIRECTION_PAIRS)


def _cosine(a: list, b: list) -> float:
    """Cosine similarity between two equal-length float vectors, pure Python (no numpy
    dependency here — pools are tiny, a handful of alphas per collect() batch)."""
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na > 0 and nb > 0 else 0.0


class Arbiter:
    """
    Pillar 4: The Judge.

    Phase 2 decision flow per Alpha:
      1. Generate embedding (if not already present)
      2. Fetch top-N similar facts from the Ledger
      3. Apply temporal adjustment to each score
      4. Fast-path: auto-DUPLICATE if top score > AUTO_MERGE_THRESHOLD
      5. Fast-path: auto-NEW if top score < GREY_ZONE_MIN (or zero matches)
      6. Grey-zone: call Judge LLM for MERGE / UPDATE / NEW decision
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        judge: Optional[JudgeLLM] = None,
    ) -> None:
        self.ledger = vector_store or VectorStore()
        self._judge_llm = judge or JudgeLLM(llm=self.ledger.llm)

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def judge_alpha(self, alpha: Alpha, topic_id: Optional[str] = None) -> AlphaDecision:
        """
        Evaluate a single Alpha and return a verdict.

        Args:
            alpha:    The incoming fact to evaluate.
            topic_id: Scope the ledger search to this topic (recommended).

        Returns:
            AlphaDecision with decision, score, matched_alpha_id, reasoning, and delta.
        """
        resolved, adjusted = self._prepare(alpha, topic_id)
        if resolved is not None:
            return resolved

        # Grey zone: one Judge LLM call for this fact.
        top_match, top_score = adjusted[0]
        logger.info(
            f"[ARBITER] '{alpha.alpha_text[:60]}...' → GREY ZONE "
            f"(score={top_score:.3f}) - calling Judge LLM"
        )
        decision, delta = self._judge_llm.call(alpha, adjusted)
        return self._grey_zone_decision(alpha, decision, delta, top_match, top_score)

    def judge_alphas(
        self, alphas: List[Alpha], topic_id: Optional[str] = None
    ) -> List[AlphaDecision]:
        """
        Evaluate several Alphas, batching the grey-zone Judge LLM calls into ONE
        request when ``settings.V3_BATCH_JUDGE`` is enabled (self-contained cases,
        safe to batch per architecture §5).

        Behaviour is identical to calling :meth:`judge_alpha` per fact — the
        returned decisions are in the same order as ``alphas``. When the flag is
        off (default) each grey-zone fact is judged individually, exactly as before.

        Intra-batch dedup (added 2026-08-13): ``_prepare()`` is called with a
        ``batch_pool`` that grows as earlier alphas in THIS SAME list are decided
        NEW/UPDATE, so a later alpha can match against an earlier one even though
        neither is in the DB yet (writes happen after this method returns, in the
        caller). See ``_prepare``'s ``extra_pool`` docstring for the live evidence.
        """
        # Resolve fast-paths first, sequentially, growing the in-batch pool as we
        # go — collect the grey-zone cases that still need the LLM after
        # considering both the DB ledger AND this batch's own earlier facts.
        batch_pool: List[Alpha] = []
        prepared: List[Tuple[Optional[AlphaDecision], List[Tuple[Alpha, float]]]] = []
        for alpha in alphas:
            resolved, adjusted = self._prepare(alpha, topic_id, extra_pool=batch_pool)
            prepared.append((resolved, adjusted))
            if resolved is not None and resolved.decision in (DecisionType.NEW, DecisionType.UPDATE):
                batch_pool.append(alpha)

        grey_idx = [i for i, (resolved, _) in enumerate(prepared) if resolved is None]

        if not grey_idx:
            return [resolved for resolved, _ in prepared]  # all fast-pathed

        decisions: List[Optional[AlphaDecision]] = [resolved for resolved, _ in prepared]

        if settings.V3_BATCH_JUDGE and len(grey_idx) >= 2:
            logger.info(f"[ARBITER] Batch-judging {len(grey_idx)} grey-zone facts in one call.")
            cases = [(alphas[i], prepared[i][1]) for i in grey_idx]
            verdicts = self._judge_llm.call_batch(cases)
            for i, (decision, delta) in zip(grey_idx, verdicts):
                adjusted = prepared[i][1]
                top_match, top_score = adjusted[0]
                decisions[i] = self._grey_zone_decision(
                    alphas[i], decision, delta, top_match, top_score
                )
        else:
            for i in grey_idx:
                adjusted = prepared[i][1]
                top_match, top_score = adjusted[0]
                decision, delta = self._judge_llm.call(alphas[i], adjusted)
                decisions[i] = self._grey_zone_decision(
                    alphas[i], decision, delta, top_match, top_score
                )

        return [d for d in decisions]  # type: ignore[misc]  # all slots filled above

    # ──────────────────────────────────────────────────────────────────────────
    # Backward-compatibility alias
    # ──────────────────────────────────────────────────────────────────────────

    def judge(self, alpha: Alpha, topic_id: Optional[str] = None) -> AlphaDecision:
        """
        Alias for judge_alpha(). Kept so existing callers (pipeline/runner.py)
        don't break. Prefer judge_alpha() in new code.
        """
        return self.judge_alpha(alpha, topic_id)

    # ──────────────────────────────────────────────────────────────────────────
    # Shared evaluation core
    # ──────────────────────────────────────────────────────────────────────────

    def _prepare(
        self,
        alpha: Alpha,
        topic_id: Optional[str],
        extra_pool: Optional[List[Alpha]] = None,
    ) -> Tuple[Optional[AlphaDecision], List[Tuple[Alpha, float]]]:
        """
        Run everything up to (but not including) the Judge LLM.

        Args:
            extra_pool: Alphas already decided NEW/UPDATE earlier in the SAME
                judge_alphas() batch, not yet written to the DB. Diagnosed
                2026-08-13 on live data: judge_alphas() judged the whole batch
                against ONLY the DB-stored ledger, writes happening afterward in
                the caller — so two near-duplicate facts extracted from the SAME
                single collect() call never saw each other (both got zero DB
                matches → AUTO-NEW, both stored as separate rows). Live audit:
                134 confirmed same-topic pairs at cosine 0.75-0.96, all inserted
                within 0.4-7.3 SECONDS of each other (same batch). Passing the
                batch's own already-decided alphas here closes that gap by
                treating them exactly like DB matches for every check below.

        Returns ``(decision, adjusted_matches)``:
          - ``decision`` is a finished AlphaDecision when a fast-path resolves it
            (embedding failure, zero matches, auto-DUPLICATE, or auto-NEW).
          - ``decision`` is ``None`` when the fact lands in the grey zone; the
            caller must run the Judge LLM using the returned (sorted) matches.
        """
        log_prefix = f"[ARBITER] '{alpha.alpha_text[:60]}...'"
        logger.info(f"{log_prefix}")

        # Step 1 - Ensure we have an embedding
        alpha = self._ensure_embedding(alpha, log_prefix)
        if alpha.embedding is None:
            logger.warning(f"{log_prefix} → AUTO-NEW (embedding failure)")
            return (
                AlphaDecision(
                    alpha=alpha,
                    decision=DecisionType.NEW,
                    reasoning="Embedding generation failed. Defaulting to NEW.",
                ),
                [],
            )

        # Step 1b — IC1 Tally collapse (V3_TALLY_COLLAPSE): running totals on the same
        # (metric, entity-set) are always an UPDATE in place, never a NEW fact.
        # Bypass vector similarity (wording varies too much) and use entity overlap.
        if settings.V3_TALLY_COLLAPSE and alpha.event_class == "tally":
            tally_match = self.ledger.find_tally_match(alpha)
            if tally_match is not None:
                # Guard 1 (Stage 2, 2026-08-16): identical numbers on both sides means
                # this is a verbatim restatement, not a genuine revision — DUPLICATE,
                # not UPDATE. Without this, IC1's own audit found it mislabeling exact
                # repeats as UPDATE 100% of the time it was wrong (per-gate breakdown,
                # docs/benchmarks/2026-08-13_arbiter-redteam-audit.md).
                if _normalized_numbers(alpha.alpha_text) == _normalized_numbers(tally_match.alpha_text):
                    logger.info(
                        f"{log_prefix} → TALLY-DUPLICATE (IC1: entity-overlap match, "
                        f"IDENTICAL numbers → '{tally_match.alpha_text[:60]}')"
                    )
                    return (
                        AlphaDecision(
                            alpha=alpha,
                            decision=DecisionType.DUPLICATE,
                            similarity_score=1.0,
                            matched_alpha_id=tally_match.id,
                            reasoning=(
                                "IC1 tally-collapse: entity-overlap match with identical "
                                "numbers — verbatim restatement, not a genuine tally revision."
                            ),
                        ),
                        [],
                    )

                # Guard 2 (Stage 2, 2026-08-16): IC1 used to fire and return UPDATE
                # before IC4's contradiction check (Step 2b, below) ever got a chance to
                # run — silently absorbing real contradictions (e.g. a polarity flip
                # mis-tagged event_class="tally") as tally revisions. Run the same check
                # here, first, so a contradiction against the matched tally is flagged as
                # NEW instead.
                contradiction_reason = detect_contradiction(
                    alpha.alpha_text, alpha.entities, alpha.event_date, alpha.event_class,
                    tally_match.alpha_text, tally_match.entities, tally_match.event_date,
                    tally_match.event_class,
                )
                if contradiction_reason:
                    alpha.contradicts_id = tally_match.id
                    alpha.contradiction_note = contradiction_reason
                    logger.info(
                        f"{log_prefix} → CONTRADICTION-NEW (IC1 pre-check vs "
                        f"'{tally_match.alpha_text[:50]}': {contradiction_reason})"
                    )
                    return (
                        AlphaDecision(
                            alpha=alpha,
                            decision=DecisionType.NEW,
                            matched_alpha_id=tally_match.id,
                            reasoning=(
                                f"IC1 pre-check contradiction — {contradiction_reason}. "
                                "Stored as NEW and flagged."
                            ),
                        ),
                        [],
                    )

                # NOTE (2026-08-16 follow-up): tried a Guard 3 here — same exact
                # event_date as the matched tally + differing numbers => NEW instead of
                # UPDATE, to close the gap where detect_contradiction()'s numeric-conflict
                # branch can never fire from this call site (alpha.event_class is always
                # "tally" here, so contradiction.py's own is_tally exemption always
                # suppresses it — it can only ever catch a polarity flip from Guard 2
                # above, never a number clash). Reverted: it broke
                # test_ic1_real_revision_still_updates and its spelled-out-number
                # sibling, both of which encode a real, legitimate pattern (a tally
                # genuinely updated twice on the same calendar date — e.g. a morning
                # report of 59 vessels revised to 63 that afternoon). Same-day numeric
                # differences on a tally-classed pair are genuinely ambiguous between
                # "conflicting report" and "same-day revision" with no reliable
                # deterministic signal available at this layer to tell them apart —
                # this needs either richer signal (e.g. Alpha.context reaching this
                # decision) or judgment, not a blunt date-equality rule. Left as a real,
                # open gap (NUMERIC_CONTRADICTION_EVASION's C8-03/07/09) rather than
                # trading a known regression for a known fix.
                logger.info(
                    f"{log_prefix} → TALLY-UPDATE (IC1: entity-overlap match → "
                    f"'{tally_match.alpha_text[:60]}')"
                )
                return (
                    AlphaDecision(
                        alpha=alpha,
                        decision=DecisionType.UPDATE,
                        similarity_score=1.0,
                        matched_alpha_id=tally_match.id,
                        reasoning=(
                            "IC1 tally-collapse: cumulative running total on the same "
                            "entity-set — updating the existing tally in place."
                        ),
                        delta=alpha.alpha_text,
                    ),
                    [],
                )

        # Step 2 - Fetch similar facts from the Ledger, plus this batch's own
        # already-decided NEW/UPDATE alphas (see extra_pool docstring above).
        # Merged in BEFORE every check below (contradiction, raw-cosine auto-merge,
        # IC3, same-day, auto-merge/grey-zone thresholding) so a same-batch
        # near-duplicate is treated identically to a DB-stored one.
        raw_matches = self._fetch_matches(alpha, topic_id)
        if extra_pool:
            raw_matches = raw_matches + self._pool_matches(alpha, extra_pool)
            raw_matches.sort(key=lambda x: x[1], reverse=True)

        # Step 2b — IC4 contradiction flag (V3_CONTRADICTION_FLAG). A fact that contradicts
        # an existing one (Hormuz open/closed; toll 3,912 vs 3,468) is NOT a duplicate — flag
        # the pair and force NEW, so this runs BEFORE the raw-cosine/same-day fast-paths below.
        if settings.V3_CONTRADICTION_FLAG:
            for match, _score in raw_matches:
                reason = detect_contradiction(
                    alpha.alpha_text, alpha.entities, alpha.event_date, alpha.event_class,
                    match.alpha_text, match.entities, match.event_date, match.event_class,
                )
                if reason:
                    alpha.contradicts_id = match.id
                    alpha.contradiction_note = reason
                    logger.info(
                        f"{log_prefix} → CONTRADICTION-NEW (vs '{match.alpha_text[:50]}': {reason})"
                    )
                    return (
                        AlphaDecision(
                            alpha=alpha,
                            decision=DecisionType.NEW,
                            matched_alpha_id=match.id,
                            reasoning=f"IC4 contradiction — {reason}. Stored as NEW and flagged.",
                        ),
                        [],
                    )

        # Step 2c — raw-cosine auto-merge fast-path (always on, no flag).
        # Diagnosed 2026-07-22 on live data: AUTO_MERGE_THRESHOLD (below, Step 3) is tested
        # against the TEMPORALLY-ADJUSTED score, and event_date extraction can drift by
        # days-to-weeks across re-reportings of the identical fact — decaying even a raw
        # 1.0 match below threshold. Confirmed live example: "Twelve IDF soldiers and 23
        # civilians have been killed..." stored twice, verbatim, with event_date 24 days
        # apart. Near-identical wording is stronger duplicate evidence than a shakily
        # extracted date, so bypass temporal adjustment entirely at this confidence level.
        for match, raw_score in raw_matches:
            if raw_score >= AUTO_MERGE_THRESHOLD:
                # Guard (Stage 2, 2026-08-16, behind V3_DIGIT_GUARD): near-identical wording
                # can still carry a real numeric change (a same-template revision). Do NOT
                # fall through to standard temporal-adjusted zoning on a mismatch — that
                # reintroduces the exact date-drift bug this gate exists to route around (see
                # the gate's own docstring above). Force this specific candidate straight to
                # the Judge LLM instead, un-adjusted. V3_DIGIT_GUARD=False reverts to the
                # pre-Stage-2 behavior: always auto-merge at this threshold, no number check.
                if settings.V3_DIGIT_GUARD and (
                    _normalized_numbers(alpha.alpha_text) != _normalized_numbers(match.alpha_text)
                ):
                    logger.info(
                        f"{log_prefix} → RAW-COSINE-NUMBER-MISMATCH "
                        f"(raw_sim={raw_score:.3f} >= {AUTO_MERGE_THRESHOLD} but numbers "
                        "differ) — routing to Judge LLM instead of auto-merge"
                    )
                    return None, [(match, raw_score)]

                logger.info(
                    f"{log_prefix} → RAW-COSINE-DUPLICATE "
                    f"(raw_sim={raw_score:.3f} >= {AUTO_MERGE_THRESHOLD}, "
                    "bypassing temporal adjustment)"
                )
                return (
                    AlphaDecision(
                        alpha=alpha,
                        decision=DecisionType.DUPLICATE,
                        similarity_score=raw_score,
                        matched_alpha_id=match.id,
                        reasoning=(
                            f"Raw-cosine auto-merge: {raw_score:.3f} >= {AUTO_MERGE_THRESHOLD} "
                            "— near-identical text regardless of event_date."
                        ),
                    ),
                    [(match, raw_score)],
                )

        # Step 3 - Apply temporal (and optionally entity) adjustment to each raw score
        adjusted: List[Tuple[Alpha, float]] = []
        for match, score in raw_matches:
            adj = adjusted_similarity(score, alpha.event_date, match.event_date)
            if settings.V3_ENTITY_DEDUP:
                # Penalise / reward based on entity overlap: no-overlap → 20% penalty,
                # full-overlap → no change, neutral (empty entities) → 10% penalty.
                e_factor = 0.80 + 0.20 * entity_overlap(alpha.entities, match.entities)
                adj *= e_factor
            adjusted.append((match, adj))

        # Step 3b — IC3 same-event fast-path: DELETED (Stage 2, 2026-08-16).
        # Was: V3_ENTITY_DEDUP triple gate (entity_overlap >= 0.80, temporal >= 0.97,
        # raw sim >= 0.50) → auto-DUPLICATE without an LLM call. Stage 1 Experiment 4
        # (docs/benchmarks/2026-08-13_stage1-validation.md) confirmed on real production
        # data that every one of its 30 measurable firings — right AND wrong — lands
        # back in the grey zone [0.75, 0.97) once this bypass is removed: none are lost
        # to AUTO_NEW, none slip past the Judge via AUTO_MERGE. Its correct calls were
        # redundant with standard zoning; its wrong calls (100% of them: antonym flips
        # and numeric evasions, per the red-team audit's per-gate breakdown) were
        # structurally guaranteed by its own design — same actors/day/cosine is exactly
        # what a paraphrase AND an antonym-flip both look like to this gate. The
        # separate Step 3 entity-overlap MULTIPLIER just above (not this fast-path) is
        # unaffected and stays exactly as-is under V3_ENTITY_DEDUP.

        # Step 3c — same-day near-identical fast-path (always on, no flag gates the
        # gate itself — V3_DIGIT_GUARD only gates its NUMBER/ENTITY checks, below).
        # Validated in prod (2026-07-06): cross-scan duplicates at cosine 0.93-0.96
        # with the SAME event_date slip past the Judge LLM ("Khamenei's three sons
        # attended a funeral" stored twice at 0.959). Same date + very high vector
        # similarity is decisive — UNLESS the numbers differ: a same-day tally
        # revision ("toll rises 20 → 25") must stay with the Judge as UPDATE.
        # Stage 2 (2026-08-16, behind V3_DIGIT_GUARD): the digit-only check is
        # replaced with _normalized_numbers() (Stage 1 Experiment 2 found the old
        # _digit_runs() equality blind to spelled-out numbers), and an entity/subject-
        # overlap guard is added so a same-template-different-subject pair can't
        # auto-merge on matching numbers alone. Threshold is 0.80, not a looser 0.5:
        # Stage 3's holdout adversarial set caught a 0.5 threshold passing a real
        # false-merge ("Houthi rebels attacked ... Hodeidah" vs "... al-Makha" — same
        # org + same country entities overlap at 0.5 even though the actual
        # differentiating entity, the specific port, differs). 0.80 matches the
        # deleted IC3 gate's own bar (validated by that gate's 0 wrong calls on true
        # duplicates in the 2026-08-13 red-team audit) — reusing an already-proven
        # number rather than picking a new one. entity_overlap() is neutral — 0.5,
        # fails this bar — when entities are empty on either side, same as its
        # existing behavior elsewhere, so an under-tagged fact routes to the Judge
        # instead of auto-merging blind. V3_DIGIT_GUARD=False reverts both checks to
        # the pre-Stage-2 behavior: raw _digit_runs() equality, no entity guard.
        for match, raw_score in raw_matches:
            if settings.V3_DIGIT_GUARD:
                numbers_match = _normalized_numbers(alpha.alpha_text) == _normalized_numbers(match.alpha_text)
                subject_match = entity_overlap(alpha.entities, match.entities) >= 0.80
            else:
                numbers_match = _digit_runs(alpha.alpha_text) == _digit_runs(match.alpha_text)
                subject_match = True  # pre-Stage-2 behavior had no entity guard
            # 2026-08-16 follow-up: numbers_match alone doesn't catch a same-value,
            # opposite-direction reversal ("increased by 5%" vs "dropped by 5%" — both
            # normalize to {5.0}). Gated behind V3_DIGIT_GUARD alongside the other two
            # Stage-2 guards on this gate; off reverts to the pre-fix behavior.
            direction_ok = not (settings.V3_DIGIT_GUARD and _direction_conflict(alpha.alpha_text, match.alpha_text))
            if (
                raw_score >= SAME_DAY_DUP_THRESHOLD
                and temporal_overlap(alpha.event_date, match.event_date) >= 0.97
                and numbers_match
                and subject_match
                and direction_ok
            ):
                logger.info(
                    f"{log_prefix} → SAME-DAY-DUPLICATE "
                    f"(sim={raw_score:.3f}, same event_date, same numbers, same subject)"
                )
                return (
                    AlphaDecision(
                        alpha=alpha,
                        decision=DecisionType.DUPLICATE,
                        similarity_score=raw_score,
                        matched_alpha_id=match.id,
                        reasoning=(
                            f"Same-day near-identical: sim={raw_score:.3f}, same "
                            "event_date, same numbers, same subject — same event reworded."
                        ),
                    ),
                    adjusted or [(match, raw_score)],
                )

        adjusted.sort(key=lambda x: x[1], reverse=True)

        # Step 4/5 - Fast paths (no LLM needed)
        if not adjusted:
            logger.info(f"{log_prefix} → AUTO-NEW (zero ledger matches)")
            return (
                AlphaDecision(
                    alpha=alpha,
                    decision=DecisionType.NEW,
                    reasoning="No similar facts found in ledger.",
                ),
                [],
            )

        top_match, top_score = adjusted[0]

        if top_score >= AUTO_MERGE_THRESHOLD:
            logger.info(
                f"{log_prefix} → AUTO-DUPLICATE (score={top_score:.3f} >= {AUTO_MERGE_THRESHOLD})"
            )
            return (
                AlphaDecision(
                    alpha=alpha,
                    decision=DecisionType.DUPLICATE,
                    similarity_score=top_score,
                    matched_alpha_id=top_match.id,
                    reasoning=f"Auto-merge: adjusted score {top_score:.3f} exceeds {AUTO_MERGE_THRESHOLD}.",
                ),
                adjusted,
            )

        if top_score < GREY_ZONE_MIN:
            logger.info(f"{log_prefix} → AUTO-NEW (score={top_score:.3f} < {GREY_ZONE_MIN})")
            return (
                AlphaDecision(
                    alpha=alpha,
                    decision=DecisionType.NEW,
                    similarity_score=top_score,
                    matched_alpha_id=top_match.id,
                    reasoning=f"Highest adjusted score {top_score:.3f} below grey-zone threshold {GREY_ZONE_MIN}.",
                ),
                adjusted,
            )

        # Grey zone — caller runs the Judge LLM.
        return None, adjusted

    def _grey_zone_decision(
        self,
        alpha: Alpha,
        decision: DecisionType,
        delta: Optional[str],
        top_match: Alpha,
        top_score: float,
    ) -> AlphaDecision:
        """Build the AlphaDecision for a fact resolved by the Judge LLM."""
        logger.info(
            f"[ARBITER] '{alpha.alpha_text[:60]}...' → Judge decision: {decision.value}"
            + (f" | delta: {delta}" if delta else "")
        )
        return AlphaDecision(
            alpha=alpha,
            decision=decision,
            similarity_score=top_score,
            matched_alpha_id=top_match.id,
            reasoning=f"Judge LLM decision. Top match score: {top_score:.3f}.",
            delta=delta,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _ensure_embedding(self, alpha: Alpha, log_prefix: str) -> Alpha:
        """Generate embedding if not already attached to the Alpha."""
        if alpha.embedding:
            return alpha
        try:
            alpha.embedding = self.ledger.llm.embed(alpha.alpha_text)
        except Exception as exc:
            logger.error(f"{log_prefix} Embedding failed: {exc}")
            alpha.embedding = None
        return alpha

    def _pool_matches(
        self, alpha: Alpha, pool: List[Alpha]
    ) -> List[Tuple[Alpha, float]]:
        """Raw cosine similarity between `alpha` and each in-memory batch-pool alpha.

        Mirrors find_similar()'s own floor (LEDGER_FETCH_THRESHOLD) so pool candidates
        get the same relevance bar as DB-fetched ones instead of flooding the
        contradiction/raw-cosine/same-day checks with noise.
        """
        matches: List[Tuple[Alpha, float]] = []
        for cand in pool:
            if cand is alpha or cand.id == alpha.id or not cand.embedding or not alpha.embedding:
                continue
            score = _cosine(alpha.embedding, cand.embedding)
            if score >= LEDGER_FETCH_THRESHOLD:
                matches.append((cand, score))
        return matches

    def _fetch_matches(
        self, alpha: Alpha, topic_id: Optional[str]
    ) -> List[Tuple[Alpha, float]]:
        """Fetch the closest known facts from the ledger."""
        try:
            return self.ledger.find_similar(
                embedding=alpha.embedding,
                topic_id=topic_id,
                limit=LEDGER_FETCH_LIMIT,
                threshold=LEDGER_FETCH_THRESHOLD,
            )
        except Exception as exc:
            logger.error(f"Ledger fetch failed: {exc}. Treating as zero matches.")
            return []
