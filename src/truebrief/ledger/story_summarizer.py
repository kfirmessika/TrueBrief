"""
Story Summarizer - ledger/story_summarizer.py

Phase 3, Task 3.3 - Recursive Summary Updates

When a new fact joins an existing StoryNode, the story's summary is stale -
it was written before the new fact arrived.  This module regenerates the
summary by feeding ALL facts in the story to an LLM and asking for a concise,
coherent narrative that incorporates every development.

The "recursive" part:  on each update the LLM sees the PREVIOUS summary plus
the new fact(s), producing an ever-evolving narrative thread.  This is
cheaper than re-summarizing all raw facts every time (which would grow
unbounded), and it preserves editorial continuity.

Flow:
    1. Fetch the story's current summary + the new fact text
    2. LLM call: merge previous summary + new fact → new summary
    3. story_manager.update_summary() persists text + re-embeds (Task 3.2)
"""

from __future__ import annotations

import logging
from typing import Optional

from truebrief.llm.client import LLMClient
from truebrief.llm.prompts import STORY_SUMMARIZER_SYSTEM, build_story_summarizer_prompt
from truebrief.ledger.story_manager import StoryManager
from truebrief.models.alpha import Alpha

logger = logging.getLogger(__name__)

# Maximum length for the generated summary (characters).
# Keeps summaries concise and embedding-friendly.
MAX_SUMMARY_LENGTH: int = 500


class StorySummarizer:
    """
    Regenerates a StoryNode's summary each time a new fact is added.

    Uses a recursive approach:
        new_summary = LLM(previous_summary + new_fact)

    This is O(1) per update (one LLM call), not O(n) over all facts.
    """

    def __init__(
        self,
        story_manager: StoryManager,
        llm_client: Optional[LLMClient] = None,
    ) -> None:
        self.story_manager = story_manager
        self.llm = llm_client or LLMClient()

    def refresh_summary(
        self,
        story_node_id: str,
        new_alpha: Alpha,
    ) -> bool:
        """
        Regenerate the summary for a story after a new fact is added.

        Args:
            story_node_id: The StoryNode to update.
            new_alpha:     The Alpha that was just added to the story.

        Returns:
            True if the summary was successfully updated, False otherwise.
        """
        log_prefix = f"[SUMMARIZER] Story {story_node_id[:8]}..."

        # 1. Fetch the story's current state
        try:
            stories = self.story_manager.db.table("story_nodes") \
                .select("title, summary, fact_count") \
                .eq("id", story_node_id) \
                .limit(1) \
                .execute()

            if not stories.data:
                logger.warning(f"{log_prefix} Story not found.")
                return False

            story_row = stories.data[0]
            previous_summary = story_row.get("summary", "")
            fact_count = story_row.get("fact_count", 1)
            title = story_row.get("title", "")
        except Exception as e:
            logger.error(f"{log_prefix} Failed to fetch story: {e}")
            return False

        # 2. Skip if this is the first fact (summary = the fact itself, no merge needed)
        if fact_count <= 1 and not previous_summary:
            logger.debug(f"{log_prefix} First fact - no summary merge needed.")
            return True

        # 3. Build the LLM prompt
        prompt = self._build_prompt(
            previous_summary=previous_summary,
            new_fact=new_alpha.alpha_text,
            new_fact_context=new_alpha.context,
            title=title,
        )

        # 4. Call the LLM
        try:
            new_summary = self.llm.call(
                step_name="story_summarizer",
                prompt=prompt,
                json_mode=False,
                system_prompt=STORY_SUMMARIZER_SYSTEM,
            )
            new_summary = new_summary.strip()

            if not new_summary:
                logger.warning(f"{log_prefix} LLM returned empty summary.")
                return False

            # Enforce length cap
            if len(new_summary) > MAX_SUMMARY_LENGTH:
                new_summary = new_summary[:MAX_SUMMARY_LENGTH].rsplit(" ", 1)[0] + "…"

        except Exception as e:
            logger.error(f"{log_prefix} LLM summary generation failed: {e}")
            return False

        # 5. Persist the new summary + re-embed (via StoryManager)
        logger.info(
            f"{log_prefix} Updating summary "
            f"({len(previous_summary)} → {len(new_summary)} chars)"
        )
        return self.story_manager.update_summary(story_node_id, new_summary)

    # ──────────────────────────────────────────────────────────────────────────
    # Prompt Engineering
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_prompt(
        previous_summary: str,
        new_fact: str,
        new_fact_context: Optional[str] = None,
        title: str = "",
    ) -> str:
        """
        Build the recursive summary prompt.

        The key insight: we give the LLM the PREVIOUS summary (already condensed)
        plus the NEW fact, and ask it to produce an updated summary.  This means
        the LLM never needs to read all raw facts - just the last summary + delta.
        """
        return build_story_summarizer_prompt(
            title=title,
            previous_summary=previous_summary,
            new_fact=new_fact,
            new_fact_context=new_fact_context or "",
            max_summary_length=MAX_SUMMARY_LENGTH,
        )
