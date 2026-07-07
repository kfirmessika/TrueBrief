"""
Vector Store - ledger/vector_store.py

Manages storing and querying Alphas with embeddings in Supabase using pgvector.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import List, Optional, Tuple

import numpy as np

from supabase import Client
from truebrief.ledger.database import get_supabase
from truebrief.ledger.source_logger import extract_domain
from truebrief.models.alpha import Alpha
from truebrief.llm.client import LLMClient
from config.settings import settings

logger = logging.getLogger(__name__)


def _cosine(a: list, b: list) -> float:
    """Cosine similarity between two equal-length float vectors."""
    av, bv = np.array(a, dtype=float), np.array(b, dtype=float)
    denom = np.linalg.norm(av) * np.linalg.norm(bv)
    return float(np.dot(av, bv) / denom) if denom > 0 else 0.0


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

        # Migration 022: compute cosine similarity between the fact embedding and the
        # topic embedding so downstream features can rank facts by relevance.
        if alpha.topic_id and alpha.embedding:
            try:
                t_row = (
                    self.db.table("topics")
                    .select("topic_embedding")
                    .eq("id", alpha.topic_id)
                    .single()
                    .execute()
                )
                topic_emb = t_row.data.get("topic_embedding") if t_row.data else None
                if topic_emb:
                    if isinstance(topic_emb, str):
                        topic_emb = json.loads(topic_emb)
                    data["relevance"] = _cosine(alpha.embedding, topic_emb)
            except Exception as _rel_err:
                logger.warning("Relevance computation failed (non-fatal): %s", _rel_err)

        # Migration 025: signal scorer columns. Only include when set so pre-025
        # databases accept the insert without them.
        if getattr(alpha, "signal_score", None) is not None:
            data["signal_score"] = alpha.signal_score
        if getattr(alpha, "signal_class", None) is not None:
            data["signal_class"] = alpha.signal_class

        # IC4: only include the contradiction columns when this fact is actually
        # flagged, so pre-migration topics never carry the keys for nothing.
        if alpha.contradicts_id:
            data["contradicts_id"] = alpha.contradicts_id
            data["contradiction_note"] = alpha.contradiction_note

        # Pre-migration fallbacks: on insert failure, strip optional column groups
        # (newest migration first) and retry, so fact storage never breaks on a DB
        # that hasn't had the latest migrations applied yet.
        _optional_groups = [
            ("migration 025 (signal columns)", ("signal_score", "signal_class")),
            ("migration 021 (two-clock fields)", ("date_basis", "published_at", "importance")),
            ("migration 015 (IC4 contradiction flags)", ("contradicts_id", "contradiction_note")),
        ]
        while True:
            try:
                # We explicitly don't pass an ID so Supabase generates a valid UUID
                response = self.db.table("known_facts").insert(data).execute()
                break
            except Exception as e:
                stripped = False
                for label, cols in _optional_groups:
                    if any(k in data for k in cols):
                        logger.warning(
                            f"Insert failed ({e}); retrying without {label} columns — "
                            f"apply {label} to persist them."
                        )
                        for k in cols:
                            data.pop(k, None)
                        stripped = True
                        break
                if not stripped:
                    logger.error(f"Failed to insert fact into Supabase: {e}")
                    raise

        if response.data:
            # Update the alpha with the DB-assigned ID
            alpha.id = response.data[0]["id"]

        # V4-4: fire-and-forget stitch generation for the new fact's adjacent pairs.
        # Runs in a daemon thread so it never blocks the pipeline. All exceptions
        # are caught internally — this path must never propagate an error.
        if settings.V4_STORY_STITCHING and alpha.id and alpha.topic_id:
            t = threading.Thread(
                target=self._generate_adjacent_stitches,
                args=(alpha,),
                daemon=True,
            )
            t.start()

        return alpha

    def _generate_adjacent_stitches(self, new_alpha: Alpha) -> None:
        """V4-4: Generate and cache stitch sentences for the pairs that include new_alpha.

        Fetches the immediately older and newer facts for the same topic (by event_date),
        then calls the LLM for each pair and upserts into fact_stitches. Entirely
        non-fatal — any exception is logged and swallowed.
        """
        try:
            db = get_supabase()

            # --- Fetch 1 older neighbor (latest fact strictly before this one) ---
            older_rows = (
                db.table("known_facts")
                .select("id, alpha_text, event_date")
                .eq("topic_id", new_alpha.topic_id)
                .neq("id", new_alpha.id)
                .lt("event_date", new_alpha.event_date.isoformat() if new_alpha.event_date else "9999-01-01")
                .order("event_date", desc=True)
                .limit(1)
                .execute()
            )

            # --- Fetch 1 newer neighbor (earliest fact strictly after this one) ---
            newer_rows = (
                db.table("known_facts")
                .select("id, alpha_text, event_date")
                .eq("topic_id", new_alpha.topic_id)
                .neq("id", new_alpha.id)
                .gt("event_date", new_alpha.event_date.isoformat() if new_alpha.event_date else "0001-01-01")
                .order("event_date", desc=False)
                .limit(1)
                .execute()
            )

            # Fetch topic name for the prompt
            topic_res = (
                db.table("topics")
                .select("raw_query")
                .eq("id", new_alpha.topic_id)
                .single()
                .execute()
            )
            topic_name = topic_res.data.get("raw_query", "") if topic_res.data else ""

            llm = self.llm

            # Build pairs: (before_fact, after_fact) where new_alpha is one member each time
            pairs: list[tuple[dict, dict]] = []

            if older_rows.data:
                older = older_rows.data[0]
                # older is the BEFORE fact, new_alpha is the AFTER fact
                pairs.append((older, {"id": new_alpha.id, "alpha_text": new_alpha.alpha_text}))

            if newer_rows.data:
                newer = newer_rows.data[0]
                # new_alpha is the BEFORE fact, newer is the AFTER fact
                pairs.append(({"id": new_alpha.id, "alpha_text": new_alpha.alpha_text}, newer))

            for before, after in pairs:
                try:
                    prompt = (
                        f"Topic: {topic_name}\n"
                        f"Fact A: {before['alpha_text']}\n"
                        f"Fact B: {after['alpha_text']}\n\n"
                        f"Write ONE sentence (max 18 words) connecting A to B. "
                        f'Return JSON: {{"passage": "..."}}.'
                    )
                    raw = llm.call(
                        step_name="story_stitch",
                        prompt=prompt,
                        json_mode=True,
                    )
                    parsed = json.loads(raw)
                    passage = str(parsed.get("passage", "")).strip()
                    if not passage:
                        continue

                    stitch_data = {
                        "topic_id": new_alpha.topic_id,
                        "before_fact_id": str(before["id"]),
                        "after_fact_id": str(after["id"]),
                        "passage": passage,
                    }
                    # ON CONFLICT DO NOTHING: if this stitch already exists, skip silently.
                    db.table("fact_stitches").upsert(
                        stitch_data,
                        on_conflict="topic_id,before_fact_id,after_fact_id",
                        ignore_duplicates=True,
                    ).execute()

                except Exception as pair_err:
                    logger.warning(
                        "V4-4 stitch generation failed for pair (%s, %s): %s",
                        before.get("id"), after.get("id"), pair_err,
                    )

        except Exception as exc:
            logger.warning("V4-4 _generate_adjacent_stitches failed (non-fatal): %s", exc)

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
