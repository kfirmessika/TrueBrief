"""
Harvester - harvester/harvester.py

Extracts atomic facts (Alphas) from raw article text using the LLM.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional

from dateutil.parser import parse as parse_date
from truebrief.llm.client import LLMClient
from truebrief.llm.prompts import HARVESTER_SYSTEM, build_harvester_prompt
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

    # §8B lag gate: a one-time event whose development predates the reporting article by more
    # than this is stale "background" → dropped from the live harvest (belongs in history).
    _LAG_DROP_DAYS = 45
    # Anything the LLM explicitly flagged as background is held to a tighter window.
    _LAG_BACKGROUND_DAYS = 14

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
                system_prompt=HARVESTER_SYSTEM,
            )

            data = json.loads(response_text)

            fact_list = data
            if isinstance(data, dict):
                for key in ["facts", "alphas", "data"]:
                    if key in data and isinstance(data[key], list):
                        fact_list = data[key]
                        break
                else:
                    # Groq/llama shapes (seen in prod 2026-07-06):
                    # a single bare fact object, or {"error": "No facts relevant..."}
                    # when the article has nothing on-topic (honest empty result).
                    if "alpha_text" in data:
                        fact_list = [data]
                    else:
                        logger.info(
                            "Harvester LLM returned no-facts dict: %s",
                            str(data)[:120],
                        )
                        return []

            if not isinstance(fact_list, list):
                logger.error(f"Harvester LLM did not return a list. Type: {type(fact_list)}")
                return []

            alphas: List[Alpha] = []
            dropped_no_date = 0
            dropped_bad_date = 0
            dropped_stale = 0
            dropped_meta = 0

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
                    if event_date.year < 2000:
                        # Sentinel / epoch date (e.g. 1970-01-01 from a null LLM date):
                        # year-correcting would fabricate a fake "2026-01-01". Anchor it to
                        # the article date instead (best estimate for an undated breaking fact).
                        logger.debug(
                            f"Date guard: sentinel date {event_date.date()} → "
                            f"anchor {anchor.date()} ({item.get('alpha_text','')[:50]})"
                        )
                        event_date = anchor
                    elif not (earliest_allowed <= event_date <= today):
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
                    "incremental", "tally", "routine", "casualty",
                }
                raw_class = str(item.get("event_class") or "").strip().lower()
                event_class = raw_class if raw_class in _VALID_CLASSES else None

                _raw_basis = str(item.get("date_basis") or "").strip().lower()
                date_basis = _raw_basis if _raw_basis in ("explicit", "relative", "inferred") else None
                is_background = bool(item.get("is_background", False))

                # §8B development-lag gate: a fact "new to us, not new to the world" belongs in
                # history, not at the top of today. Drop (a) anything the LLM flagged as
                # background/standing-state — it is referenced as context, not reported as today's
                # development (this catches evergreens like "since 1991"/"ongoing talks" whose
                # event_date the LLM anchors to now, so lag alone can't catch them); and (b) any
                # one-time event whose development predates the article by > _LAG_DROP_DAYS.
                # Tallies are exempt (they legitimately reference a cumulative period).
                if settings.V3_LAG_GATE and event_class != "tally":
                    lag_days = (anchor - event_date).days if anchor is not None else 0
                    if is_background or lag_days > self._LAG_DROP_DAYS:
                        dropped_stale += 1
                        logger.info(
                            "Lag gate: dropped stale/background fact (lag=%dd, bg=%s): %s",
                            lag_days, is_background, item.get("alpha_text", "")[:70],
                        )
                        continue

                _raw_importance = item.get("importance")
                importance = None
                if _raw_importance is not None:
                    try:
                        importance = max(0.0, min(1.0, float(_raw_importance)))
                    except (TypeError, ValueError):
                        pass

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
                    published_at=anchor,
                    date_basis=date_basis,
                    is_background=is_background,
                    importance=importance,
                )

                if not alpha.alpha_text:
                    continue

                # Meta-sentence guard: the LLM sometimes answers ABOUT the article
                # instead of extracting FROM it ("There are no facts in the provided
                # article relevant to X"). These are not facts — never store them.
                # (Found in production: stored with relevance 0.65, shown to users.)
                if self._is_meta_sentence(alpha.alpha_text):
                    dropped_meta += 1
                    logger.info(
                        "Meta-sentence guard: dropped non-fact: %s",
                        alpha.alpha_text[:80],
                    )
                    continue

                alphas.append(alpha)

            if dropped_no_date or dropped_bad_date or dropped_stale or dropped_meta:
                logger.info(
                    f"Harvester filter: kept {len(alphas)}, "
                    f"dropped {dropped_no_date} (no date), {dropped_bad_date} (bad date), "
                    f"{dropped_stale} (stale/background), {dropped_meta} (meta-sentence)"
                )

            return alphas

        except Exception as e:
            logger.error(f"Harvester failed for article {article.url}: {e}")
            return []

    # Patterns that indicate the LLM answered ABOUT the article instead of
    # extracting a fact FROM it. Case-insensitive, matched anywhere in the text.
    # NOTE: deliberately NOT matching the bare "the article" — real extractions
    # occasionally phrase a fact as "The article states that X happened" (found
    # in prod: a genuine Trump/World Cup fact). Only meta-specific constructs.
    _META_PATTERNS = re.compile(
        r"("
        r"\bno (?:new |verifiable )?(?:facts?|information|developments?|updates?|news content)\b"
        r"|\bprovided article\b"
        r"|\barticle (?:text|content)\b"
        r"|\bthis article\b"
        r"|\btopic filter\b"
        r"|\bin the prompt\b"
        r"|\bno mention of\b"
        r"|\bnot (?:mentioned|addressed)\b"
        r"|\bnot (?:directly )?relevant\b"
        r"|\birrelevant to\b"
        r"|\bnews organizations? published\b"
        r"|\bcannot (?:be )?extract"
        r")",
        re.IGNORECASE,
    )

    @classmethod
    def _is_meta_sentence(cls, text: str) -> bool:
        """True when the text is LLM meta-commentary, not an extractable fact."""
        return bool(cls._META_PATTERNS.search(text))

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

        return build_harvester_prompt(
            article_text=article.text,
            pub_date_str=pub_date_str,
            topic_block=topic_block,
            date_guard=_s.V3_DATE_GUARD,
        )

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
