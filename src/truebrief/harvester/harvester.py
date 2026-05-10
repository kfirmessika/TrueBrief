"""
Harvester - harvester/harvester.py

Extracts atomic facts (Alphas) from raw article text using the LLM.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import List, Optional

from dateutil.parser import parse as parse_date
from truebrief.llm.client import LLMClient
from truebrief.models.article import RawArticle
from truebrief.models.alpha import Alpha

logger = logging.getLogger(__name__)

class Harvester:
    """
    Pillar 2: Intelligence.
    Converts unstructured text into structured facts (Alphas).
    """

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self.llm = llm_client or LLMClient()

    def extract(self, article: RawArticle, topic_id: Optional[str] = None) -> List[Alpha]:
        """
        Extract facts from a single article.
        Returns a list of Alpha objects.
        Facts with confidence < 0.6 are dropped.
        """
        if not article.text:
            logger.warning(f"No text to harvest for article: {article.url}")
            return []

        prompt = self._get_prompt(article)
        
        try:
            response_text = self.llm.call(
                step_name="harvester",
                prompt=prompt,
                json_mode=True,
                system_prompt="You are a precision intelligence analyst. Extract every atomic, verifiable fact from this article into a structured JSON list."
            )
            
            # The LLM should return a JSON list of fact objects.
            # Handle potential dictionary wrapping if the model doesn't follow instructions perfectly.
            data = json.loads(response_text)
            
            fact_list = data
            if isinstance(data, dict):
                # Sometimes models wrap the list in a key like "facts" or "alphas"
                for key in ["facts", "alphas", "data"]:
                    if key in data and isinstance(data[key], list):
                        fact_list = data[key]
                        break
            
            if not isinstance(fact_list, list):
                logger.error(f"Harvester LLM did not return a list. Type: {type(fact_list)}")
                return []

            alphas: List[Alpha] = []
            for item in fact_list:
                if not isinstance(item, dict):
                    continue
                    
                confidence = float(item.get("confidence", 1.0))
                if confidence < 0.6:
                    continue  # Drop low confidence facts
                    
                # Parse the event date if provided and valid
                event_date = None
                raw_event_date = item.get("event_date")
                if raw_event_date and raw_event_date.lower() != "unknown":
                    try:
                        event_date = parse_date(raw_event_date)
                    except Exception:
                        pass # Keep it as None if unparseable

                # Create the Alpha model
                alpha = Alpha(
                    alpha_text=item.get("alpha_text", "").strip(),
                    entities=item.get("entities", []),
                    source_url=article.url,
                    source_name=article.source_name,
                    event_date=event_date,
                    context=item.get("context", ""),
                    confidence=confidence,
                    topic_id=topic_id
                )
                
                if alpha.alpha_text:
                    alphas.append(alpha)

            return alphas

        except Exception as e:
            logger.error(f"Harvester failed for article {article.url}: {e}")
            return []

    def _get_prompt(self, article: RawArticle) -> str:
        """Construct the prompt for fact extraction."""
        
        pub_date_str = article.published_at.strftime("%Y-%m-%d") if article.published_at else "Unknown"
        
        return f"""
ARTICLE PUBLISHED DATE: {pub_date_str}

ARTICLE TEXT:
{article.text}

TASK:
Extract every atomic, verifiable fact from this article into a structured JSON list.

For each fact extract:
1. "alpha_text": The fact as one clean standalone sentence.
2. "entities": List of named entities (companies, people, countries, products).
3. "event_date": When this HAPPENED (not when it was published).
   Convert relative dates ("yesterday", "last quarter") to YYYY-MM-DD
   using the ARTICLE PUBLISHED DATE as an anchor. If unknown, return "unknown".
4. "context": 20-40 words - why does this fact matter? What story does it belong to?
5. "confidence": How verifiable is this? (0.0-1.0)

RULES:
- NEVER extract opinions, predictions, or editorial commentary.
- NEVER extract meta-information about the article itself.
- Drop anything with confidence < 0.6.
- Each fact must stand alone - a reader with no other context should understand it.
- Output ONLY a valid JSON list.

EXPECTED OUTPUT FORMAT:
[
  {{
    "alpha_text": "Fact sentence.",
    "entities": ["Entity1", "Entity2"],
    "event_date": "2026-04-15",
    "context": "Context string.",
    "confidence": 0.95
  }}
]
"""

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from truebrief.models.article import ArticleSource
    
    harvester = Harvester()
    
    test_article = RawArticle(
        url="https://example.com/test",
        title="Test Article",
        source_name="Example News",
        source_type=ArticleSource.TAVILY,
        published_at=datetime(2026, 4, 16),
        text="Tesla reported Q3 revenue of $25.2B yesterday, beating analyst expectations of $24.1B. CEO Elon Musk announced plans to begin Robotaxi production in 2025."
    )
    
    alphas = harvester.extract(test_article)
    for a in alphas:
        print(f"- {a.alpha_text} (Date: {a.event_date}, Conf: {a.confidence})")
        print(f"  Entities: {a.entities}")
        print(f"  Context: {a.context}\n")
