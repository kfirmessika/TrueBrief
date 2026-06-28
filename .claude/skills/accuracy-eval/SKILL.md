---
name: accuracy-eval
description: Measure TrueBrief's output quality and per-stage accuracy. Use after any pipeline/prompt/threshold change, before shipping, or when asked to compare TrueBrief vs Gemini. Defines the Gemini-vs-TrueBrief signal benchmark (scripts/quality_benchmark.py), the per-stage pytest map, the judge axes, pass thresholds, and regression detection against docs/benchmarks/.
---

# Accuracy Evaluation — Gemini vs TrueBrief, per stage

TrueBrief's whole reason to exist is **signal over noise**. This skill is how we prove it didn't regress.
Two layers: (1) a **whole-brief judge benchmark** vs a Gemini Search reference, and (2) **per-stage pytest** checks.

## Layer 1 — Whole-brief signal benchmark
```bash
python scripts/quality_benchmark.py "Iran War ceasefire deal"   # one topic
python scripts/quality_benchmark.py "Trump" "Iran War"          # several
python scripts/quality_benchmark.py                             # preset DEFAULT_TOPICS
```
What it does (`scripts/quality_benchmark.py`): runs the **real `PipelineRunner`** on a throwaway topic row (cleaned up after) **and** Gemini 2.5 Flash-lite with Google Search grounding, in parallel, then an LLM judge scores both. Output: a console score table **and** `docs/benchmarks/YYYY-MM-DD_<slug>.md` with both briefs + sources.

**Judge axes (0–10 each, ours vs reference):**
| Axis | Question |
|---|---|
| `lede_quality` | does it surface the single most important CURRENT development first? |
| `completeness` | does it cover all key stories, or miss important ones? |
| `synthesis` | is there a "so what" / state-of-play summary? |
| `noise_level` | free of repetition, old news, low-priority items? (10 = clean) |
Plus `gaps_in_ours` (stories the reference had that we missed), `false_positives_in_ours` (items we included that it correctly excluded), and a one-line `verdict`.

**Reading the result:** TOTAL ours ≥ TOTAL reference = win. An axis flagged `⚠️`/`<<<` (ours < ref − 2) is the priority fix. The launch gate (roadmap §1) is **beat the reference on signal-vs-noise**. Treat a drop vs the previous dated report in `docs/benchmarks/` for the same topic as a **regression**.
Needs `GOOGLE_API_KEY`/`GEMINI_API_KEY` in `.env`. If quota is exhausted, fall back to Layer 2.

## Layer 2 — Per-stage pytest map
Run the check that matches the stage you changed:
| Pipeline stage | Command |
|---|---|
| Whole-brief signal | `python scripts/quality_benchmark.py "<topic>"` |
| Collector / dedup | `.venv/Scripts/python.exe -m pytest tests/test_neardup.py` |
| Harvester / extraction | `.venv/Scripts/python.exe -m pytest tests/test_extractor_fallback.py tests/test_v3_content_quality.py -k harvester` |
| Arbiter / judge | `.venv/Scripts/python.exe -m pytest tests/test_batch_judge.py tests/test_ic1_ic2.py` |
| Salience / ranking | `.venv/Scripts/python.exe -m pytest tests/test_salience.py tests/test_golden_iran_war.py` |
| Contradiction / date guard | `.venv/Scripts/python.exe -m pytest tests/test_contradiction.py tests/test_date_guard_sentinel.py` |
| State of play / synthesis | `.venv/Scripts/python.exe -m pytest tests/test_state_of_play.py` |
| Briefer / formatting | `.venv/Scripts/python.exe -m pytest tests/test_briefer.py tests/test_v3_content_quality.py` |
| Golden regression (whole) | `.venv/Scripts/python.exe -m pytest tests/test_golden_iran_war.py` |

The **golden tests** (`tests/test_golden_iran_war.py`) encode hard-won rules: no buried lede, state-change outranks tally, same-event duplicate clears the IC3 gate, contradiction flagged, state-of-play present, a tally is not a contradiction. **These must stay green** — a failure is a real quality regression, not a flaky test.

There is also `tests/master_benchmark_v2.py` + `tests/benchmark_v2_results.json` (longer scenario benchmark) — consult the JSON for the last recorded baseline.

## Standard accuracy workflow
1. Identify which stage(s) the change touched (use [[truebrief-pipeline]]).
2. Run that stage's pytest row. Then run the golden tests (always).
3. If the change could affect the final brief, run Layer 1 for ≥1 topic and diff scores vs the latest `docs/benchmarks/` report for that topic.
4. Report: per-axis ours-vs-ref, PASS/FAIL per stage test, any new gaps/false-positives, and a verdict. Flag any axis that dropped.

The `accuracy-evaluator` subagent automates this; the `/accuracy-check` command is the entry point. Root-causing a failure → [[truebrief-pipeline]] known issues + the `pipeline-debugger` agent.
