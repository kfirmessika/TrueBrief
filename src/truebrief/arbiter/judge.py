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

_PROMPT_TEMPLATE = """\
NEW FACT (just extracted from an article):
  "{new_fact}"
  Entities: {new_entities}
  Event date: {new_date}

CLOSEST KNOWN FACTS (from memory, ranked by similarity):
{matches_block}

Choose exactly ONE decision and output ONLY valid JSON:

If MERGE (duplicate/trivial restatement - no new information):
  {{"decision": "MERGE"}}

If UPDATE (new information that extends or corrects a known fact):
  {{"decision": "UPDATE", "delta": "One sentence describing exactly what is new."}}

If NEW (no existing knowledge matches - brand new information):
  {{"decision": "NEW"}}
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

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _build_prompt(self, new_alpha: Alpha, matches: List[Tuple[Alpha, float]]) -> str:
        """Construct the full classification prompt."""
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

        return _PROMPT_TEMPLATE.format(
            new_fact=new_alpha.alpha_text,
            new_entities=new_entities_str,
            new_date=new_date_str,
            matches_block=matches_block,
        )

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
