"""
Judge LLM - arbiter/judge.py

The LLM arbiter for ambiguous cases. Called by the Arbiter ONLY when the
vector similarity score falls in the "grey zone" (between STRONG_MATCH and AUTO-NEW).

Decision tree:
  MERGE  - Same fact restated. No new information. Don't store.
  UPDATE - New information that extends or corrects a known fact. Store + add delta to brief.
  NEW    - Unrelated to known facts. Store as fresh fact.

Design principles:
  - Parse failures trigger 1 retry, then fall back to NEW (err on over-reporting, not under)
  - Entity mismatch in prompt context steers LLM toward NEW
  - JSON-only output enforced via Gemini response_mime_type
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, date
from typing import List, Optional, Tuple

from truebrief.llm.client import LLMClient, LLMError
from truebrief.models.alpha import Alpha, DecisionType

logger = logging.getLogger(__name__)


def _format_event_date(event_date) -> str:
    """Format event_date (datetime, date, or ISO string from DB) as YYYY-MM-DD."""
    if event_date is None:
        return "unknown"
    if isinstance(event_date, (datetime, date)):
        return event_date.strftime("%Y-%m-%d")
    if isinstance(event_date, str):
        try:
            return datetime.fromisoformat(event_date.replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except Exception:
            return event_date
    return str(event_date)

# Label descriptions sent to the LLM alongside similarity scores
_SCORE_LABELS = {
    "IDENTICAL":     (0.90, 1.00),
    "STRONG_MATCH":  (0.75, 0.90),
}


def _score_label(score: float) -> str:
    """Map a similarity score to a human-readable label for the prompt."""
    if score >= 0.90:
        return "IDENTICAL"
    if score >= 0.75:
        return "STRONG_MATCH"
    return "RELATED"


_SYSTEM_PROMPT = """\
You are a precision news intelligence arbiter. Your job is to determine whether a new fact
duplicates, updates, or is entirely different from known stored facts.

Rules (apply strictly):
1. A change in numbers (price, %, revenue, count, date) = UPDATE, never MERGE.
2. If the entities are different companies/people/products → lean NEW.
3. Editorial rephrasing of the exact same factual claim → MERGE.
4. When uncertain between UPDATE and MERGE → choose UPDATE (false negatives are worse).
5. Output ONLY valid JSON. No explanation outside the JSON object.
"""

_CASE_BLOCK = """\
NEW FACT (just extracted from an article):
  "{new_fact}"
  Entities: {new_entities}
  Event date: {new_date}

CLOSEST KNOWN FACTS (from memory, ranked by similarity):
{matches_block}"""

_PROMPT_TEMPLATE = _CASE_BLOCK + """

Choose exactly ONE decision and output ONLY valid JSON:

If MERGE (duplicate/trivial restatement - no new information):
  {{"decision": "MERGE"}}

If UPDATE (new information that extends or corrects a known fact):
  {{"decision": "UPDATE", "delta": "One sentence stating exactly the new verifiable fact."}}
  The delta must be a FACT, not characterization: state what changed (the new status, number,
  or action), NOT a read of its trajectory or significance. Do NOT use evaluative verbs like
  "progressed/advanced/improved/worsened/escalated" or phrases like "in a major step".
  BAD : "Talks have progressed to peace-specific negotiations."
  GOOD: "Lebanon and Israel held a round of negotiations focused on a peace agreement on June 25."

If NEW (no existing knowledge matches - brand new information):
  {{"decision": "NEW"}}
"""

# Batch prompt — N self-contained cases judged in one call (V3_BATCH_JUDGE).
# Safe to batch because each case is independent (no shared state between facts).
_BATCH_INSTRUCTIONS = """\

==============================================================================
You are given {n} INDEPENDENT cases above, numbered CASE 1 .. CASE {n}.
For EACH case choose exactly ONE decision: MERGE, UPDATE, or NEW (same rules as
a single case). Output ONLY a valid JSON array with exactly {n} objects, one per
case, in order. Each object MUST include its 1-based "case" number:

