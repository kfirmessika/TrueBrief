#!/usr/bin/env python3
"""
scripts/_integrity_redteam_run.py

Read-only runner for the 2026-08-13 /integrity red-team audit of the Arbiter/Judge
dedup cascade. Loads the 120 cases from scripts/_integrity_redteam_cases.py, runs
each through the REAL Arbiter (arbiter.py / judge.py / contradiction.py, unmodified)
against the live "iran war" topic ledger, and dumps raw per-case results to JSON.

HARD SAFETY CONSTRAINT: only Arbiter.judge_alpha() / judge_alphas() are called.
Neither calls VectorStore.add_fact() or any DB write — both only read via
find_similar() / find_tally_match() (RPC reads). This script must not add a single
row to known_facts. Verify with a topic fact-count query before and after running.

Usage:
    python scripts/_integrity_redteam_run.py
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(ROOT, ".env"))

# CRITICAL: local .env overrides EMBED_PROVIDER to "local" (free CPU sentence-transformers
# embedder). Production's Railway Worker does NOT set this var, so known_facts in the DB
# were embedded with EMBED_PROVIDER=gemini (gemini-embedding-2). Cosine similarity between
# a "local"-embedded query and "gemini"-embedded stored facts is meaningless (different
# embedding spaces, despite matching 768-dim) -- first run of this harness (pre-fix)
# produced verbatim-duplicate cases scoring raw/adjusted similarity 0.3-0.6 instead of
# ~1.0, which would have been reported as a false "dedup is broken" finding. Mirrors the
# same fix already applied in scripts/judge_accuracy_audit.py for this exact reason.
os.environ["EMBED_PROVIDER"] = "gemini"

logging.basicConfig(level=logging.WARNING)

from config.settings import settings  # noqa: E402
from truebrief.arbiter.arbiter import Arbiter  # noqa: E402
from truebrief.models.alpha import Alpha  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _integrity_redteam_cases import CASES, TOPIC_ID  # noqa: E402

DEFAULT_OUT_PATH = os.path.join(ROOT, "docs", "benchmarks", "_data", "2026-08-13_arbiter-redteam-results.json")

# ── Guardrails (added 2026-08-16 — catch the two classes of "silent wrong result"
# a prior LLM-analysis pass had to notice by eye: an embedding-space mismatch, and
# out-of-band DB writes during the run). Both are cheap deterministic checks, no LLM. ──

# Cases whose expected_decision is DUPLICATE via a verbatim/near-verbatim match against
# the ledger — if the embedder is misconfigured (e.g. local .env EMBED_PROVIDER=local
# instead of production's gemini), these score raw cosine ~0.3-0.6 instead of ~0.95+,
# and EVERY downstream result becomes silently meaningless. Checking a handful of known
# gimmes catches that before trusting 131 results built on top of it.
_SANITY_CHECK_IDS = {"C1-01", "C1-04", "C1-07", "C1-09", "C3-03", "C3-05", "C3-08"}
_SANITY_MIN_SIMILARITY = 0.85


def _known_facts_count(topic_id: str) -> int:
    from truebrief.ledger.database import get_supabase
    db = get_supabase()
    resp = db.table("known_facts").select("id", count="exact").eq("topic_id", topic_id).execute()
    return resp.count if resp.count is not None else len(resp.data)


def make_alpha(case: dict) -> Alpha:
    return Alpha(
        alpha_text=case["alpha_text"],
        entities=case["entities"],
        source_url="https://redteam.internal/synthetic",
        source_name="redteam-harness",
        event_date=case["event_date"],
        event_class=case.get("event_class"),
        context=case.get("context"),
        topic_id=TOPIC_ID,
        embedding=None,
    )


def decision_record(case: dict, decision, extra_note: str = "") -> dict:
    return {
        "id": case["id"],
        "category": case["category"],
        "alpha_text": case["alpha_text"],
        "expected_decision": case["expected_decision"],
        "actual_decision": decision.decision.value,
        "similarity_score": decision.similarity_score,
        "matched_alpha_id": decision.matched_alpha_id,
        "reasoning": decision.reasoning,
        "delta": decision.delta,
        "note": case["note"],
        "extra_note": extra_note,
        "error": None,
    }


def error_record(case: dict, exc: Exception) -> dict:
    return {
        "id": case["id"],
        "category": case["category"],
        "alpha_text": case["alpha_text"],
        "expected_decision": case["expected_decision"],
        "actual_decision": "ERROR",
        "similarity_score": None,
        "matched_alpha_id": None,
        "reasoning": None,
        "delta": None,
        "note": case["note"],
        "extra_note": "",
        "error": f"{type(exc).__name__}: {exc}",
    }


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT_PATH

    print("=" * 80)
    print("ARBITER RED-TEAM AUDIT RUNNER — READ-ONLY")
    print("=" * 80)
    print(f"TOPIC_ID = {TOPIC_ID}")
    print(f"Total cases loaded: {len(CASES)}")
    print(f"Output path: {out_path}")
    print()
    print("Live flag states (from config/settings.py + .env):")
    print(f"  V3_ENTITY_DEDUP       = {settings.V3_ENTITY_DEDUP}")
    print(f"  V3_CONTRADICTION_FLAG = {settings.V3_CONTRADICTION_FLAG}")
    print(f"  V3_TALLY_COLLAPSE     = {settings.V3_TALLY_COLLAPSE}")
    print(f"  V3_BATCH_JUDGE        = {settings.V3_BATCH_JUDGE}")
    print(f"  V3_DIGIT_GUARD        = {settings.V3_DIGIT_GUARD}")
    print()

    try:
        pre_count = _known_facts_count(TOPIC_ID)
        print(f"[GUARDRAIL] known_facts row count for topic (pre-run): {pre_count}")
    except Exception as exc:
        pre_count = None
        print(f"[GUARDRAIL] pre-run row count check failed (non-fatal, continuing): {exc}")
    print()

    arbiter = Arbiter()

    singles = [c for c in CASES if "batch_group" not in c]
    batch_groups = defaultdict(list)
    for c in CASES:
        if "batch_group" in c:
            batch_groups[c["batch_group"]].append(c)

    results = []

    # ── Singles: judge_alpha() one at a time ────────────────────────────────
    for i, case in enumerate(singles, start=1):
        print(f"[{i}/{len(singles)}] {case['id']} ({case['category']}) ... ", end="", flush=True)
        try:
            alpha = make_alpha(case)
            t0 = time.time()
            decision = arbiter.judge_alpha(alpha, topic_id=TOPIC_ID)
            dt = time.time() - t0
            rec = decision_record(case, decision)
            results.append(rec)
            print(f"{decision.decision.value} (expected {case['expected_decision']}) [{dt:.1f}s]")
        except Exception as exc:  # noqa: BLE001 — red-team harness must never die mid-run
            traceback.print_exc()
            results.append(error_record(case, exc))
            print(f"ERROR: {exc}")

    # ── C12 batches: judge_alphas() once per batch_group, in batch_order ───
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
                rec = decision_record(c, decision, extra_note=f"batch_group={group_name}")
                results.append(rec)
            print(f"{[d.decision.value for d in decisions]} (expected {[c['expected_decision'] for c in group_cases]}) [{dt:.1f}s]")
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            for c in group_cases:
                results.append(error_record(c, exc))
            print(f"ERROR: {exc}")

    # ── Guardrail 1: embedding-space sanity check ───────────────────────────
    # If these known-verbatim/near-verbatim cases don't score high similarity, the
    # embedder is misconfigured (e.g. local .env EMBED_PROVIDER mismatch vs prod) and
    # every other result in this run is meaningless. Fail loudly instead of writing
    # 131 silently-wrong results.
    by_id = {r["id"]: r for r in results}
    sanity_scores = [by_id[cid]["similarity_score"] for cid in _SANITY_CHECK_IDS
                      if cid in by_id and by_id[cid]["similarity_score"] is not None]
    if sanity_scores:
        avg_sanity = sum(sanity_scores) / len(sanity_scores)
        print(f"[GUARDRAIL] embedding sanity check: avg similarity on {len(sanity_scores)} "
              f"known-verbatim cases = {avg_sanity:.3f} (need >= {_SANITY_MIN_SIMILARITY})")
        if avg_sanity < _SANITY_MIN_SIMILARITY:
            print(
                "\n[GUARDRAIL FAILED] Known-verbatim duplicate cases scored implausibly low "
                "similarity — this almost always means the embedder is misconfigured (e.g. "
                "EMBED_PROVIDER=local in .env vs production's gemini), making every result in "
                "this run meaningless. Results were NOT written. Check EMBED_PROVIDER and re-run."
            )
            sys.exit(2)
    else:
        print("[GUARDRAIL] embedding sanity check: SKIPPED (no sanity-check case results found)")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "run_at": datetime.utcnow().isoformat(),
                "topic_id": TOPIC_ID,
                "total_cases": len(CASES),
                "flags": {
                    "V3_ENTITY_DEDUP": settings.V3_ENTITY_DEDUP,
                    "V3_CONTRADICTION_FLAG": settings.V3_CONTRADICTION_FLAG,
                    "V3_TALLY_COLLAPSE": settings.V3_TALLY_COLLAPSE,
                    "V3_BATCH_JUDGE": settings.V3_BATCH_JUDGE,
                    "V3_DIGIT_GUARD": settings.V3_DIGIT_GUARD,
                },
                "results": results,
            },
            f,
            indent=2,
            default=str,
        )

    print()
    print(f"Wrote {len(results)} results to {out_path}")
    n_error = sum(1 for r in results if r["actual_decision"] == "ERROR")
    print(f"Errors: {n_error}")

    # ── Guardrail 2: no-write confirmation ──────────────────────────────────
    if pre_count is not None:
        try:
            post_count = _known_facts_count(TOPIC_ID)
            print(f"[GUARDRAIL] known_facts row count for topic (post-run): {post_count}")
            if post_count != pre_count:
                print(
                    f"\n[GUARDRAIL WARNING] Row count changed during this run: {pre_count} -> "
                    f"{post_count} (delta {post_count - pre_count}). This harness only calls "
                    "judge_alpha()/judge_alphas(), which are read-only (find_similar/"
                    "find_tally_match RPCs) — grep this file and _integrity_redteam_cases.py "
                    "for add_fact/INSERT/UPDATE/DELETE to confirm. If it's really zero writes "
                    "here, something ELSE touched this table during the run window — flag it, "
                    "don't assume the harness caused it, but don't ignore it either."
                )
            else:
                print("[GUARDRAIL] row count unchanged — consistent with a read-only run.")
        except Exception as exc:
            print(f"[GUARDRAIL] post-run row count check failed (non-fatal): {exc}")


if __name__ == "__main__":
    main()
