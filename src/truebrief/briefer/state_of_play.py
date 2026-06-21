"""
State of Play - briefer/state_of_play.py  (IC7 — architecture §7.4)

Synthesizes the topic-level "state of play" block shown at the top of the topic
view: one current-situation line + a 3–6 item checklist of open threads, each
tagged agreed / contested / postponed / escalating and anchored to stored facts.

Key properties (per architecture §7.4):
  - Generated ONLY from stored facts + their sources — no ungrounded prediction.
  - Regenerated ONLY when a state_change fact lands (cheap, ~1 LLM call).
  - A bounded living-summary: re-derived from facts each time, never recursively
    rewritten (no telephone-game drift).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional

from truebrief.llm.client import LLMClient

logger = logging.getLogger(__name__)

# The only statuses a thread may carry. Anything else from the LLM is dropped.
VALID_STATUSES = ("agreed", "contested", "postponed", "escalating")

# Hard caps so the block stays a glanceable header, not a wall of text.
MAX_THREADS = 6
MAX_FACTS_IN = 40


class StateOfPlayGenerator:
    """Builds the grounded status block from a topic's stored facts."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()

    def generate(self, facts: List[dict], topic_name: str) -> Optional[dict]:
        """
        Args:
            facts: stored facts, each a dict with at least `alpha_text`; optional
                   `event_class`, `event_date`, `source_domain`. Most-recent-first
                   is preferred but not required.
            topic_name: human-readable topic name for the header.

        Returns:
            {"situation": str, "threads": [{label,status,note}], "generated_at": iso}
            or None if there are no facts / the LLM call or parse fails.
        """
        if not facts:
            return None

        prompt = self._get_prompt(facts[:MAX_FACTS_IN], topic_name)
        try:
            raw = self.llm.call(
                step_name="state_of_play",
                prompt=prompt,
                json_mode=True,
                system_prompt=(
                    "You are an intelligence analyst writing a grounded status board. "
                    "You report ONLY what the facts establish. You never predict."
                ),
            )
        except Exception as exc:
            logger.warning(f"[STATE-OF-PLAY] LLM call failed: {exc}")
            return None

        parsed = self._parse(raw)
        if parsed is None:
            logger.warning("[STATE-OF-PLAY] Could not parse a valid block from LLM output.")
            return None

        parsed["generated_at"] = datetime.now(timezone.utc).isoformat()
        return parsed

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _get_prompt(self, facts: List[dict], topic_name: str) -> str:
        today = datetime.now().strftime("%B %d, %Y")
        payload = json.dumps(
            [
                {
                    "fact": f.get("alpha_text", ""),
                    "significance": f.get("event_class") or "development",
                    "date": str(f.get("event_date") or ""),
                    "source": f.get("source_domain") or "",
                }
                for f in facts
            ],
            indent=2,
        )
        return f"""
Build a "state of play" status board for this topic from the FACTS below — and ONLY
from those facts. This is a glanceable header that answers "where do things stand right now?"

TOPIC: {topic_name}
DATE: {today}

FACTS (most significant / recent first):
{payload}

Produce JSON with this EXACT shape:
{{
  "situation": "ONE or TWO sentences naming the current overall state — the single most
                important reality right now, grounded in the facts.",
  "threads": [
    {{"label": "<short name of an open thread>",
      "status": "<one of: agreed | contested | postponed | escalating>",
      "note": "<≤8 words anchoring it to the facts, e.g. 'signed Jun 17'>"}}
  ]
}}

RULES:
- Use ONLY the facts provided. Do NOT add outside knowledge. Do NOT predict or speculate.
- "status" MUST be exactly one of: agreed, contested, postponed, escalating.
    agreed     = settled / signed / in force.
    contested  = disputed, conflicting claims, or violated.
    postponed  = delayed, paused, awaiting.
    escalating = actively worsening / new hostilities.
- 3 to {MAX_THREADS} threads, the most consequential first. No filler threads.
- "note" must be short and tied to a fact (a date or a concrete detail). No prose.
- If a fact set supports no clear thread, omit it rather than inventing one.
- Output ONLY the JSON object. No markdown fences, no commentary.
"""

    def _parse(self, raw: str) -> Optional[dict]:
        """Extract + validate the JSON block. Drops threads with bad statuses."""
        if not raw:
            return None
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except Exception:
            return None

        situation = str(data.get("situation", "")).strip()
        threads_in = data.get("threads", [])
        if not isinstance(threads_in, list):
            threads_in = []

        threads_out = []
        for t in threads_in:
            if not isinstance(t, dict):
                continue
            status = str(t.get("status", "")).strip().lower()
            label = str(t.get("label", "")).strip()
            if status not in VALID_STATUSES or not label:
                continue
            threads_out.append(
                {"label": label, "status": status, "note": str(t.get("note", "")).strip()}
            )
            if len(threads_out) >= MAX_THREADS:
                break

        # A block with neither a situation line nor any valid thread is useless.
        if not situation and not threads_out:
            return None

        return {"situation": situation, "threads": threads_out}
