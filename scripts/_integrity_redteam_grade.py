#!/usr/bin/env python3
"""
scripts/_integrity_redteam_grade.py

Grading pass for an Arbiter red-team audit run
(docs/benchmarks/_data/2026-08-13_arbiter-redteam-results.json by default — pass a
different path as argv[1] to grade a re-run against Stage 2 code, e.g. after
scripts/_integrity_redteam_run.py produces a fresh results file).

Read-only, no DB/LLM calls — pure Python over the already-collected JSON.
Computes strict + macro (PASS/FILTER) correctness, a confusion matrix on the
macro binary (positive class = FILTER), precision/recall/F1 overall, per
category, per cascade stage (fast-path vs Judge LLM), per INDIVIDUAL GATE
(IC1/IC4/raw-cosine/same-day/etc — added 2026-08-16 as a standing feature, not a
one-off, so every future cascade change gets this breakdown for free), plus an
embedding-only precision/recall subset (pure cosine-driven fast-path decisions,
no entity/contradiction/tally special-case).

Usage:
    python scripts/_integrity_redteam_grade.py [path/to/results.json]
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_RESULTS_PATH = os.path.join(ROOT, "docs", "benchmarks", "_data", "2026-08-13_arbiter-redteam-results.json")

PASS_DECISIONS = {"NEW", "UPDATE"}
FILTER_DECISIONS = {"DUPLICATE"}


def macro_bucket(decision: str) -> str:
    if decision in PASS_DECISIONS:
        return "PASS"
    if decision in FILTER_DECISIONS:
        return "FILTER"
    return "OTHER"  # ERROR / AMBIGUOUS


def stage_of(reasoning: str) -> str:
    if not reasoning:
        return "unknown"
    if reasoning.startswith("Judge LLM decision"):
        return "judge_llm"
    return "fast_path"


# Fast-path reasons that are driven PURELY by the vector/cosine signal (no
# entity-overlap special-case, no contradiction check, no tally-collapse,
# no same-day digit-run check). "Auto-merge"/"Highest adjusted score" (Steps 4/5)
# still fold in the V3_ENTITY_DEDUP entity factor multiplicatively, but that is
# the ambient adjustment applied to EVERY case, not a special-case gate firing —
# so they're counted as "embedding-stage" per the audit brief's own framing
# ("purely off similarity_score (no entity/contradiction/tally special-case fired)").
EMBEDDING_PURE_PREFIXES = (
    "Highest adjusted score",
    "Auto-merge:",
    "Raw-cosine auto-merge",
    "No similar facts found",
)
SPECIAL_CASE_PREFIXES = (
    "IC1 tally-collapse",
    "IC4 contradiction",
    "IC3 same-event",
    "Same-day near-identical",
)


def is_embedding_pure(reasoning: str) -> bool:
    if not reasoning:
        return False
    return any(reasoning.startswith(p) for p in EMBEDDING_PURE_PREFIXES)


def is_special_case(reasoning: str) -> bool:
    if not reasoning:
        return False
    return any(reasoning.startswith(p) for p in SPECIAL_CASE_PREFIXES)


# ── Per-gate breakdown (standing feature, added 2026-08-16 / Stage 2) ──────────
# Every fast-path gate (and the two catch-all thresholds) gets its own bucket,
# checked in this order — most specific prefix first, since "IC1 pre-check
# contradiction" and "IC1 tally-collapse" both start with "IC1" but mean
# different outcomes (NEW+flagged vs UPDATE/DUPLICATE).
GATE_PREFIX_ORDER = [
    ("IC1 pre-check contradiction", "IC1_precheck_contradiction"),
    ("IC1 tally-collapse", "IC1_tally_collapse"),
    ("IC4 contradiction", "IC4_contradiction"),
    # IC3 was deleted in Stage 2 (2026-08-16) — this prefix can only appear in a
    # PRE-Stage-2 results file (e.g. the 2026-08-13 baseline), kept here so the
    # same grader can compare before/after on the same axis.
    ("IC3 same-event", "IC3_same_event_DELETED_in_stage2"),
    ("Raw-cosine auto-merge", "raw_cosine_auto_merge"),
    ("Same-day near-identical", "same_day_near_identical"),
    ("Auto-merge:", "auto_merge_score_threshold"),
    ("Highest adjusted score", "auto_new_score_threshold"),
    ("No similar facts found", "auto_new_zero_matches"),
    ("Embedding generation failed", "embedding_failure"),
    ("Judge LLM decision", "judge_llm"),
]


def gate_of(reasoning: str) -> str:
    if not reasoning:
        return "unknown"
    for prefix, label in GATE_PREFIX_ORDER:
        if reasoning.startswith(prefix):
            return label
    return "other"


def confusion(rows):
    tp = fp = fn = tn = 0
    for r in rows:
        exp_b = macro_bucket(r["expected_decision"])
        act_b = macro_bucket(r["actual_decision"])
        if exp_b == "FILTER" and act_b == "FILTER":
            tp += 1
        elif exp_b == "PASS" and act_b == "FILTER":
            fp += 1
        elif exp_b == "FILTER" and act_b == "PASS":
            fn += 1
        elif exp_b == "PASS" and act_b == "PASS":
            tn += 1
    return tp, fp, fn, tn


def prf(tp, fp, fn, tn):
    n = tp + fp + fn + tn
    acc = (tp + tn) / n if n else 0.0
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {"n": n, "tp": tp, "fp": fp, "fn": fn, "tn": tn, "accuracy": acc, "precision": prec, "recall": rec, "f1": f1}


def strict_macro_accuracy(rows):
    n = len(rows)
    if n == 0:
        return 0.0, 0.0
    strict = sum(1 for r in rows if r["actual_decision"] == r["expected_decision"]) / n
    macro = sum(1 for r in rows if macro_bucket(r["actual_decision"]) == macro_bucket(r["expected_decision"])) / n
    return strict, macro


def main():
    results_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_RESULTS_PATH
    grading_out = os.path.splitext(results_path)[0].replace("-results", "-grading") + ".json"
    if grading_out == results_path:  # fallback if the filename didn't match the *-results.json convention
        grading_out = results_path.replace(".json", "-grading.json")

    data = json.load(open(results_path, encoding="utf-8"))
    all_results = data["results"]

    ambiguous = [r for r in all_results if r["expected_decision"] == "AMBIGUOUS"]
    errors = [r for r in all_results if r["actual_decision"] == "ERROR"]
    gradable = [r for r in all_results if r["expected_decision"] != "AMBIGUOUS"]

    for r in gradable:
        r["_stage"] = stage_of(r["reasoning"] or "")
        r["_embedding_pure"] = is_embedding_pure(r["reasoning"] or "")
        r["_special_case"] = is_special_case(r["reasoning"] or "")
        r["_gate"] = gate_of(r["reasoning"] or "")
        r["_strict_correct"] = r["actual_decision"] == r["expected_decision"]
        r["_macro_correct"] = macro_bucket(r["actual_decision"]) == macro_bucket(r["expected_decision"])

    overall_strict, overall_macro = strict_macro_accuracy(gradable)
    overall_conf = confusion(gradable)
    overall_prf = prf(*overall_conf)

    # Per category
    by_cat = defaultdict(list)
    for r in gradable:
        by_cat[r["category"]].append(r)
    cat_stats = {}
    for cat, rows in sorted(by_cat.items()):
        strict, macro = strict_macro_accuracy(rows)
        conf = confusion(rows)
        p = prf(*conf)
        cat_stats[cat] = {
            "n": len(rows),
            "strict_accuracy": strict,
            "macro_accuracy": macro,
            "precision": p["precision"],
            "recall": p["recall"],
            "f1": p["f1"],
            "confusion": conf,
            "failures": [r["id"] for r in rows if not r["_strict_correct"]],
        }

    # Per stage
    fast_path_rows = [r for r in gradable if r["_stage"] == "fast_path"]
    judge_rows = [r for r in gradable if r["_stage"] == "judge_llm"]
    stage_stats = {}
    for name, rows in [("fast_path", fast_path_rows), ("judge_llm", judge_rows)]:
        strict, macro = strict_macro_accuracy(rows)
        conf = confusion(rows)
        p = prf(*conf)
        stage_stats[name] = {
            "n": len(rows),
            "strict_accuracy": strict,
            "macro_accuracy": macro,
            "precision": p["precision"],
            "recall": p["recall"],
            "f1": p["f1"],
        }

    # Per gate (standing feature — see gate_of() above)
    by_gate = defaultdict(list)
    for r in gradable:
        by_gate[r["_gate"]].append(r)
    gate_stats = {}
    for gate, rows in sorted(by_gate.items(), key=lambda kv: -len(kv[1])):
        strict, macro = strict_macro_accuracy(rows)
        conf = confusion(rows)
        p = prf(*conf)
        gate_stats[gate] = {
            "n": len(rows),
            "strict_accuracy": strict,
            "macro_accuracy": macro,
            "precision": p["precision"],
            "recall": p["recall"],
            "f1": p["f1"],
            "failures": [r["id"] for r in rows if not r["_strict_correct"]],
        }

    # Embedding-pure subset (fast-path DUPLICATE/NEW decisions with NO special-case)
    embed_pure_rows = [r for r in gradable if r["_embedding_pure"] and not r["_special_case"]]
    e_strict, e_macro = strict_macro_accuracy(embed_pure_rows)
    e_conf = confusion(embed_pure_rows)
    e_prf = prf(*e_conf)

    special_case_rows = [r for r in gradable if r["_special_case"]]
    s_strict, s_macro = strict_macro_accuracy(special_case_rows)
    s_conf = confusion(special_case_rows)
    s_prf = prf(*s_conf)

    grading = {
        "flags": data["flags"],
        "topic_id": data["topic_id"],
        "total_cases": len(all_results),
        "ambiguous_excluded": len(ambiguous),
        "errors": len(errors),
        "gradable": len(gradable),
        "overall": {
            "strict_accuracy": overall_strict,
            "macro_accuracy": overall_macro,
            **overall_prf,
        },
        "per_category": cat_stats,
        "per_stage": stage_stats,
        "per_gate": gate_stats,
        "embedding_pure_subset": {"n": len(embed_pure_rows), "strict_accuracy": e_strict, "macro_accuracy": e_macro, **e_prf, "ids": [r["id"] for r in embed_pure_rows]},
        "special_case_subset": {"n": len(special_case_rows), "strict_accuracy": s_strict, "macro_accuracy": s_macro, **s_prf, "ids": [r["id"] for r in special_case_rows]},
        "ambiguous_ids": [r["id"] for r in ambiguous],
        "error_ids": [r["id"] for r in errors],
        "rows": gradable,
    }

    os.makedirs(os.path.dirname(grading_out), exist_ok=True)
    with open(grading_out, "w", encoding="utf-8") as f:
        json.dump(grading, f, indent=2, default=str)

    print(f"Gradable cases: {len(gradable)} (excluded {len(ambiguous)} AMBIGUOUS, {len(errors)} ERROR)")
    print(f"Overall strict accuracy: {overall_strict:.1%}")
    print(f"Overall macro accuracy:  {overall_macro:.1%}")
    print(f"Overall confusion (pos=FILTER): TP={overall_conf[0]} FP={overall_conf[1]} FN={overall_conf[2]} TN={overall_conf[3]}")
    print(f"Overall precision={overall_prf['precision']:.3f} recall={overall_prf['recall']:.3f} f1={overall_prf['f1']:.3f}")
    print()
    print("Per category:")
    for cat, s in cat_stats.items():
        print(f"  {cat:32s} n={s['n']:3d} strict={s['strict_accuracy']:.0%} macro={s['macro_accuracy']:.0%} P={s['precision']:.2f} R={s['recall']:.2f} F1={s['f1']:.2f}  failures={s['failures']}")
    print()
    print("Per stage:")
    for name, s in stage_stats.items():
        print(f"  {name:12s} n={s['n']:3d} strict={s['strict_accuracy']:.0%} macro={s['macro_accuracy']:.0%} P={s['precision']:.2f} R={s['recall']:.2f}")
    print()
    print("Per gate (standing breakdown — every fast-path mechanism, individually):")
    for gate, s in gate_stats.items():
        print(f"  {gate:36s} n={s['n']:3d} strict={s['strict_accuracy']:.0%} macro={s['macro_accuracy']:.0%} P={s['precision']:.2f} R={s['recall']:.2f}  failures={s['failures']}")
    print()
    print(f"Embedding-pure subset: n={len(embed_pure_rows)} strict={e_strict:.0%} macro={e_macro:.0%} P={e_prf['precision']:.2f} R={e_prf['recall']:.2f}")
    print(f"Special-case subset:   n={len(special_case_rows)} strict={s_strict:.0%} macro={s_macro:.0%} P={s_prf['precision']:.2f} R={s_prf['recall']:.2f}")
    print()
    print(f"Graded: {results_path}")
    print(f"Wrote grading to {grading_out}")


if __name__ == "__main__":
    main()
