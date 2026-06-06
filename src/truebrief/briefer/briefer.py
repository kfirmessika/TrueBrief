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

    def generate(self, decisions: List[AlphaDecision], topic_name: str) -> str:
        """
        Takes a list of Arbiter decisions and formats a brief.
        Only NEW and UPDATE decisions are included.
        """
        # Filter out duplicates
        active_decisions = [d for d in decisions if d.decision in (DecisionType.NEW, DecisionType.UPDATE)]
        
        if not active_decisions:
            logger.info("No new facts to brief. Generating empty brief.")
            return ""

        prompt = self._get_prompt(active_decisions, topic_name)
        
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


    def _get_prompt(self, decisions: List[AlphaDecision], topic_name: str) -> str:
        today = datetime.now().strftime("%B %d, %Y")
        
        # Prepare facts payload
        new_facts = []
        update_facts = []
        
        for d in decisions:
            fact_data = {
                "fact": d.alpha.alpha_text,
                "context": d.alpha.context,
                "source": f"{d.alpha.source_name} ({d.alpha.source_url})"
            }
            if d.decision == DecisionType.NEW:
                new_facts.append(fact_data)
            else:
                update_facts.append(fact_data)

        payload = json.dumps({
            "NEW_STORIES": new_facts,
            "UPDATES": update_facts
        }, indent=2)

        return f"""
Generate a clean, professional intelligence brief based ONLY on the provided facts.

TOPIC: {topic_name}
DATE: {today}

INPUT FACTS:
{payload}

FORMAT REQUIREMENTS:
Follow this EXACT structure:

📋 TrueBrief | [Topic Name] | [Date]

🆕 NEW STORIES ([Count])
━━━━━━━━━━━━━━━━━━━━━━━━━━
**Story Title**
• Bullet fact one sentence. → Sources: [Source Name](url)
• Bullet fact two sentence. → Sources: [Source Name 1](url1), [Source Name 2](url2)

📈 UPDATES ([Count])
━━━━━━━━━━━━━━━━━━━━━━━━━━
**Story Title**
• WHAT'S NEW: The new delta fact. → Sources: [Source Name](url)
• FULL CONTEXT: Why this matters. → Sources: [Source Name](url)

RULES:
- Do NOT hallucinate. Use ONLY the facts provided in the JSON payload.
- EVERY bullet point MUST end with → Sources: [Source Name](url) — one per bullet, using the exact name and url from the "source" field of the fact that bullet is based on.
- Multiple sources for one bullet: → Sources: [Name 1](url1), [Name 2](url2)
- Each source must use the markdown link format [Name](url) with both name and url.
- If a section (NEW STORIES or UPDATES) has 0 items, omit that section entirely.
- Combine closely related facts from the same story under one **heading**, each as its own bullet with its own source.
- Keep it concise, punchy, and professional. NO filler text.
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
