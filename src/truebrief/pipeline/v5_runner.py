"""
V5 Pipeline Runner — pipeline/v5_runner.py

The production entry point per docs/core/architecture_v5.md: Gemini Search collector ->
Arbiter (memory/dedup + judge) -> stored facts -> brief. Deliberately minimal — no
query_builder, no search layers, no harvester, no signal scorer, no story
stitching/clustering, no AYR. Those stay available on V4's PipelineRunner
(pipeline/runner.py, unmodified) for the Phase 4 A/B benchmark; nothing there was
deleted, only not called from here.

Same public contract as PipelineRunner.run() (topic_input, topic_id) -> brief text, so
tasks/pipeline_task.py only needs to change which runner it constructs.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from truebrief.arbiter.arbiter import Arbiter
from truebrief.briefer.briefer import Briefer
from truebrief.collector.gemini_search_collector import GeminiSearchCollector
from truebrief.ledger.vector_store import VectorStore
from truebrief.models.alpha import DecisionType

logger = logging.getLogger(__name__)


class GeminiSearchRunner:
    """V5's pipeline: one grounded search, memory/dedup, one brief. See module docstring."""

    def __init__(self) -> None:
        self.vector_store = VectorStore()
        self.arbiter = Arbiter(vector_store=self.vector_store)
        self.collector = GeminiSearchCollector(vector_store=self.vector_store)
        self.briefer = Briefer()
        # Exposed for pipeline_task.py's **getattr(runner, "last_run_stats", {}) telemetry.
        self.last_run_stats: dict = {}

    def run(self, topic_input: str, topic_id: Optional[str] = None) -> str:
        """Run one V5 pass for a topic. Returns brief markdown, or "" if nothing new."""
        last_run_date = self._get_last_run_date(topic_id) if topic_id else None

        logger.info(
            "[V5] Collecting for '%s' (last_run=%s)",
            topic_input, last_run_date.date() if last_run_date else "first run",
        )
        alphas = self.collector.collect(topic_input, last_run_date=last_run_date, topic_id=topic_id)
        self.last_run_stats["alphas_extracted"] = len(alphas)

        if not alphas:
            logger.info("[V5] No new facts found for '%s'.", topic_input)
            return ""

        logger.info("[V5] Judging %d candidate facts.", len(alphas))
        judged = self.arbiter.judge_alphas(alphas, topic_id=topic_id)

        decisions = []
        new_count = update_count = duplicate_count = 0
        for alpha, decision in zip(alphas, judged):
            decisions.append(decision)
            if decision.decision == DecisionType.NEW:
                new_count += 1
            elif decision.decision == DecisionType.UPDATE:
                update_count += 1
            else:
                duplicate_count += 1

            if decision.decision in (DecisionType.NEW, DecisionType.UPDATE):
                try:
                    self.vector_store.add_fact(decision.alpha)
                except Exception as exc:
                    logger.error("[V5] Failed to save fact: %s", exc)

        self.last_run_stats.update({
            "decisions_new": new_count,
            "decisions_update": update_count,
            "decisions_duplicate": duplicate_count,
        })
        logger.info(
            "[V5] Decisions: %d NEW, %d UPDATE, %d DUPLICATE.",
            new_count, update_count, duplicate_count,
        )

        brief_text = self.briefer.generate(decisions, topic_input)
        logger.info("[V5] Brief generated (%d chars).", len(brief_text))
        return brief_text

    @staticmethod
    def _get_last_run_date(topic_id: str) -> Optional[datetime]:
        """Read topics.last_run_at so the collector searches only what's new since then."""
        try:
            from dateutil.parser import parse as parse_date

            from truebrief.ledger.database import get_supabase
            res = get_supabase().table("topics").select("last_run_at").eq("id", topic_id).execute()
            if res.data and res.data[0].get("last_run_at"):
                dt = parse_date(res.data[0]["last_run_at"])
                return dt.replace(tzinfo=None) if dt.tzinfo else dt
        except Exception as exc:
            logger.warning("[V5] Could not read last_run_at (treating as first run): %s", exc)
        return None
