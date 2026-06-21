"""
Query Builder Collector Plugin - collector/query_builder.py

Uses an LLM to take a simple user topic and produce:
1. Formalized topic name.
2. Topic DOMAINS — distinct facets (military, diplomacy, humanitarian, …) each with
   2-3 search queries that surface different articles than the other domains.
3. Relevant RSS categories from rss_feeds.yaml.
4. Input validation (reject garbage).

Domain-based querying (V3_DOMAIN_QUERIES): the runner fires one query per domain in
parallel so a single scan covers all major facets of a topic instead of one angle.

Backward compatibility: primary_query and alt_queries are derived from domains so the
existing UCB1 rotator continues to work without schema changes.
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
class TopicDomain:
    """One facet of a topic with its own search queries.

    Example (Israel topic):
      name="military_operations", description="IDF, Hezbollah, air strikes",
      queries=["IDF Gaza offensive 2025", "Hezbollah attack northern Israel"]
    """
    name: str           # slug: lowercase_underscore (e.g. "military_operations")
    description: str    # one-line summary of what this facet covers
    queries: list[str]  # 1-3 diverse search strings for this facet


@dataclass
class SearchQuery:
    """The result of the Query Builder process."""
    topic_name: str
    primary_query: str
    alt_queries: list[str] = field(default_factory=list)
    rss_categories: list[str] = field(default_factory=list)
    # Structured domain facets — populated by QueryBuilder when LLM output includes them.
    # Empty list = legacy / fallback (single-query mode still works fine).
    domains: list[TopicDomain] = field(default_factory=list)
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
                    reason=data.get("reason", "Input rejected by LLM."),
                )

            domains = self._parse_domains(data.get("domains") or [])

            # Derive flat primary_query + alt_queries from domains for UCB1 backward compat.
            # primary_query = domain[0] query[0]; alt_queries = everything else, flattened.
            if domains:
                primary_query = domains[0].queries[0] if domains[0].queries else topic_input
                alt_queries: list[str] = []
                for i, d in enumerate(domains):
                    start = 1 if i == 0 else 0
                    alt_queries.extend(d.queries[start:])
            else:
                primary_query = data.get("primary_query", topic_input)
                alt_queries = data.get("alt_queries", [])

            return SearchQuery(
                topic_name=data.get("short_name", topic_input),
                primary_query=primary_query,
                alt_queries=alt_queries,
                rss_categories=data.get("rss_categories", ["general"]),
                domains=domains,
            )

        except Exception as e:
            logger.error(f"QueryBuilder failed: {e}")
            return SearchQuery(
                topic_name=topic_input,
                primary_query=topic_input,
                rss_categories=["general"],
            )

    # ── Private ───────────────────────────────────────────────────────────────

    def _parse_domains(self, raw: list[dict]) -> list[TopicDomain]:
        """Convert raw LLM JSON list into TopicDomain objects. Tolerant of bad output."""
        domains: list[TopicDomain] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            desc = str(item.get("description") or "").strip()
            queries_raw = item.get("queries") or []
            queries = [str(q).strip() for q in queries_raw if str(q).strip()]
            if name and queries:
                domains.append(TopicDomain(name=name, description=desc, queries=queries))
        return domains

    def _get_prompt(self, topic: str) -> str:
        return f"""
The user wants to track breaking news for: '{topic}'

TASK:
1. Decide if the input is a legitimate news topic or gibberish/malicious. Reject the latter.
2. Formalize a clean 'short_name' (e.g. 'Israel-Hamas War', 'TSMC Semiconductors').
3. Split the topic into 3-4 DISTINCT DOMAINS — each covering a different facet.
   For each domain generate 2 search queries that surface articles OTHER domains wouldn't.
4. Choose relevant RSS categories from the list below.

AVAILABLE RSS CATEGORIES:
{self._rss_categories}

DOMAIN RULES (critical — read carefully):
- Each domain covers a DIFFERENT slice of the topic. No overlap.
- Queries within a domain are angle variations of the SAME facet.
- Queries ACROSS domains must be topically DIVERGENT: domain A queries must NOT return
  the same articles as domain B queries. Think "what stories would only appear under this facet?"
- Domain 0 is the PRIMARY facet (most direct match to user intent).
- Keep queries specific enough for news search but not so narrow they return nothing.
- Do NOT use site: operators or boolean syntax — plain keyword queries only.

EXAMPLES:

Topic "Israel":
  domain 0 "military_operations":
    queries: ["IDF Gaza offensive operations 2025", "Hezbollah rocket attack Lebanon Israel"]
  domain 1 "diplomacy_ceasefire":
    queries: ["Gaza ceasefire negotiations mediators 2025", "US Iran nuclear talks Middle East"]
  domain 2 "humanitarian_crisis":
    queries: ["Gaza civilian casualties aid delivery 2025", "West Bank Palestinian refugees UN"]
  domain 3 "domestic_political":
    queries: ["Netanyahu government coalition protest 2025", "Israel defense industry economy war"]

Topic "Shark attack Australia":
  domain 0 "incident_victim":
    queries: ["shark attack Queensland beach 2025", "surfer bitten Australia coast fatality"]
  domain 1 "safety_response":
    queries: ["beach closure shark drumlines Queensland", "lifeguard aerial drone shark patrol"]
  domain 2 "ecology_science":
    queries: ["great white shark population Australia habitat", "shark species behavior attack research"]

IF INPUT IS GIBBERISH/INVALID/HARMFUL:
Return: {{"status": "REJECTED", "reason": "Explanation"}}

IF VALID, return ONLY this JSON (no markdown, no extra keys):
{{
  "status": "APPROVED",
  "short_name": "Clean Topic Name",
  "rss_categories": ["category1", "category2"],
  "domains": [
    {{
      "name": "domain_slug",
      "description": "One sentence: what facet this covers",
      "queries": ["query one", "query two"]
    }}
  ]
}}
"""


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    qb = QueryBuilder()

    print("=== Israel test ===")
    res = qb.build("isreal")
    print(f"topic_name: {res.topic_name}")
    print(f"primary_query: {res.primary_query}")
    print(f"domains ({len(res.domains)}):")
    for d in res.domains:
        print(f"  [{d.name}] {d.description}")
        for q in d.queries:
            print(f"    . {q}")

    print("\n=== Rejection test ===")
    bad = qb.build("asdf1234!!")
    print(f"status: {bad.status}, reason: {bad.reason}")
