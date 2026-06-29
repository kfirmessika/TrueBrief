"""
Vector Store - ledger/vector_store.py

Manages storing and querying Alphas with embeddings in Supabase using pgvector.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from supabase import Client
from truebrief.ledger.database import get_supabase
from truebrief.ledger.source_logger import extract_domain
from truebrief.models.alpha import Alpha
from truebrief.llm.client import LLMClient

logger = logging.getLogger(__name__)

class VectorStore:
    """
    Pillar 3: Memory.
    Provides semantic search over known facts.
    """

    def __init__(self, supabase_client: Optional[Client] = None, llm_client: Optional[LLMClient] = None):
        self.db = supabase_client or get_supabase()
        self.llm = llm_client or LLMClient()

    def add_fact(self, alpha: Alpha, story_node_id: Optional[str] = None) -> Alpha:
        """
        Generate an embedding and store the fact in the database.
        Returns the Alpha with its ID and embedding populated.

        Args:
            alpha:         The fact to store.
            story_node_id: Optional StoryNode ID to link this fact to (Phase 3).
        """
        logger.info(f"Adding fact to ledger: {alpha.alpha_text[:50]}...")
        
        if not alpha.embedding:
            alpha.embedding = self.llm.embed(alpha.alpha_text)

        # Convert to DB dict
        data = {
            "topic_id":        alpha.topic_id,
            "alpha_text":      alpha.alpha_text,
            "alpha_embedding": alpha.embedding,
            "entities":        alpha.entities,
            "event_date":      alpha.event_date.isoformat() if alpha.event_date else None,
            "context":         alpha.context,
            "confidence":      alpha.confidence,
            "source_url":      alpha.source_url,
            "source_domain":   extract_domain(alpha.source_url),
            "verified_count":  alpha.verified_count,
            "verifier_flags":  alpha.verifier_flags,
            "event_class":     alpha.event_class,
        }

        # Phase 3: Link fact to its StoryNode (if set by StoryManager)
        if story_node_id:
            data["story_node_id"] = story_node_id

        # Migration 021: two-clock fields and importance.
        # Only include when present — pre-021 databases accept the insert without them.
        if getattr(alpha, "date_basis", None):
            data["date_basis"] = alpha.date_basis
        if getattr(alpha, "published_at", None):
            data["published_at"] = alpha.published_at.isoformat()
        if getattr(alpha, "importance", None) is not None:
            data["importance"] = alpha.importance

        # IC4: only include the contradiction columns when this fact is actually
        # flagged, so pre-migration topics never carry the keys for nothing.
        if alpha.contradicts_id:
            data["contradicts_id"] = alpha.contradicts_id
            data["contradiction_note"] = alpha.contradiction_note

        try:
            # We explicitly don't pass an ID so Supabase generates a valid UUID
            response = self.db.table("known_facts").insert(data).execute()
        except Exception as e:
            # Pre-migration fallback: if migration 021 columns aren't applied yet,
            # retry without them. Same pattern as the IC4 fallback below.
            if any(k in data for k in ("date_basis", "published_at", "importance")):
                logger.warning(
                    f"Insert with migration-021 columns failed ({e}); retrying without them "
                    "(apply migration 021 to persist two-clock fields)."
                )
                data.pop("date_basis", None)
                data.pop("published_at", None)
                data.pop("importance", None)
                try:
                    response = self.db.table("known_facts").insert(data).execute()
                except Exception as e2:
                    # Pre-migration fallback: if the IC4 columns (migration 015) aren't applied
                    # yet, retry once without them so fact storage never breaks.
                    if "contradicts_id" in data:
                        logger.warning(
                            f"Insert with IC4 columns failed ({e2}); retrying without them "
                            "(apply migration 015 to persist contradiction flags)."
                        )
                        data.pop("contradicts_id", None)
                        data.pop("contradiction_note", None)
                        response = self.db.table("known_facts").insert(data).execute()
                    else:
                        logger.error(f"Failed to insert fact into Supabase: {e2}")
                        raise
            elif "contradicts_id" in data:
                # Pre-migration fallback: if the IC4 columns (migration 015) aren't applied
                # yet, retry once without them so fact storage never breaks.
                logger.warning(
                    f"Insert with IC4 columns failed ({e}); retrying without them "
                    "(apply migration 015 to persist contradiction flags)."
                )
                data.pop("contradicts_id", None)
                data.pop("contradiction_note", None)
                response = self.db.table("known_facts").insert(data).execute()
            else:
                logger.error(f"Failed to insert fact into Supabase: {e}")
                raise

        if response.data:
            # Update the alpha with the DB-assigned ID
            alpha.id = response.data[0]["id"]
        return alpha

    def get_seen_urls(self, topic_id: Optional[str], days: int = 14) -> set:
        """
        Return the set of source_url values already stored for this topic
        within the last `days` days.  Used to skip re-processing the same
        articles across pipeline runs.
        """
        if not topic_id:
            return set()
        try:
            from datetime import datetime, timedelta
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
            response = (
                self.db.table("known_facts")
                .select("source_url")
                .eq("topic_id", topic_id)
                .gte("first_seen_at", cutoff)
                .execute()
            )
            return {row["source_url"] for row in response.data if row.get("source_url")}
        except Exception as e:
            logger.warning(f"get_seen_urls failed (non-fatal): {e}")
            return set()

    def find_similar(
        self,
        embedding: list[float],
        topic_id: Optional[str] = None,
        limit: int = 5,
        threshold: float = 0.70
    ) -> List[Tuple[Alpha, float]]:
        """
        Find similar known facts using pgvector cosine distance via match_facts RPC.

        PostgREST cannot cast a JSON array to pgvector's vector type — there is no
        implicit json→vector cast registered in PostgreSQL. Passing embedding as a
        pgvector-format string ("[0.1,0.2,...]") triggers the text→vector input
        function instead, which works correctly.
        """
        # Serialize to pgvector text format: "[v1,v2,...]"
        # Using list() first handles Gemini's RepeatedScalarFieldContainer.
        embedding_str = "[" + ",".join(f"{float(v):.8f}" for v in list(embedding)) + "]"

        rpc_params = {
            "query_embedding": embedding_str,
            "match_threshold": threshold,
            "match_count": limit,
            "filter_topic_id": topic_id,
        }

        response = self.db.rpc("match_facts", rpc_params).execute()

        results = []
        for item in response.data:
            alpha = Alpha(
                id=item.get("id"),
                topic_id=item.get("topic_id"),
                alpha_text=item.get("alpha_text"),
                entities=item.get("entities", []),
                source_url=item.get("source_url", ""),
                source_name=item.get("source_domain", ""),
                event_date=item.get("event_date"),
                context=item.get("context"),
                confidence=item.get("confidence", 1.0),
                event_class=item.get("event_class"),
            )
            score = item.get("similarity", 0.0)
            results.append((alpha, score))

        logger.debug(f"find_similar: {len(results)} matches (threshold={threshold}, topic={topic_id})")
        return results

    def find_tally_match(
        self,
        alpha: Alpha,
        min_entity_overlap: float = 0.5,
    ) -> Optional[Alpha]:
        """
        IC1 (V3_TALLY_COLLAPSE): find an existing tally fact for the same entities.

        Used when the incoming alpha has event_class='tally'. We skip vector similarity
        (wording varies too much across tallies) and use entity overlap instead.
        Returns the most-recent matching stored tally, or None.
        """
        if not alpha.topic_id or not alpha.entities:
            return None
        try:
            response = (
                self.db.table("known_facts")
                .select("id, alpha_text, entities, event_date, source_url, source_domain, context, confidence, event_class")
                .eq("topic_id", alpha.topic_id)
                .eq("event_class", "tally")
                .order("event_date", desc=True)
                .limit(20)
                .execute()
            )
        except Exception as e:
            logger.warning(f"find_tally_match query failed (non-fatal): {e}")
            return None

        incoming_set = {e.lower() for e in alpha.entities}
        for row in response.data:
            stored_entities = {e.lower() for e in (row.get("entities") or [])}
            if not stored_entities:
                continue
            overlap = len(incoming_set & stored_entities) / max(len(incoming_set | stored_entities), 1)
            if overlap >= min_entity_overlap:
                return Alpha(
                    id=row.get("id"),
                    topic_id=alpha.topic_id,
                    alpha_text=row.get("alpha_text", ""),
                    entities=row.get("entities", []),
                    source_url=row.get("source_url", ""),
                    source_name=row.get("source_domain", ""),
                    event_date=row.get("event_date"),
                    context=row.get("context"),
                    confidence=row.get("confidence", 1.0),
                    event_class=row.get("event_class"),
                )
        return None
