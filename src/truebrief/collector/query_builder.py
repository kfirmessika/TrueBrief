"""
Query Builder Collector Plugin - collector/query_builder.py

Uses an LLM to take a simple user topic and produce:
1. Formalized topic name.
2. Search queries for Tavily.
3. Relevant RSS categories from rss_feeds.yaml.
4. Input validation (reject garbage).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

import yaml
from config.settings import RSS_FEEDS_PATH
from truebrief.llm.client import LLMClient
from truebrief.models.topic import Topic

logger = logging.getLogger(__name__)

@dataclass
class SearchQuery:
    """The result of the Query Builder process."""
    topic_name: str
    primary_query: str
    alt_queries: list[str] = field(default_factory=list)
    rss_categories: list[str] = field(default_factory=list)
    status: str = "APPROVED"  # "APPROVED" or "REJECTED"
    reason: Optional[str] = None


class QueryBuilder:
    """
    Topic -> Search Strategy.
    The first step in any pipeline run.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self.llm = llm_client or LLMClient()
        self._rss_categories = self._load_rss_categories()

    def _load_rss_categories(self) -> list[str]:
        """Load available categories from the curated feed database."""
        try:
            with open(RSS_FEEDS_PATH, "r") as f:
                feeds = yaml.safe_load(f)
                return list(feeds.keys())
        except Exception as e:
            logger.error(f"Failed to load RSS feeds from {RSS_FEEDS_PATH}: {e}")
            return ["general"]

    def build(self, topic_input: str) -> SearchQuery:
        """
        Analyze the user input and produce a search strategy.
        """
        prompt = self._get_prompt(topic_input)
        
        try:
            response_text = self.llm.call(
                step_name="query_builder",
                prompt=prompt,
                json_mode=True,
                system_prompt="You are the TrueBrief Librarian. Your job is to analyze user tracking topics.",
            )
            
            data = json.loads(response_text)
            
            if data.get("status") == "REJECTED":
                return SearchQuery(
                    topic_name=topic_input,
                    primary_query="",
                    status="REJECTED",
                    reason=data.get("reason", "Input rejected by LLM.")
                )

            # Map the response to our SearchQuery object
            return SearchQuery(
                topic_name=data.get("short_name", topic_input),
                primary_query=data.get("primary_query", topic_input),
                alt_queries=data.get("alt_queries", []),
                rss_categories=data.get("rss_categories", ["general"]),
            )

        except Exception as e:
            logger.error(f"QueryBuilder failed: {e}")
            # Fallback to a basic search
            return SearchQuery(
                topic_name=topic_input,
                primary_query=topic_input,
                rss_categories=["general"],
            )

    def _get_prompt(self, topic: str) -> str:
        """Generate the LLM prompt for topic analysis."""
        return f"""
The user wants to track breaking news updates for the following topic: '{topic}'

TASK:
1. Decide if this input is legitimate or if it's gibberish/malicious.
2. Formalize a clean 'short_name' for the topic (e.g. 'Elon Musk' instead of 'elon musks stuff').
3. Generate 1 primary search query and 2 alternative queries that are highly effective for news search.
4. Select the most relevant categories from our curated RSS feed database.

AVAILABLE RSS CATEGORIES:
{self._rss_categories}

IF INPUT IS GIBBERISH/INVALID:
Return JSON: {{"status": "REJECTED", "reason": "Explanation of why"}}

IF INPUT IS VALID:
Return JSON:
{{
  "status": "APPROVED",
  "short_name": "Official Clean Name",
  "primary_query": "Most specific news query",
  "alt_queries": ["query 2", "query 3"],
  "rss_categories": ["matched_category_1", "matched_category_2"]
}}

REMEMBER: Return ONLY the raw JSON object. No markdown.
"""

if __name__ == "__main__":
    # Quick debug run
    logging.basicConfig(level=logging.INFO)
    qb = QueryBuilder()
    res = qb.build("TSMC semiconductor manufacturing")
    print(res)
    
    bad = qb.build("asdf1234!!")
    print(bad)
