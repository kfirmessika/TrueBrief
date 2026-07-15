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
from truebrief.llm.prompts import QUERY_BUILDER_SYSTEM, build_query_builder_prompt
from truebrief.models.topic import Topic

logger = logging.getLogger(__name__)


@dataclass
class TopicDomain:
    """One facet of a topic with its own search queries.

    Example (Israel topic):
      name="military_operations", description="IDF, Hezbollah, air strikes",
      queries=["IDF Gaza offensive", "Hezbollah attack northern Israel"]
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
    # Spelling-corrected version of the user's raw input (no semantic change).
    # "isreal" -> "israel", "nvida" -> "nvidia". Empty = no correction needed.
    corrected_query: str = ""


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
                system_prompt=QUERY_BUILDER_SYSTEM,
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
                corrected_query=data.get("corrected_query", topic_input),
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
        from datetime import datetime
        _today = datetime.now().strftime("%B %Y")  # e.g. "July 2026"
        return build_query_builder_prompt(
            topic=topic,
            rss_categories=self._rss_categories,
            today=_today,
        )


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
