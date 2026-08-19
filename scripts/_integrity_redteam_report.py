#!/usr/bin/env python3
"""
scripts/_integrity_redteam_report.py

Deterministic report writer for an Arbiter red-team audit. Zero LLM calls, zero
DB calls — pure Python over the JSON that _integrity_redteam_grade.py already
computed. Reuses each case's pre-written `note` field (the attack rationale,
written once by hand when the case was designed) as the "why" explanation
instead of asking an LLM to re-derive it every run.

This is the missing third stage of the fully-automated loop:
    run.py (hits the real Arbiter + Gemini)  ->  grade.py (pure math)  ->  report.py (this file, pure formatting)
Chain them with _integrity_redteam_pipeline.py to go from "code changed" to
"finished .md report" in one command, with a human/AI only reading the last file.

Usage:
    python scripts/_integrity_redteam_report.py [path/to/grading.json] [path/to/report.md]
Defaults to the 2026-08-13 grading/report paths if no args given.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _integrity_redteam_cases import CASES  # noqa: E402

NOTES = {c["id"]: c["note"] for c in CASES}

DEFAULT_GRADING = os.path.join(ROOT, "docs", "benchmarks", "_data", "2026-08-13_arbiter-redteam-grading.json")
DEFAULT_REPORT = os.path.join(ROOT, "docs", "benchmarks", "2026-08-13_arbiter-redteam-audit-auto.md")


def pct(x: float) -> str:
    return f"{x:.1%}"


def trunc(s: str, n: int = 90) -> str:
    s = (s or "").replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def build_report(g: dict) -> str:
    lines = []
    a = lines.append

    a("# Arbiter/Judge Dedup Red-Team Audit — auto-generated report\n")
    a(
        "Generated deterministically by `scripts/_integrity_redteam_report.py` from "
        "`scripts/_integrity_redteam_grade.py`'s output. No LLM calls were used to write "
        "this file — every number below is computed math, and every failure explanation "
        "reuses the attack rationale written once into each test case's `note` field.\n"
    )
    a(f"- **Topic**: `{g['topic_id']}`")
    a(f"- **Total cases**: {g['total_cases']}  |  **Gradable**: {g['gradable']}  |  "
      f"**Ambiguous excluded**: {g['ambiguous_excluded']}  |  **Errors**: {g['errors']}\n")

    a("## Live flag states\n")
    a("| Flag | Value |")
    a("|---|---|")
    for k, v in g["flags"].items():
        a(f"| `{k}` | {v} |")
    a("")

    o = g["overall"]
    a("## Overall results\n")
    a("| Metric | Value |")
    a("|---|---|")
    a(f"| Strict accuracy | **{pct(o['strict_accuracy'])}** |")
    a(f"| Macro accuracy (PASS/FILTER bucket) | **{pct(o['macro_accuracy'])}** |")
    a(f"| Confusion (positive=FILTER) | TP={o['tp']} FP={o['fp']} FN={o['fn']} TN={o['tn']} |")
    a(f"| Precision | **{o['precision']:.3f}** |")
    a(f"| Recall | **{o['recall']:.3f}** |")
    a(f"| F1 | **{o['f1']:.3f}** |")
    a("")
    a(
        f"Of cases that should have been FILTERed ({o['tp']+o['fn']}), {o['tp']} were caught "
        f"and **{o['fn']} leaked through** (a real duplicate sneaked in). Of cases that should "
        f"have PASSed ({o['fp']+o['tn']}), {o['tn']} passed correctly and **{o['fp']} were "
        f"wrongly filtered** (a real fact incorrectly dropped).\n"
    )

    a("## Per-category stats\n")
    a("| Category | n | Strict | Macro | Precision | Recall | F1 | Failing case IDs |")
    a("|---|---:|---:|---:|---:|---:|---:|---|")
    for cat, s in g["per_category"].items():
        tp, fp, fn, tn = s["confusion"]
        p = f"{s['precision']:.2f}" if (tp + fp) else "n/a"
        r = f"{s['recall']:.2f}" if (tp + fn) else "n/a"
        f1 = f"{s['f1']:.2f}" if p != "n/a" and r != "n/a" else "n/a"
        fails = ", ".join(s["failures"]) if s["failures"] else "—"
        a(f"| {cat} | {s['n']} | {pct(s['strict_accuracy'])} | {pct(s['macro_accuracy'])} | {p} | {r} | {f1} | {fails} |")
    a("")

    a("## Per cascade-stage stats\n")
    a("| Stage | n | Strict | Macro | Precision | Recall |")
    a("|---|---:|---:|---:|---:|---:|")
    for name, s in g["per_stage"].items():
        a(f"| {name} | {s['n']} | {pct(s['strict_accuracy'])} | {pct(s['macro_accuracy'])} | {s['precision']:.2f} | {s['recall']:.2f} |")
    a("")

    a("## Per-gate stats (every fast-path mechanism individually)\n")
    a("| Gate | n | Strict | Macro | Precision | Recall | Failing case IDs |")
    a("|---|---:|---:|---:|---:|---:|---|")
    for gate, s in g["per_gate"].items():
        fails = ", ".join(s["failures"]) if s["failures"] else "—"
        a(f"| {gate} | {s['n']} | {pct(s['strict_accuracy'])} | {pct(s['macro_accuracy'])} | {s['precision']:.2f} | {s['recall']:.2f} | {fails} |")
    a("")

    ep, sc = g["embedding_pure_subset"], g["special_case_subset"]
    a("## Embedding-pure vs. special-case gates\n")
    a("| Subset | n | Strict | Macro | Precision | Recall |")
    a("|---|---:|---:|---:|---:|---:|")
    a(f"| Embedding-pure (no special gate fired) | {ep['n']} | {pct(ep['strict_accuracy'])} | {pct(ep['macro_accuracy'])} | {ep['precision']:.2f} | {ep['recall']:.2f} |")
    a(f"| Special-case gates (IC1/IC3/IC4/same-day) | {sc['n']} | {pct(sc['strict_accuracy'])} | {pct(sc['macro_accuracy'])} | {sc['precision']:.2f} | {sc['recall']:.2f} |")
    a("")

    a("---\n")
    a("## What specifically broke, grouped by mechanism\n")
    a(
        "Each failing case's rationale below is the attack design written when the case was "
        "built (`note` field in `_integrity_redteam_cases.py`), paired with the system's own "
        "stated reasoning for the wrong verdict. No new analysis was generated to produce this "
        "section.\n"
    )
    rows_by_id = {r["id"]: r for r in g["rows"]}
    by_gate_fail = defaultdict(list)
    for r in g["rows"]:
        if not r["_strict_correct"]:
            by_gate_fail[r["_gate"]].append(r)

    for gate, rows in sorted(by_gate_fail.items(), key=lambda kv: -len(kv[1])):
        a(f"### `{gate}` — {len(rows)} failing case(s)\n")
        for r in rows:
            note = NOTES.get(r["id"], "(no note on file)")
            a(f"- **{r['id']}** ({r['category']}) — expected `{r['expected_decision']}`, got `{r['actual_decision']}` "
              f"(sim={r['similarity_score']})")
            a(f"  - Attack rationale: {note}")
            a(f"  - System reasoning: {trunc(r['reasoning'], 160)}")
        a("")

    if not by_gate_fail:
        a("No failures — every gradable case matched its expected decision.\n")

    a("---\n")
    a("## Full per-test table (grouped by category)\n")
    by_cat = defaultdict(list)
    for r in g["rows"]:
        by_cat[r["category"]].append(r)
    for cat, rows in sorted(by_cat.items()):
        a(f"### {cat} (n={len(rows)})\n")
        a("| id | alpha_text | expected | actual | gate | sim | strict | macro |")
        a("|---|---|---|---|---|---:|---|---|")
        for r in sorted(rows, key=lambda x: x["id"]):
            sim = f"{r['similarity_score']:.3f}" if r["similarity_score"] is not None else "—"
            a(f"| {r['id']} | {trunc(r['alpha_text'], 70)} | {r['expected_decision']} | {r['actual_decision']} | "
              f"{r['_gate']} | {sim} | {'YES' if r['_strict_correct'] else 'no'} | {'YES' if r['_macro_correct'] else 'no'} |")
        a("")

    if g["ambiguous_ids"]:
        a(f"## Ambiguous cases (excluded from grading): {', '.join(g['ambiguous_ids'])}\n")
    if g["error_ids"]:
        a(f"## Error cases (excluded from grading): {', '.join(g['error_ids'])}\n")

    return "\n".join(lines)


def main():
    grading_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_GRADING
    report_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_REPORT

    g = json.load(open(grading_path, encoding="utf-8"))
    report = build_report(g)

    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Read grading:  {grading_path}")
    print(f"Wrote report:  {report_path}")
    print(f"Report length: {len(report):,} chars")


if __name__ == "__main__":
    main()
