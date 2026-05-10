"""
Story Manager - ledger/story_manager.py

Phase 3, Tasks 3.1 + 3.2 - Story Nodes + Dual Vectors

Manages the lifecycle of StoryNodes:
  - assign_to_story():  Given a judged Alpha, attach it to an existing
                         StoryNode or create a new one.
  - update_summary():   Regenerate a story's summary text and re-embed it
                         (called by Task 3.3 on each UPDATE event).
  - get_stories():      Retrieve all StoryNodes for a topic.
  - get_story_facts():  Retrieve all facts in a StoryNode.

Story Assignment Logic:
  - UPDATE Alpha → always joins the same StoryNode as the matched fact.
  - NEW Alpha    → embed its text, compare against existing story summaries.
                   If similarity ≥ STORY_ASSIGNMENT_THRESHOLD → join that story.
                   Otherwise → create a new StoryNode.
  - DUPLICATE    → ignored (fact already exists in the system).

Dual-Vector Design (Task 3.2):
  - alpha_embedding   → per-fact vector in known_facts (unchanged from Phase 1)
  - summary_embedding → per-story vector in story_nodes (set here on create/update)
  The summary_embedding enables story-level semantic search, which is broader
  than fact-level search. The match_stories() RPC queries this vector.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from supabase import Client
from truebrief.ledger.database import get_supabase
from truebrief.llm.client import LLMClient
from truebrief.models.alpha import Alpha, AlphaDecision, DecisionType
from truebrief.models.story import StoryNode, StoryStatus

logger = logging.getLogger(__name__)

# Similarity threshold for attaching a NEW Alpha to an existing story.
# Lower than Arbiter thresholds because stories are broad clusters, not exact matches.
STORY_ASSIGNMENT_THRESHOLD: float = 0.70

# Maximum stories to check when looking for a match.
STORY_MATCH_LIMIT: int = 5


class StoryManager:
    """
    Manages StoryNode creation, assignment, and retrieval.

    Integrates with the pipeline after the Arbiter judging step.
    """

    def __init__(
        self,
        supabase_client: Optional[Client] = None,
        llm_client: Optional[LLMClient] = None,
    ) -> None:
        self.db = supabase_client or get_supabase()
        self.llm = llm_client or LLMClient()

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def assign_to_story(
        self, decision: AlphaDecision, topic_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Assign a judged Alpha to a StoryNode.

        Returns the story_node_id the Alpha was attached to, or None if
        the decision is DUPLICATE (no action needed).

        Args:
            decision:  The Arbiter's verdict for this Alpha.
            topic_id:  The topic this Alpha belongs to.

        Returns:
            story_node_id (str) or None
        """
        if decision.decision == DecisionType.DUPLICATE:
            logger.debug("DUPLICATE - skipping story assignment.")
            return None

        alpha = decision.alpha
        effective_topic_id = topic_id or alpha.topic_id

        if decision.decision == DecisionType.UPDATE:
            # UPDATE: attach to the same story as the matched fact
            return self._assign_update(decision, effective_topic_id)

        # NEW: check if it fits an existing story, or create one
        return self._assign_new(alpha, effective_topic_id)

    def update_summary(self, story_node_id: str, new_summary: str) -> bool:
        """
        Update a story's summary text and re-embed it (Task 3.2 dual-vector).

        Called by Task 3.3 (recursive summary updates) after each UPDATE event.

        Args:
            story_node_id: The story to update.
            new_summary:   The new LLM-generated summary text.

        Returns:
            True if successful, False otherwise.
        """
        try:
            # Re-embed the new summary text (this is the "dual-vector" update)
            embedding = self.llm.embed(new_summary)
        except Exception as e:
            logger.error(f"Failed to embed new summary for story {story_node_id}: {e}")
            embedding = None

        update_data: dict = {
            "summary": new_summary,
            "updated_at": "now()",
        }
        if embedding:
            update_data["summary_embedding"] = embedding

        try:
            self.db.table("story_nodes").update(update_data).eq(
                "id", story_node_id
            ).execute()
            logger.info(
                f"Updated summary for StoryNode {story_node_id} "
                f"({'with' if embedding else 'without'} embedding)"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to update story summary: {e}")
            return False

    def get_stories(
        self,
        topic_id: str,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[StoryNode]:
        """
        Retrieve all StoryNodes for a topic, optionally filtered by status.
        """
        try:
            query = (
                self.db.table("story_nodes")
                .select("*")
                .eq("topic_id", topic_id)
                .order("updated_at", desc=True)
                .limit(limit)
            )
            if status:
                query = query.eq("status", status)

            response = query.execute()
            return [self._row_to_story(row) for row in response.data]
        except Exception as e:
            logger.error(f"Failed to fetch stories: {e}")
            return []

    def get_story_facts(self, story_node_id: str) -> List[dict]:
        """
        Retrieve all facts (known_facts rows) attached to a StoryNode.
        Returns raw dicts from Supabase.
        """
        try:
            response = (
                self.db.table("known_facts")
                .select("*")
                .eq("story_node_id", story_node_id)
                .order("first_seen_at", desc=False)
                .execute()
            )
            return response.data
        except Exception as e:
            logger.error(f"Failed to fetch story facts: {e}")
            return []

    # ──────────────────────────────────────────────────────────────────────────
    # Private: Assignment Logic
    # ──────────────────────────────────────────────────────────────────────────

    def _assign_update(
        self, decision: AlphaDecision, topic_id: Optional[str]
    ) -> Optional[str]:
        """
        UPDATE Alpha: find the story of the matched fact, attach there.
        """
        matched_id = decision.matched_alpha_id
        if not matched_id:
            logger.warning("UPDATE decision has no matched_alpha_id. Treating as NEW.")
            return self._assign_new(decision.alpha, topic_id)

        # Look up the story_node_id of the matched fact
        try:
            response = (
                self.db.table("known_facts")
                .select("story_node_id")
                .eq("id", matched_id)
                .limit(1)
                .execute()
            )
            if response.data and response.data[0].get("story_node_id"):
                story_id = response.data[0]["story_node_id"]
                self._attach_fact_to_story(decision.alpha, story_id)
                return story_id
            else:
                # Matched fact has no story - create one and attach both
                logger.info(
                    f"Matched fact {matched_id} has no story. "
                    "Creating a new story for the pair."
                )
                story_id = self._create_story(decision.alpha, topic_id)
                # Also link the matched fact to the new story
                self._link_fact_to_story(matched_id, story_id)
                return story_id
        except Exception as e:
            logger.error(f"Failed to look up matched fact story: {e}")
            return self._assign_new(decision.alpha, topic_id)

    def _assign_new(self, alpha: Alpha, topic_id: Optional[str]) -> Optional[str]:
        """
        NEW Alpha: try to find a semantically similar existing story.
        If found → attach. Otherwise → create a new StoryNode.
        """
        if not topic_id:
            logger.warning("No topic_id - creating standalone story.")
            return self._create_story(alpha, topic_id)

        # Generate embedding for the alpha text (reuse if already present)
        embedding = alpha.embedding
        if not embedding:
            try:
                embedding = self.llm.embed(alpha.alpha_text)
            except Exception as e:
                logger.error(f"Failed to embed Alpha for story matching: {e}")
                return self._create_story(alpha, topic_id)

        # Search for similar stories via the match_stories RPC
        try:
            matches = self._find_similar_stories(embedding, topic_id)
        except Exception as e:
            logger.warning(f"Story matching failed: {e}. Creating new story.")
            return self._create_story(alpha, topic_id)

        if matches:
            best_story_id, best_score = matches[0]
            logger.info(
                f"Best story match: {best_story_id} "
                f"(similarity={best_score:.3f}, threshold={STORY_ASSIGNMENT_THRESHOLD})"
            )
            if best_score >= STORY_ASSIGNMENT_THRESHOLD:
                self._attach_fact_to_story(alpha, best_story_id)
                return best_story_id

        # No good match - create a new story
        return self._create_story(alpha, topic_id)

    # ──────────────────────────────────────────────────────────────────────────
    # Private: Database Operations
    # ──────────────────────────────────────────────────────────────────────────

    def _create_story(self, alpha: Alpha, topic_id: Optional[str]) -> Optional[str]:
        """
        Create a new StoryNode from an Alpha.

        The Alpha's text becomes the initial title, summary, and summary_embedding.
        The fact-to-story link is NOT set here - the caller (pipeline) passes
        story_node_id to VectorStore.add_fact(), which persists the link at insert time.
        For UPDATE facts whose matched_alpha already exists in the DB, _link_fact_to_story
        is called separately after creation.
        """
        # Title = first 200 chars of the fact text
        title = alpha.alpha_text[:200]

        # Embed the summary for future match_stories() queries (Task 3.2 dual-vector)
        try:
            summary_embedding = self.llm.embed(alpha.alpha_text)
        except Exception as e:
            logger.error(f"Failed to embed story summary: {e}")
            summary_embedding = None

        data = {
            "topic_id":          topic_id,
            "title":             title,
            "summary":           alpha.alpha_text,  # Initial summary = the first fact itself
            "summary_embedding": summary_embedding,
            "status":            StoryStatus.ACTIVE.value,
            "fact_count":        1,
        }

        try:
            response = self.db.table("story_nodes").insert(data).execute()
            if response.data:
                story_id = response.data[0]["id"]
                logger.info(f"Created StoryNode {story_id}: '{title[:60]}...'")
                return story_id
        except Exception as e:
            logger.error(f"Failed to create StoryNode: {e}")

        return None

    def _attach_fact_to_story(self, alpha: Alpha, story_node_id: str) -> None:
        """
        Attach an Alpha to an existing StoryNode.
        Updates the fact's story_node_id and increments the story's fact_count.
        """
        # Link the fact row to the story
        self._link_fact_to_story(alpha.id, story_node_id)

        # Increment fact_count and refresh updated_at using a direct SELECT + UPDATE.
        # (No custom RPC needed - keeps migration SQL simpler.)
        try:
            existing = (
                self.db.table("story_nodes")
                .select("fact_count")
                .eq("id", story_node_id)
                .limit(1)
                .execute()
            )
            if existing.data:
                new_count = (existing.data[0].get("fact_count") or 0) + 1
                self.db.table("story_nodes").update({
                    "fact_count": new_count,
                }).eq("id", story_node_id).execute()
                logger.info(
                    f"Attached fact '{alpha.alpha_text[:40]}...' "
                    f"to StoryNode {story_node_id} (fact_count={new_count})"
                )
        except Exception as e:
            logger.error(f"Failed to update story fact_count: {e}")

    def _link_fact_to_story(self, fact_id: str, story_node_id: str) -> None:
        """Set the story_node_id column on a known_facts row."""
        try:
            self.db.table("known_facts").update({
                "story_node_id": story_node_id
            }).eq("id", fact_id).execute()
        except Exception as e:
            logger.error(f"Failed to link fact {fact_id} to story {story_node_id}: {e}")

    def _find_similar_stories(
        self, embedding: list[float], topic_id: str
    ) -> List[Tuple[str, float]]:
        """
        Find StoryNodes whose summary_embedding is similar to the given embedding.
        Returns list of (story_node_id, similarity_score) tuples.
        """
        rpc_params = {
            "query_embedding": embedding,
            "match_threshold": STORY_ASSIGNMENT_THRESHOLD,
            "match_count": STORY_MATCH_LIMIT,
            "filter_topic_id": topic_id,
        }
        response = self.db.rpc("match_stories", rpc_params).execute()
        return [
            (row["id"], row["similarity"])
            for row in response.data
        ]

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_story(row: dict) -> StoryNode:
        """Convert a Supabase row dict into a StoryNode dataclass."""
        return StoryNode(
            id=row["id"],
            topic_id=row["topic_id"],
            title=row["title"],
            summary=row.get("summary", ""),
            status=StoryStatus(row.get("status", "active")),
            fact_count=row.get("fact_count", 0),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )
