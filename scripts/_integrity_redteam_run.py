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

OUT_PATH = os.path.join(ROOT, "docs", "benchmarks", "_data", "2026-08-13_arbiter-redteam-results.json")


def make_alpha(case: dict) -> Alpha:
    return Alpha(
        alpha_text=case["alpha_text"],
        entities=case["entities"],
        source_url="https://redteam.internal/synthetic",
        source_name="redteam-harness",
        event_date=case["event_date"],
        event_class=case.get("event_class"),
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
    print("=" * 80)
    print("ARBITER RED-TEAM AUDIT RUNNER — 2026-08-13 — READ-ONLY")
    print("=" * 80)
    print(f"TOPIC_ID = {TOPIC_ID}")
    print(f"Total cases loaded: {len(CASES)}")
    print()
    print("Live flag states (from config/settings.py + .env):")
    print(f"  V3_ENTITY_DEDUP       = {settings.V3_ENTITY_DEDUP}")
    print(f"  V3_CONTRADICTION_FLAG = {settings.V3_CONTRADICTION_FLAG}")
    print(f"  V3_TALLY_COLLAPSE     = {settings.V3_TALLY_COLLAPSE}")
    print(f"  V3_BATCH_JUDGE        = {settings.V3_BATCH_JUDGE}")
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

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
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
                },
                "results": results,
            },
            f,
            indent=2,
            default=str,
        )

    print()
    print(f"Wrote {len(results)} results to {OUT_PATH}")
    n_error = sum(1 for r in results if r["actual_decision"] == "ERROR")
    print(f"Errors: {n_error}")


if __name__ == "__main__":
    main()