[
  {{"case": 1, "decision": "MERGE"}},
  {{"case": 2, "decision": "UPDATE", "delta": "One sentence on what is new."}},
  {{"case": 3, "decision": "NEW"}}
]
"""


class JudgeLLM:
    """
    Calls the LLM to decide MERGE / UPDATE / NEW for ambiguous alpha comparisons.

    Usage:
        judge = JudgeLLM()
        decision, delta = judge.call(new_alpha, matches)
        # decision: DecisionType.MERGE | UPDATE | NEW
        # delta:    str | None  (only present on UPDATE)
    """

    MAX_PARSE_RETRIES = 2

    def __init__(self, llm: Optional[LLMClient] = None) -> None:
        self.llm = llm or LLMClient()

    def call(
        self,
        new_alpha: Alpha,
        matches: List[Tuple[Alpha, float]],  # (alpha, adjusted_score)
    ) -> Tuple[DecisionType, Optional[str]]:
        """
        Run the Judge LLM for an ambiguous fact.

        Args:
            new_alpha: The incoming fact being evaluated.
            matches:   Top N similar known facts with their adjusted scores.

        Returns:
            (DecisionType, delta_sentence | None)
        """
        prompt = self._build_prompt(new_alpha, matches)

        for attempt in range(1, self.MAX_PARSE_RETRIES + 1):
            try:
                raw = self.llm.call(
                    step_name="arbiter",
                    prompt=prompt,
                    json_mode=True,
                    system_prompt=_SYSTEM_PROMPT,
                )
                return self._parse_response(raw)

            except (json.JSONDecodeError, KeyError, ValueError) as parse_err:
                logger.warning(
                    f"Judge parse failure (attempt {attempt}/{self.MAX_PARSE_RETRIES}): {parse_err}"
                )
                if attempt == self.MAX_PARSE_RETRIES:
                    logger.error("Judge LLM: all parse retries exhausted. Defaulting to NEW.")
                    return DecisionType.NEW, None

            except LLMError as llm_err:
                logger.error(f"Judge LLM call failed: {llm_err}. Defaulting to NEW.")
                return DecisionType.NEW, None

        # Should never reach here, but keep the type checker happy
        return DecisionType.NEW, None

    def call_batch(
        self,
        cases: List[Tuple[Alpha, List[Tuple[Alpha, float]]]],
    ) -> List[Tuple[DecisionType, Optional[str]]]:
        """
        Judge several grey-zone facts in a SINGLE LLM call (V3_BATCH_JUDGE).

        Each case is independent (no shared state between facts), so batching is
        safe — unlike extraction. Saves call count on productive scans.

        Args:
            cases: list of (new_alpha, adjusted_matches) tuples.

        Returns:
            A list of (DecisionType, delta|None) in the SAME order as `cases`.

        On any batch failure (LLM error, unparseable, or count mismatch) this
        falls back to judging each case with the single-call path, so the result
        is never worse than calling .call() N times.
        """
        if not cases:
            return []
        if len(cases) == 1:
            new_alpha, matches = cases[0]
            return [self.call(new_alpha, matches)]

        prompt = self._build_batch_prompt(cases)
        try:
            raw = self.llm.call(
                step_name="arbiter",
                prompt=prompt,
                json_mode=True,
                system_prompt=_SYSTEM_PROMPT,
            )
            parsed = self._parse_batch_response(raw, len(cases))
            if parsed is not None:
                return parsed
            logger.warning(
                "Judge batch: response count mismatch or parse issue; "
                "falling back to per-case calls."
            )
        except LLMError as llm_err:
            logger.error(f"Judge batch LLM call failed: {llm_err}. Falling back to per-case.")

        # Fallback: judge each case independently (preserves quality).
        return [self.call(new_alpha, matches) for new_alpha, matches in cases]

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _format_case_block(self, new_alpha: Alpha, matches: List[Tuple[Alpha, float]]) -> str:
        """Render the NEW FACT + CLOSEST KNOWN FACTS block for one comparison case.

        Shared by the single-call prompt and each numbered case in a batch prompt.
        """
        new_date_str = _format_event_date(new_alpha.event_date)
        new_entities_str = ", ".join(new_alpha.entities) if new_alpha.entities else "unknown"

        # Build the matches block (up to 3 shown for context)
        lines = []
        for i, (match, score) in enumerate(matches[:3], start=1):
            label = _score_label(score)
            match_date = _format_event_date(match.event_date)
            match_entities = ", ".join(match.entities) if match.entities else "unknown"
            lines.append(
                f"  {i}. [{label} {score:.2f}] \"{match.alpha_text}\"\n"
                f"     Entities: {match_entities} | Event date: {match_date}"
            )

        matches_block = "\n".join(lines) if lines else "  (none)"

        return _CASE_BLOCK.format(
            new_fact=new_alpha.alpha_text,
            new_entities=new_entities_str,
            new_date=new_date_str,
            matches_block=matches_block,
        )

    def _build_prompt(self, new_alpha: Alpha, matches: List[Tuple[Alpha, float]]) -> str:
        """Construct the full single-case classification prompt (block + instructions)."""
        block = self._format_case_block(new_alpha, matches)
        # _PROMPT_TEMPLATE == _CASE_BLOCK + instructions tail; reuse the tail only.
        return block + _PROMPT_TEMPLATE[len(_CASE_BLOCK):]

    def _build_batch_prompt(
        self, cases: List[Tuple[Alpha, List[Tuple[Alpha, float]]]]
    ) -> str:
        """Construct one prompt holding all N numbered cases + batch instructions."""
        parts = []
        for idx, (new_alpha, matches) in enumerate(cases, start=1):
            parts.append(f"CASE {idx}:\n{self._format_case_block(new_alpha, matches)}")
        body = "\n\n".join(parts)
        return body + _BATCH_INSTRUCTIONS.format(n=len(cases))

    def _parse_batch_response(
        self, raw: str, expected: int
    ) -> Optional[List[Tuple[DecisionType, Optional[str]]]]:
        """
        Parse the batch JSON array into N (DecisionType, delta) tuples in order.

        Returns None if the response can't be trusted (not a list, wrong length,
        or unparseable) so the caller can fall back to per-case judging.
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None

        # Tolerate {"results": [...]} or {"cases": [...]} wrappers.
        if isinstance(data, dict):
            for key in ("results", "cases", "decisions"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break

        if not isinstance(data, list) or len(data) != expected:
            return None

        # Order by explicit 1-based "case" index when present; else trust array order.
        if all(isinstance(d, dict) and isinstance(d.get("case"), int) for d in data):
            data = sorted(data, key=lambda d: d["case"])

        results: List[Tuple[DecisionType, Optional[str]]] = []
        for item in data:
            if not isinstance(item, dict):
                return None
            decision_str = str(item.get("decision", "")).upper()
            if decision_str == "MERGE":
                results.append((DecisionType.DUPLICATE, None))
            elif decision_str == "UPDATE":
                delta = str(item.get("delta", "")).strip()
                if not delta:
                    # UPDATE with no delta is meaningless — treat as duplicate (same
                    # rule as the single-call path).
                    results.append((DecisionType.DUPLICATE, None))
                else:
                    results.append((DecisionType.UPDATE, delta))
            elif decision_str == "NEW":
                results.append((DecisionType.NEW, None))
            else:
                return None  # unknown decision → distrust the whole batch
        return results

    @staticmethod
    def _parse_response(raw: str) -> Tuple[DecisionType, Optional[str]]:
        """
        Parse the LLM's JSON response into (DecisionType, delta).

        Raises:
            json.JSONDecodeError: If response isn't valid JSON.
            ValueError:           If 'decision' field has an unexpected value.
        """
        data = json.loads(raw)
        decision_str = data.get("decision", "").upper()

        if decision_str == "MERGE":
            return DecisionType.DUPLICATE, None  # MERGE maps to DUPLICATE in our enum

        if decision_str == "UPDATE":
            delta = data.get("delta", "").strip()
            if not delta:
                logger.warning("Judge returned UPDATE with no delta. Treating as MERGE.")
                return DecisionType.DUPLICATE, None
            return DecisionType.UPDATE, delta

        if decision_str == "NEW":
            return DecisionType.NEW, None

        raise ValueError(f"Unexpected decision value from Judge LLM: '{decision_str}'")
