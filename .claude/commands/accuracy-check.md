---
description: Check TrueBrief accuracy — run the Gemini-vs-TrueBrief whole-brief benchmark and/or the per-stage pytest map, then report a scorecard with regressions. Use after any pipeline/prompt/threshold change.
argument-hint: [stage name | topic | "all"] — e.g. "arbiter", "Iran War ceasefire deal", or "all"
---

Dispatch the **accuracy-evaluator** subagent, which uses the `accuracy-eval` skill (the stage→test map, judge axes, and regression rules).

**Target:** $ARGUMENTS  (a pipeline stage like `arbiter`/`salience`/`briefer`; a news topic; or `all`/empty)

Instructions for the evaluator:
1. If a **stage** is named → run that stage's pytest row from the accuracy-eval map **plus** the golden tests (`tests/test_golden_iran_war.py`). Always include golden.
2. If a **topic** is named (or `all`/empty) → run `python scripts/quality_benchmark.py "<topic>"` (live pipeline vs Gemini Search grounding + LLM judge) and the golden tests.
3. **Detect regressions** — compare the new per-axis scores against the most recent dated report in `docs/benchmarks/` for that topic, and any previously-green golden test that now fails.

Report in the accuracy-evaluator format: VERDICT (improved/regressed/neutral), per-stage PASS/FAIL, whole-brief per-axis (ours vs reference) + TOTAL, REGRESSIONS, top gaps in ours, false positives, and the single most fixable thing. If a check can't run (missing Gemini key / quota / no DB), say so — never invent a score.
