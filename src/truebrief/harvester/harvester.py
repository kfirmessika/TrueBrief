"""
Harvester - harvester/harvester.py

Extracts atomic facts (Alphas) from raw article text using the LLM.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
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

    # Maximum days an event_date may differ from article.published_at before the fact is dropped.
    _MAX_DATE_DELTA_DAYS = 365

    def extract(
        self,
        article: RawArticle,
        topic_id: Optional[str] = None,
        topic_context: Optional[str] = None,
    ) -> List[Alpha]:
        """
        Extract facts from a single article.
        Returns a list of Alpha objects.
        Facts with confidence < 0.6 are dropped.
        Facts whose event_date is missing or >365 days from article publish date are dropped.
        Off-topic facts (when topic_context is provided) are dropped by the LLM prompt.
        """
        if not article.text:
            logger.warning(f"No text to harvest for article: {article.url}")
            return []

        prompt = self._get_prompt(article, topic_context=topic_context)

        try:
            response_text = self.llm.call(
                step_name="harvester",
                prompt=prompt,
                json_mode=True,
                system_prompt="You are a precision intelligence analyst. Extract every atomic, verifiable fact from this article into a structured JSON list."
            )

            data = json.loads(response_text)

            fact_list = data
            if isinstance(data, dict):
                for key in ["facts", "alphas", "data"]:
                    if key in data and isinstance(data[key], list):
                        fact_list = data[key]
                        break

            if not isinstance(fact_list, list):
                logger.error(f"Harvester LLM did not return a list. Type: {type(fact_list)}")
                return []

            alphas: List[Alpha] = []
            dropped_no_date = 0
            dropped_bad_date = 0

            for item in fact_list:
                if not isinstance(item, dict):
                    continue

                confidence = float(item.get("confidence", 1.0))
                if confidence < 0.6:
                    continue

                # event_date is now REQUIRED — drop any fact that can't be dated.
                raw_event_date = item.get("event_date")
                if not raw_event_date or str(raw_event_date).strip().lower() in ("unknown", "null", "none", ""):
                    dropped_no_date += 1
                    continue

                event_date = None
                try:
                    event_date = parse_date(str(raw_event_date))
                    # Make timezone-naive for comparison
                    if event_date.tzinfo is not None:
                        event_date = event_date.replace(tzinfo=None)
                except Exception:
                    dropped_no_date += 1
                    continue

                # Date-sanity check: always anchor to published_at when known, or scan-time
                # (today) when unknown. Never skip — that's what lets 2020/2023 LLM
                # hallucinations through on dateless Tavily/Brave articles.
                anchor = article.published_at
                if anchor is None:
                    anchor = datetime.now().replace(tzinfo=None)
                elif anchor.tzinfo is not None:
                    anchor = anchor.replace(tzinfo=None)

                from config.settings import settings
                if settings.V3_DATE_GUARD:
                    today = datetime.now().replace(tzinfo=None)
                    earliest_allowed = anchor.replace(year=anchor.year - 1)
                    if not (earliest_allowed <= event_date <= today):
                        # Try correcting the year to the anchor year first.
                        try:
                            corrected = event_date.replace(year=anchor.year)
                        except ValueError:
                            corrected = event_date  # leap-day edge case
                        if earliest_allowed <= corrected <= today:
                            logger.debug(
                                f"Date guard: corrected year "
                                f"{event_date.date()} → {corrected.date()} "
                                f"(anchor={anchor.date()})"
                            )
                            event_date = corrected
                        else:
                            dropped_bad_date += 1
                            logger.debug(
                                f"Date guard: dropped fact outside "
                                f"[{earliest_allowed.date()}, {today.date()}]: "
                                f"{event_date.date()} — "
                                f"{item.get('alpha_text', '')[:60]}"
                            )
                            continue
                else:
                    delta = abs((event_date - anchor).days)
                    if delta > self._MAX_DATE_DELTA_DAYS:
                        dropped_bad_date += 1
                        logger.debug(
                            f"Dropped fact with out-of-range event_date "
                            f"({event_date.date()} vs article {anchor.date()}, delta={delta}d): "
                            f"{item.get('alpha_text', '')[:60]}"
                        )
                        continue

                _VALID_CLASSES = {
                    "state_change", "escalation", "development",
                    "incremental", "tally", "routine",
                }
                raw_class = str(item.get("event_class") or "").strip().lower()
                event_class = raw_class if raw_class in _VALID_CLASSES else None

                alpha = Alpha(
                    alpha_text=item.get("alpha_text", "").strip(),
                    entities=item.get("entities", []),
                    source_url=article.url,
                    source_name=article.source_name,
                    event_date=event_date,
                    context=item.get("context", ""),
                    confidence=confidence,
                    topic_id=topic_id,
                    event_class=event_class,
                )

                if alpha.alpha_text:
                    alphas.append(alpha)

            if dropped_no_date or dropped_bad_date:
                logger.info(
                    f"Harvester date filter: kept {len(alphas)}, "
                    f"dropped {dropped_no_date} (no date), {dropped_bad_date} (bad date)"
                )

            return alphas

        except Exception as e:
            logger.error(f"Harvester failed for article {article.url}: {e}")
            return []

    def _get_prompt(self, article: RawArticle, topic_context: Optional[str] = None) -> str:
        """Construct the prompt for fact extraction."""
        from config.settings import settings as _s

        pub_date_str = article.published_at.strftime("%Y-%m-%d") if article.published_at else "Unknown"

        topic_block = ""
        if topic_context:
            topic_block = f"""
