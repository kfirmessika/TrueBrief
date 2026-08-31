#!/usr/bin/env python3
"""
scripts/_integrity_redteam_run_local_embed.py

Same 131-case red-team audit as `_integrity_redteam_run.py`, run against the REAL
Arbiter (unmodified) against the SAME live "iran war" topic — but with EMBED_PROVIDER
forced to "local" (free CPU sentence-transformers) instead of "gemini", to answer:
how does dedup accuracy change if the embedder is swapped?

CRITICAL DIFFERENCE FROM THE GEMINI RUNNER: the topic's `known_facts` rows are
permanently stored with GEMINI embeddings (`alpha_embedding` column) -- setting
EMBED_PROVIDER=local only changes what NEW embed() calls produce, it does not
retroactively re-embed anything already in the DB. Comparing a local-embedded query
against Gemini-embedded stored facts would be meaningless (different embedding
spaces). So this script builds an in-memory `LocalVectorStore` that:
  1. Fetches the real fact TEXT (not the stored Gemini embedding) for every row in
     the topic via a plain read-only select.
  2. Re-embeds every one of those texts locally, in-memory, once at startup.
  3. Implements find_similar()/find_tally_match() as in-memory cosine search over
     that local-embedded pool, matching VectorStore's real method signatures/output
     shape so the real, unmodified Arbiter can't tell the difference.
No DB writes anywhere -- read-only, same safety contract as the Gemini runner.

CAVEAT (deliberately not glossed over): AUTO_MERGE_THRESHOLD (0.97), GREY_ZONE_MIN
(0.75), SAME_DAY_DUP_THRESHOLD (0.93) in arbiter.py were tuned and validated against
Gemini's embedding-space similarity distribution, not local's. A lower score here
does not by itself mean "local embeddings are worse" -- it may mean these thresholds
don't transfer, since a different model can cluster similarity scores differently
(e.g. paraphrases scoring lower, or unrelated text scoring higher, on average, under
one model vs another). This run answers "same thresholds, different embedder" --
not "local's best-achievable accuracy with its own tuned thresholds."

Usage:
    python scripts/_integrity_redteam_run_local_embed.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import traceback
from collections import defaultdict
from datetime import datetime
from typing import List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(ROOT, ".env"))

# The one deliberate difference from the Gemini runner's forced override.
os.environ["EMBED_PROVIDER"] = "local"

logging.basicConfig(level=logging.WARNING)

from config.settings import settings  # noqa: E402
from truebrief.arbiter.arbiter import Arbiter, _cosine  # noqa: E402
from truebrief.arbiter.temporal import entity_overlap  # noqa: E402
from truebrief.ledger.database import get_supabase  # noqa: E402
from truebrief.ledger.vector_store import VectorStore  # noqa: E402
from truebrief.llm.client import LLMClient  # noqa: E402
from truebrief.models.alpha import Alpha  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _integrity_redteam_cases import CASES, TOPIC_ID  # noqa: E402

OUT_PATH = os.path.join(
    ROOT, "docs", "benchmarks", "_data", "2026-08-13_arbiter-redteam-results-LOCAL-EMBED.json"
)


class LocalVectorStore(VectorStore):
    """VectorStore whose find_similar()/find_tally_match() search an in-memory pool
    of the topic's real facts, re-embedded locally at startup -- see module docstring
    for why this is necessary (mixing embedding spaces is meaningless). Everything
    else (add_fact, etc.) is inherited unchanged but never called by this harness.
    """

    def __init__(self, topic_id: str):
        super().__init__()
        self.llm = LLMClient()  # embed() reads settings.EMBED_PROVIDER = "local" now
        print(f"Fetching real fact text for topic {topic_id} (no embeddings, text only)...")
        resp = (
            self.db.table("known_facts")
            .select("id, alpha_text, entities, event_date, event_class, context, "
                    "source_url, source_domain, confidence")
            .eq("topic_id", topic_id)
            .execute()
        )
        rows = resp.data or []
        print(f"  {len(rows)} facts found. Locally re-embedding all of them (one-time)...")
        t0 = time.time()
        self._pool: List[Tuple[Alpha, List[float]]] = []
        for row in rows:
            text = row.get("alpha_text") or ""
            if not text:
                continue
            emb = self.llm.embed(text)
            alpha = Alpha(
                id=row.get("id"),
                topic_id=topic_id,
                alpha_text=text,
                entities=row.get("entities") or [],
                source_url=row.get("source_url", ""),
                source_name=row.get("source_domain", ""),
                event_date=row.get("event_date"),
                context=row.get("context"),
                confidence=row.get("confidence", 1.0),
                event_class=row.get("event_class"),
            )
            self._pool.append((alpha, emb))
        print(f"  Done in {time.time()-t0:.1f}s. Local-embedded pool size: {len(self._pool)}.")

    def find_similar(self, embedding, topic_id=None, limit=5, threshold=0.70):
        scored = []
        for alpha, emb in self._pool:
            s = _cosine(embedding, emb)
            if s >= threshold:
                scored.append((alpha, s))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    def find_tally_match(self, alpha: Alpha, min_entity_overlap: float = 0.5) -> Optional[Alpha]:
        if not alpha.topic_id or not alpha.entities:
            return None
        incoming_set = {e.lower() for e in alpha.entities}
        candidates = []
        for cand, emb in self._pool:
            if (cand.event_class or "") != "tally":
                continue
            stored_entities = {e.lower() for e in (cand.entities or [])}
            if not stored_entities:
                continue
            overlap = len(incoming_set & stored_entities) / max(len(incoming_set | stored_entities), 1)
            if overlap >= min_entity_overlap:
                candidates.append((cand, emb))
        if not candidates:
            return None
        if alpha.embedding:
            scored = [(cand, _cosine(alpha.embedding, emb)) for cand, emb in candidates]
            scored.sort(key=lambda pair: pair[1], reverse=True)
            return scored[0][0]
        return candidates[0][0]


def make_alpha(case: dict) -> Alpha:
    return Alpha(
        alpha_text=case["alpha_text"], entities=case["entities"],
        source_url="https://redteam.internal/synthetic", source_name="redteam-harness",
        event_date=case["event_date"], event_class=case.get("event_class"),
        context=case.get("context"), topic_id=TOPIC_ID, embedding=None,
    )


def decision_record(case, decision, extra_note=""):
    return {
        "id": case["id"], "category": case["category"], "alpha_text": case["alpha_text"],
        "expected_decision": case["expected_decision"], "actual_decision": decision.decision.value,
        "similarity_score": decision.similarity_score, "matched_alpha_id": decision.matched_alpha_id,
        "reasoning": decision.reasoning, "delta": decision.delta, "note": case["note"],
        "extra_note": extra_note, "error": None,
    }


def error_record(case, exc):
    return {
        "id": case["id"], "category": case["category"], "alpha_text": case["alpha_text"],
        "expected_decision": case["expected_decision"], "actual_decision": "ERROR",
        "similarity_score": None, "matched_alpha_id": None, "reasoning": None, "delta": None,
        "note": case["note"], "extra_note": "", "error": f"{type(exc).__name__}: {exc}",
    }


def main():
    print("=" * 80)
    print("ARBITER RED-TEAM AUDIT RUNNER -- LOCAL EMBEDDING -- READ-ONLY")
    print("=" * 80)
    print(f"TOPIC_ID = {TOPIC_ID}")
    print(f"Total cases loaded: {len(CASES)}")
    print(f"EMBED_PROVIDER = {os.environ['EMBED_PROVIDER']} (forced, same-thresholds-different-embedder test)")
    print()

    local_vs = LocalVectorStore(TOPIC_ID)
    arbiter = Arbiter(vector_store=local_vs)

    singles = [c for c in CASES if "batch_group" not in c]
    batch_groups = defaultdict(list)
    for c in CASES:
        if "batch_group" in c:
            batch_groups[c["batch_group"]].append(c)

    results = []
    for i, case in enumerate(singles, start=1):
        print(f"[{i}/{len(singles)}] {case['id']} ({case['category']}) ... ", end="", flush=True)
        try:
            alpha = make_alpha(case)
            t0 = time.time()
            decision = arbiter.judge_alpha(alpha, topic_id=TOPIC_ID)
            dt = time.time() - t0
            results.append(decision_record(case, decision))
            print(f"{decision.decision.value} (expected {case['expected_decision']}) [{dt:.1f}s]")
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            results.append(error_record(case, exc))
            print(f"ERROR: {exc}")

    for group_name in sorted(batch_groups.keys()):
        group_cases = sorted(batch_groups[group_name], key=lambda c: c["batch_order"])
        ids = [c["id"] for c in group_cases]
        print(f"[BATCH {group_name}] {ids} ... ", end="", flush=True)
        try:
            alphas = [make_alpha(c) for c in group_cases]
            t0 = time.time()
            decisions = arbiter.judge_alphas(alphas, topic_id=TOPIC_ID)
            dt = time.time() - t0
            for c, decision in zip(group_cases, decisions):
                results.append(decision_record(c, decision, extra_note=f"batch_group={group_name}"))
            print(f"{[d.decision.value for d in decisions]} (expected {[c['expected_decision'] for c in group_cases]}) [{dt:.1f}s]")
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            for c in group_cases:
                results.append(error_record(c, exc))
            print(f"ERROR: {exc}")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "run_at": datetime.utcnow().isoformat(), "topic_id": TOPIC_ID,
                "total_cases": len(CASES), "embed_provider": "local",
                "flags": {
                    "V3_ENTITY_DEDUP": settings.V3_ENTITY_DEDUP,
                    "V3_CONTRADICTION_FLAG": settings.V3_CONTRADICTION_FLAG,
                    "V3_TALLY_COLLAPSE": settings.V3_TALLY_COLLAPSE,
                    "V3_BATCH_JUDGE": settings.V3_BATCH_JUDGE,
                    "V3_DIGIT_GUARD": settings.V3_DIGIT_GUARD,
                },
                "results": results,
            },
            f, indent=2, default=str,
        )
    print(f"\nWrote {len(results)} results to {OUT_PATH}")
    print(f"Errors: {sum(1 for r in results if r['actual_decision'] == 'ERROR')}")


if __name__ == "__main__":
    main()
