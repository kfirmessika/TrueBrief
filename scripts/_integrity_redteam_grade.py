#!/usr/bin/env python3
"""
scripts/_integrity_redteam_grade.py

Grading pass for the 2026-08-13 Arbiter red-team audit results
(docs/benchmarks/_data/2026-08-13_arbiter-redteam-results.json).

Read-only, no DB/LLM calls — pure Python over the already-collected JSON.
Computes strict + macro (PASS/FILTER) correctness, a confusion matrix on the
macro binary (positive class = FILTER), precision/recall/F1 overall, per
category, and per cascade stage (fast-path vs Judge LLM), plus an
embedding-only precision/recall subset (pure cosine-driven fast-path decisions,
no entity/contradiction/tally special-case).

Usage:
    python scripts/_integrity_redteam_grade.py
"""

from __future__ import annotations

import json
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_PATH = os.path.join(ROOT, "docs", "benchmarks", "_data", "2026-08-13_arbiter-redteam-results.json")
GRADING_OUT = os.path.join(ROOT, "docs", "benchmarks", "_data", "2026-08-13_arbiter-redteam-grading.json")

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
    data = json.load(open(RESULTS_PATH, encoding="utf-8"))
    all_results = data["results"]

    ambiguous = [r for r in all_results if r["expected_decision"] == "AMBIGUOUS"]
    errors = [r for r in all_results if r["actual_decision"] == "ERROR"]
    gradable = [r for r in all_results if r["expected_decision"] != "AMBIGUOUS"]

    for r in gradable:
        r["_stage"] = stage_of(r["reasoning"] or "")
        r["_embedding_pure"] = is_embedding_pure(r["reasoning"] or "")
        r["_special_case"] = is_special_case(r["reasoning"] or "")
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
        "embedding_pure_subset": {"n": len(embed_pure_rows), "strict_accuracy": e_strict, "macro_accuracy": e_macro, **e_prf, "ids": [r["id"] for r in embed_pure_rows]},
        "special_case_subset": {"n": len(special_case_rows), "strict_accuracy": s_strict, "macro_accuracy": s_macro, **s_prf, "ids": [r["id"] for r in special_case_rows]},
        "ambiguous_ids": [r["id"] for r in ambiguous],
        "error_ids": [r["id"] for r in errors],
        "rows": gradable,
    }

    os.makedirs(os.path.dirname(GRADING_OUT), exist_ok=True)
    with open(GRADING_OUT, "w", encoding="utf-8") as f:
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
    print(f"Embedding-pure subset: n={len(embed_pure_rows)} strict={e_strict:.0%} macro={e_macro:.0%} P={e_prf['precision']:.2f} R={e_prf['recall']:.2f}")
    print(f"Special-case subset:   n={len(special_case_rows)} strict={s_strict:.0%} macro={s_macro:.0%} P={s_prf['precision']:.2f} R={s_prf['recall']:.2f}")
    print()
    print(f"Wrote grading to {GRADING_OUT}")


if __name__ == "__main__":
    main()