TOPIC FILTER: {topic_context}
Only extract facts that are directly and specifically relevant to this topic.
Ignore any facts about unrelated events, people, or subjects — even if they appear in the same article.

"""

        if _s.V3_DATE_GUARD:
            date_instruction = (
                'REQUIRED. The date the event HAPPENED in ISO format (YYYY-MM-DD).\n'
                '   Use the ARTICLE PUBLISHED DATE as the anchor. Relative phrases like "yesterday", "last month",\n'
                '   "on Tuesday", "June 7" MUST resolve to a date within 1 year of the article publish date.\n'
                '   The year MUST come from the publish date context — do NOT default to prior years.\n'
                '   If you cannot confidently determine the year from context, do NOT extract the fact.'
            )
        else:
            date_instruction = (
                'REQUIRED. The date the event HAPPENED in ISO format (YYYY-MM-DD).\n'
                '   Use the ARTICLE PUBLISHED DATE as anchor for relative phrases ("yesterday", "last quarter").\n'
                '   If the article does not anchor the event in time, do NOT extract the fact.\n'
                '   This field is non-optional — facts without a verifiable event date are not facts.'
            )

        return f"""
ARTICLE PUBLISHED DATE: {pub_date_str}
{topic_block}
ARTICLE TEXT:
{article.text}

TASK:
Extract every atomic, verifiable fact from this article into a structured JSON list.

For each fact extract:
1. "alpha_text": The fact as one clean standalone sentence.
2. "entities": List of named entities (companies, people, countries, products).
3. "event_date": {date_instruction}
4. "context": 20-40 words - why does this fact matter? What story does it belong to?
5. "confidence": How verifiable is this? (0.0-1.0)
6. "event_class": The development type. Choose EXACTLY ONE:
   - "state_change"  — a discrete, durable status flip: ceasefire signed, treaty agreed, leadership change,
                       strait opened/closed, law passed, company acquired, person dies/resigns.
   - "escalation"    — a new discrete aggressive or deteriorating act: strike, attack, front opens,
                       sanctions imposed, talks collapsed, troops deployed.
   - "development"   — a discrete new fact inside an ongoing story that does not flip a status:
                       meeting held, statement issued, vote scheduled, person arrested.
   - "incremental"   — a follow-up or minor update: "X now says…", clarification, minor revision.
   - "tally"         — a cumulative running count or total that will be updated again:
                       death tolls, case counts, funding totals, damage estimates. Label even if the
                       number changed — it is NEVER the lede.
   - "routine"       — scheduling/logistics: press briefing scheduled, convoy arrived, ship docked.

RULES:
- ONLY extract facts relevant to the TOPIC FILTER above (if specified).
- NEVER extract opinions, predictions, or editorial commentary.
- NEVER extract meta-information about the article itself (download links, app info, copyright notices).
- Drop anything with confidence < 0.6.
- DROP any fact where you cannot determine a specific event_date — omit it entirely.
- Each fact must stand alone - a reader with no other context should understand it.
- Output ONLY a valid JSON list.

EXPECTED OUTPUT FORMAT:
[
  {{
    "alpha_text": "Fact sentence.",
    "entities": ["Entity1", "Entity2"],
    "event_date": "2026-04-15",
    "context": "Context string.",
    "confidence": 0.95,
    "event_class": "state_change"
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
