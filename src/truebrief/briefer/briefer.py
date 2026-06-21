"""
Briefer - briefer/briefer.py

Takes new and updated Alphas and generates a clean, readable report.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import List, Optional

from truebrief.llm.client import LLMClient
from truebrief.models.alpha import AlphaDecision, DecisionType

logger = logging.getLogger(__name__)

class Briefer:
    """
    Pillar 5: Output.
    Generates the final human-readable report from the delta facts.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()

    def generate(
        self,
        decisions: List[AlphaDecision],
        topic_name: str,
        situation: Optional[str] = None,
    ) -> str:
        """
        Takes a list of Arbiter decisions and formats a brief.
        Only NEW and UPDATE decisions are included.
        situation: if provided (from IC7 state-of-play), anchors the lede synthesis.
        """
        # Filter out duplicates
        active_decisions = [d for d in decisions if d.decision in (DecisionType.NEW, DecisionType.UPDATE)]

        if not active_decisions:
            logger.info("No new facts to brief. Generating empty brief.")
            return ""

        prompt = self._get_prompt(active_decisions, topic_name, situation=situation)
        
        try:
            logger.info(f"Generating brief for topic: {topic_name}")
            response_text = self.llm.call(
                step_name="briefer",
                prompt=prompt,
                json_mode=False,
                system_prompt="You are an elite intelligence briefer. Your job is to format raw facts into a scannable, highly readable report."
            )
            return response_text.strip()
        except Exception as e:
            logger.error(f"Failed to generate brief: {e}")
            raise


    def _get_prompt(
        self,
        decisions: List[AlphaDecision],
        topic_name: str,
        situation: Optional[str] = None,
    ) -> str:
        today = datetime.now().strftime("%B %d, %Y")

        # Prepare facts payload. Facts arrive PRE-SORTED by significance (IC2,
        # runner step 5d) — preserve that order so the briefer leads with the lede.
        new_facts = []
        update_facts = []

        for d in decisions:
            fact_data = {
                "fact": d.alpha.alpha_text,
                "context": d.alpha.context,
                "significance": d.alpha.event_class or "development",
                "corroborating_sources": max(int(d.alpha.verified_count or 0), 1),
                "source": f"{d.alpha.source_name} ({d.alpha.source_url})",
            }
            if d.decision == DecisionType.NEW:
                new_facts.append(fact_data)
            else:
                # For UPDATES, surface the delta (what changed) explicitly.
                fact_data["whats_new"] = d.delta or d.alpha.alpha_text
                update_facts.append(fact_data)

        payload = json.dumps({
            "NEW_STORIES": new_facts,
            "UPDATES": update_facts
        }, indent=2)

        situation_hint = ""
        if situation:
            situation_hint = (
                f'\nCURRENT SITUATION (IC7 anchor — use this as the basis for your '
                f'"📌 Bottom line"; the new facts below update it):\n{situation}\n'
            )

        return f"""
Generate a clean, professional intelligence brief based ONLY on the provided facts.
Maximize signal-to-noise: lead with the single most important development, group
related facts, and never repeat the same point.

TOPIC: {topic_name}
DATE: {today}{situation_hint}
INPUT FACTS (already ordered most-significant first; "significance" ranks them:
state_change > escalation > development > incremental > tally > routine):
{payload}

FORMAT — follow this EXACT structure:

📋 TrueBrief | [Topic Name] | [Date]

**📌 Bottom line:** [ONE sentence naming the single most important CURRENT development across all facts — this is the lede a reader sees first.]

🆕 NEW STORIES ([Count])
━━━━━━━━━━━━━━━━━━━━━━━━━━
**Story Title**
• The fact, with its context woven in as natural prose (one flowing sentence or two — NOT labelled fragments). → Sources: [domain.com](url)

📈 UPDATES ([Count])
━━━━━━━━━━━━━━━━━━━━━━━━━━
**Story Title**
• What changed, stated directly, with the prior situation woven in as prose. → Sources: [domain.com](url)

RULES:
- Do NOT hallucinate. Use ONLY the facts in the JSON payload.
- LEAD WITH THE LEDE: the "📌 Bottom line" must name the most consequential current
  development (prefer a state_change / escalation over a tally or routine item).
- PRESERVE the given order — the most significant facts come first; render them first.
- WEAVE context as prose. Do NOT prefix bullets with rigid all-caps labels (no
  "whats-new" / "full-context" style tags) — write flowing sentences instead.
- COLLAPSE running tallies: if several facts are successive counts of the same metric
  (casualty totals, fund sizes), render ONE bullet with the latest figure — not one per update.
- Group closely related facts from the same story under one **heading**, each its own bullet.
- EVERY bullet ends with → Sources: [domain.com](url) using the exact url from that fact's
  "source" field. Use the markdown link format [name](url).
- ONE chip per OUTLET: if a bullet draws on several articles from the SAME domain, cite that
  domain ONCE. Only list multiple sources when they are DIFFERENT outlets.
- If a fact has corroborating_sources > 1, you may append " (N sources)" to the bullet text.
- If a section (NEW STORIES or UPDATES) has 0 items, omit that section AND its header entirely.
- Concise, punchy, professional. NO filler.
"""

if __name__ == "__main__":
    from truebrief.models.alpha import Alpha
    logging.basicConfig(level=logging.INFO)
    
    briefer = Briefer()
    
    a1 = Alpha(alpha_text="Tesla announced a new Gigafactory in Indonesia.", entities=["Tesla"], source_name="Reuters", source_url="http://reuters.com")
    d1 = AlphaDecision(alpha=a1, decision=DecisionType.NEW)
    
    a2 = Alpha(alpha_text="Tesla Q3 Revenue beat expectations by $1.1B.", entities=["Tesla"], source_name="CNBC", source_url="http://cnbc.com", context="Tesla revenue updates")
    d2 = AlphaDecision(alpha=a2, decision=DecisionType.UPDATE)
    
    print(briefer.generate([d1, d2], "Tesla & EVs"))
