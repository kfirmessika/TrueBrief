"""Backfill Migration 022: topic_embedding (raw_query) + relevance.

Embeds every topic using the user's raw_query exactly as typed — NOT the
pipeline-expanded topic_name (e.g. "Israel Geopolitical Situation").

The expanded name dilutes the embedding toward generic space, producing a flat
cosine distribution across all facts. The raw query sits at a tighter semantic
point and gives a wider, more meaningful score spread after per-topic normalization.

Then recomputes relevance for ALL known_facts using the corrected embeddings.

Run from project root:
    python scripts/backfill_relevance.py
"""

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "src"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(_ROOT, ".env"))

import numpy as np  # noqa: E402
from truebrief.ledger.database import get_supabase  # noqa: E402
from truebrief.llm.client import LLMClient  # noqa: E402


def cosine(a: list, b: list) -> float:
    av, bv = np.array(a, dtype=float), np.array(b, dtype=float)
    d = np.linalg.norm(av) * np.linalg.norm(bv)
    return float(np.dot(av, bv) / d) if d > 0 else 0.0


def main() -> None:
    db = get_supabase()
    llm = LLMClient()

    # ── 1. Re-embed ALL topic embeddings using raw_query ──────────────────────
    topics_res = db.table("topics").select("id,raw_query").execute()
    topic_embeddings: dict[str, list[float]] = {}

    print(f"Re-embedding {len(topics_res.data or [])} topics using raw_query...\n")
    for t in topics_res.data or []:
        try:
            text = t["raw_query"]
            print(f"  embedding raw_query: {text!r}")
            embedding = llm.embed(text)
            db.table("topics").update({"topic_embedding": embedding}).eq("id", t["id"]).execute()
            topic_embeddings[t["id"]] = embedding
        except Exception as exc:
            print(f"  WARN: could not embed topic {t['id']!r}: {exc}")

    print(f"\nTopics re-embedded: {len(topic_embeddings)}")

    # ── 2. Recompute relevance for ALL facts using updated topic embeddings ────
    # Uses in-memory embeddings (avoids re-fetching from DB and the json-string issue).
    print("\nRecomputing relevance for all facts...\n")
    facts_updated = 0
    for topic_id, topic_emb in topic_embeddings.items():
        try:
            facts_res = (
                db.table("known_facts")
                .select("id,alpha_embedding")
                .eq("topic_id", topic_id)
                .execute()
            )
            rows = facts_res.data or []
            for f in rows:
                fact_emb = f.get("alpha_embedding")
                if not fact_emb:
                    continue
                if isinstance(fact_emb, str):
                    fact_emb = json.loads(fact_emb)
                rel = cosine(fact_emb, topic_emb)
                db.table("known_facts").update({"relevance": rel}).eq("id", f["id"]).execute()
                facts_updated += 1
            print(f"  topic {topic_id}: {len(rows)} facts updated")
        except Exception as exc:
            print(f"  WARN: relevance update failed for topic {topic_id}: {exc}")

    print(f"\nFacts updated: {facts_updated}")
    print("Done.")


if __name__ == "__main__":
    main()
