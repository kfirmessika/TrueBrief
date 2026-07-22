"""
Gemini Search Collector — collector/gemini_search_collector.py (V5)

Replaces the query_builder + search layers (Tavily/Brave/Exa/RSS) + extractor +
harvester chain with two Gemini calls per topic run:
  1. Grounded prose search ("what's new on <topic> from <last_run> to now")
  2. A cheap, non-grounded restructuring call into the Alpha JSON contract

See docs/core/architecture_v5.md §3 for the design and why this is two calls, not one
(forcing JSON output on the grounded call suppresses real source metadata and makes the
model fabricate URLs — verified live 2026-07-22, see llm/client.py's
call_gemini_with_grounding docstring).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import List, Optional

from dateutil.parser import parse as parse_date

from truebrief.llm.client import GroundedResult, LLMClient
from truebrief.llm.prompts import (
    GEMINI_EXTRACT_SYSTEM,
    GEMINI_SEARCH_SYSTEM,
    build_gemini_extract_prompt,
    build_gemini_search_prompt,
)
from truebrief.models.alpha import Alpha

logger = logging.getLogger(__name__)

# Same confidence floor the harvester used — facts below this are noise, not signal.
_MIN_CONFIDENCE = 0.6

_VALID_EVENT_CLASSES = {
    "state_change", "escalation", "development",
    "incremental", "tally", "routine", "casualty",
}
_VALID_DATE_BASES = {"explicit", "relative", "inferred"}


def _insert_citation_markers(text: str, supports: list) -> str:
    """Insert [i] or [i,j] markers at each grounding_supports segment's end_index.

    segment.start_index/end_index are exact Python string character offsets into
    `text` (verified live 2026-07-22 — text[start:end] == segment.text exactly).
    Must process in REVERSE order of end_index so inserting a marker doesn't shift
    the offsets of segments not yet processed.
    """
    ordered = sorted(
        (s for s in supports if getattr(s, "segment", None) and s.segment.end_index is not None),
        key=lambda s: s.segment.end_index,
        reverse=True,
    )
    out = text
    for s in ordered:
        indices = list(s.grounding_chunk_indices or [])
        if not indices:
            continue
        marker = "[" + ",".join(str(i) for i in indices) + "]"
        idx = s.segment.end_index
        out = out[:idx] + marker + out[idx:]
    return out


def _build_source_legend(chunks: list) -> tuple:
    """Returns (legend_text, urls_by_index, names_by_index).

    urls/names come ONLY from grounding_chunks — real, Google-verified sources, never
    from anything the model generated. This is the entire point of the two-call design.
    """
    lines: List[str] = []
    urls: List[Optional[str]] = []
    names: List[Optional[str]] = []
    for i, c in enumerate(chunks):
        web = getattr(c, "web", None)
        uri = getattr(web, "uri", None) if web else None
        title = getattr(web, "title", None) if web else None
        urls.append(uri)
        names.append(title)
        lines.append(f"[{i}] {title or uri or 'unknown source'}")
    return ("\n".join(lines) if lines else "(no sources)"), urls, names


class GeminiSearchCollector:
    """V5's main collection pipeline. Replaces Collector + QueryBuilder + Harvester."""

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self.llm = llm_client or LLMClient()

    def collect(
        self,
        topic_name: str,
        last_run_date: Optional[datetime] = None,
        topic_id: Optional[str] = None,
    ) -> List[Alpha]:
        """Search for and extract facts on `topic_name` since `last_run_date`.

        `last_run_date=None` means a first-ever run — searches the last 7 days instead
        of an exact range. Returns Alpha objects ready for the arbiter; empty list on
        "nothing new" or any parse failure (never raises for a bad LLM response).
        """
        today = datetime.now()
        today_str = today.strftime("%Y-%m-%d")
        last_run_str = last_run_date.strftime("%Y-%m-%d") if last_run_date else ""

        search_prompt = build_gemini_search_prompt(topic_name, last_run_str, today_str)
        grounded: GroundedResult = self.llm.call_gemini_with_grounding(
            step_name="gemini_search",
            prompt=search_prompt,
            system_prompt=GEMINI_SEARCH_SYSTEM,
        )

        if not grounded.text.strip():
            logger.info("[gemini_search] empty response for topic '%s' — nothing new.", topic_name)
            return []

        cited_text = _insert_citation_markers(grounded.text, grounded.supports)
        legend, urls, names = _build_source_legend(grounded.chunks)

        extract_prompt = build_gemini_extract_prompt(cited_text, legend, topic_name, today_str)
        raw = self.llm.call(
            step_name="gemini_extract",
            prompt=extract_prompt,
            json_mode=True,
            system_prompt=GEMINI_EXTRACT_SYSTEM,
        )

        return self._parse_facts(raw, urls, names, topic_id)

    def _parse_facts(
        self,
        raw: str,
        urls: List[Optional[str]],
        names: List[Optional[str]],
        topic_id: Optional[str],
    ) -> List[Alpha]:
        try:
            data = json.loads(raw)
        except Exception as exc:
            logger.error("[gemini_extract] JSON parse failed: %s. raw=%s", exc, raw[:200])
            return []

        # Defensive shape handling — same tolerance as harvester.py for non-list responses
        # (a bare fact object, an {"error": "..."} no-facts dict, etc).
        fact_list = data
        if isinstance(data, dict):
            for key in ("facts", "alphas", "data"):
                if key in data and isinstance(data[key], list):
                    fact_list = data[key]
                    break
            else:
                if "alpha_text" in data:
                    fact_list = [data]
                else:
                    logger.info("[gemini_extract] no-facts dict: %s", str(data)[:120])
                    return []

        if not isinstance(fact_list, list):
            logger.error("[gemini_extract] did not return a list. type=%s", type(fact_list))
            return []

        alphas: List[Alpha] = []
        for item in fact_list:
            if not isinstance(item, dict):
                continue

            confidence = float(item.get("confidence", 1.0))
            if confidence < _MIN_CONFIDENCE:
                continue

            alpha_text = str(item.get("alpha_text", "")).strip()
            if not alpha_text:
                continue

            raw_date = item.get("event_date")
            if not raw_date or str(raw_date).strip().lower() in ("unknown", "null", "none", ""):
                continue
            try:
                event_date = parse_date(str(raw_date))
                if event_date.tzinfo is not None:
                    event_date = event_date.replace(tzinfo=None)
            except Exception:
                continue

            raw_class = str(item.get("event_class") or "").strip().lower()
            event_class = raw_class if raw_class in _VALID_EVENT_CLASSES else None

            raw_basis = str(item.get("date_basis") or "").strip().lower()
            date_basis = raw_basis if raw_basis in _VALID_DATE_BASES else None

            # Source attribution — ONLY from real grounding_chunks, via the model's
            # citation_indices. A model-generated URL is never requested or trusted.
            source_url = ""
            source_name = ""
            for ci in item.get("citation_indices") or []:
                if isinstance(ci, int) and 0 <= ci < len(urls) and urls[ci]:
                    source_url = urls[ci]
                    source_name = names[ci] or source_url
                    break

            importance = item.get("importance")
            try:
                importance = float(importance) if importance is not None else None
            except (TypeError, ValueError):
                importance = None

            alphas.append(Alpha(
                alpha_text=alpha_text,
                entities=[str(e) for e in (item.get("entities") or [])],
                source_url=source_url,
                source_name=source_name,
                event_date=event_date,
                context=item.get("context") or None,
                confidence=confidence,
                date_basis=date_basis,
                is_background=bool(item.get("is_background", False)),
                topic_id=topic_id,
                event_class=event_class,
                importance=importance,
            ))

        return alphas
