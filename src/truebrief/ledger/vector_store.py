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
            "source_domain":   extract_domain(alpha.source_url),  # "reuters.com", not "Reuters"
        }

        # Phase 3: Link fact to its StoryNode (if set by StoryManager)
        if story_node_id:
            data["story_node_id"] = story_node_id

        try:
            # We explicitly don't pass an ID so Supabase generates a valid UUID
            response = self.db.table("known_facts").insert(data).execute()
            if response.data:
                # Update the alpha with the DB-assigned ID
                alpha.id = response.data[0]["id"]
            return alpha
        except Exception as e:
            logger.error(f"Failed to insert fact into Supabase: {e}")
            raise

    def find_similar(
        self, 
        embedding: list[float], 
        topic_id: Optional[str] = None, 
        limit: int = 5,
        threshold: float = 0.70
    ) -> List[Tuple[Alpha, float]]:
        """
        Find similar known facts using pgvector cosine distance.
        Supabase requires an RPC call to do distance calculations efficiently.
        """
        try:
            # Note: For production pgvector queries in Supabase, you usually create a matching function (RPC).
            # To avoid requiring the user to run complex SQL RPC definitions right now, 
            # we will do a basic threshold match using a standard RPC if available, or just fetch and compare in Python
            # as a fallback if the RPC is missing.
            
            # Assuming an RPC `match_facts` exists:
            # create or replace function match_facts(query_embedding vector(768), match_threshold float, match_count int, filter_topic_id uuid)
            
            # Since we can't guarantee the RPC exists yet without running it, we'll try the RPC first.
            rpc_params = {
                "query_embedding": embedding,
                "match_threshold": threshold,
                "match_count": limit,
                "filter_topic_id": topic_id
            }
            
            response = self.db.rpc("match_facts", rpc_params).execute()
            
            results = []
            for item in response.data:
                # Reconstruct Alpha
                alpha = Alpha(
                    id=item.get("id"),
                    topic_id=item.get("topic_id"),
                    alpha_text=item.get("alpha_text"),
                    entities=item.get("entities", []),
                    source_url=item.get("source_url", ""),
                    source_name=item.get("source_domain", ""),
                    event_date=item.get("event_date"), # Requires parsing in real app
                    context=item.get("context"),
                    confidence=item.get("confidence", 1.0)
                )
                score = item.get("similarity", 0.0)
                results.append((alpha, score))
                
            return results
            
        except Exception as e:
            logger.error(f"Error querying similar facts: {e}")
            # If RPC fails (likely because it's not created), return empty list for now.
            # In a real setup we'd instruct the user to run the migration.
            logger.warning("Make sure you have created the `match_facts` RPC in Supabase.")
            return []
