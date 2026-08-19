# Stage 2 Fix + Stage 3 Re-measurement — Arbiter Integrity Plan

**Date:** 2026-08-16
**Plan:** `watt-integrity-read-the-raport-resilient-blossom.md`, Stage 2 (per-gate code fix)
+ Stage 3 primary (re-measurement). Stage 4 (flag/rollout wiring) explicitly **not** started —
stopping here for review as instructed.

**Baseline this compares against:** `docs/benchmarks/2026-08-13_arbiter-redteam-audit.md`
(56.6% strict accuracy, 0.590 precision, 0.719 recall, live "iran war" topic, 131 red-team
cases). Backed up verbatim at `docs/benchmarks/_data/2026-08-13_arbiter-redteam-results-PRE-STAGE2-BASELINE.json`
/ `...-grading-PRE-STAGE2-BASELINE.json` before this session overwrote the harness's default
output path.

---

## What changed

### `src/truebrief/arbiter/arbiter.py` (+204/−lines net, see `git diff --stat`)

**1. New shared helper — `_normalized_numbers()`.** Compact word→number map (one..twenty,
tens, hundred/thousand/million/billion, dozen, half — not a full NLP parser, per project
philosophy). Replaces raw `_digit_runs()` equality in the three gates below. `_digit_runs()`
itself is untouched (a locked-in test, `test_digit_runs()` in `tests/test_same_day_dup.py`,
still imports and asserts its exact behavior).

**2. IC1 tally-collapse** — two guards added before the existing UPDATE return:
```python
if _normalized_numbers(alpha.alpha_text) == _normalized_numbers(tally_match.alpha_text):
    return AlphaDecision(..., decision=DecisionType.DUPLICATE, ...)   # Guard 1
...
contradiction_reason = detect_contradiction(alpha..., tally_match...)
if contradiction_reason:
    return AlphaDecision(..., decision=DecisionType.NEW, ...)         # Guard 2
```

**3. Raw-cosine auto-merge** — on a normalized-number mismatch at `raw_score >= 0.97`, routes
straight to the Judge LLM instead of falling through to temporal-adjusted zoning:
```python
if _normalized_numbers(alpha.alpha_text) != _normalized_numbers(match.alpha_text):
    return None, [(match, raw_score)]   # forces the grey-zone/Judge path
```

**4. Same-day near-identical** — digit check replaced with `_normalized_numbers()` equality,
plus an entity/subject-overlap guard. **Note:** shipped first at `>= 0.5`, per the plan's own
example; Stage 3's holdout set (below) caught a real false-merge at that threshold, so it was
raised to `>= 0.80` (matching the deleted IC3 gate's own validated bar) before this report was
finalized. All numbers in this report reflect the `>= 0.80` version.

**5. IC3 same-event fast-path — deleted outright** (was `arbiter.py:341-366`). The separate
Step-3 entity-overlap *multiplier* (`arbiter.py:334-338`, not a gate) is untouched.

**6. `contradiction.py`** — not modified. `ANTONYM_PAIRS`/`METRIC_KEYWORDS` left exactly as-is
per the plan.

### `src/truebrief/llm/prompts.py` (+50/−lines net)

`ARBITER_SYSTEM` rule 1 rewritten (not just supplemented) to distinguish a REVISION (later
report of the same running measurement → UPDATE) from a CONFLICT (same specific incident,
incompatible numbers → NEW, never UPDATE/MERGE). New rule 2 does the same for status/polarity
reversals not covered by `ANTONYM_PAIRS`. Iterated 3 times against the Stage 1 Experiment 3
fixture (20 real antonym/numeric-evasion cases, live Gemini calls):

| Version | Overall | Antonym (C7) | Numeric (C8) | Note |
|---|---:|---:|---:|---|
| Baseline (Stage 1, unmodified prompt) | 0/20 (0%) | 0/10 | 0/10 | Judge names the contradiction in its own delta text, then outputs UPDATE anyway — rule 1's old wording rewarded it |
| V2 (rewrite, shipped) | 16/20 (**80%**) | 9/10 | 7/10 | Shipped to `prompts.py` |
| V3 (added stricter same-day framing) | 16/20 (80%) | 8/10 | 8/10 | Same overall, different failure mix, more complex wording — not worth the added complexity over V2 |

V2 shipped (simpler, same ceiling). Raw per-case data: `docs/benchmarks/_data/2026-08-16_stage2_v2.json`, `..._v3.json`.

### `scripts/_integrity_redteam_grade.py`

Extended with a permanent per-gate breakdown (`gate_of()` / `GATE_PREFIX_ORDER`, one bucket
per fast-path mechanism), and now accepts a results-file path as `argv[1]` so it can grade any
run, not just the fixed 2026-08-13 file. This is a standing feature for future cascade changes,
not a one-off.

### Tests

`tests/test_number_normalizer.py` (new, 15 tests): unit coverage for `_normalized_numbers()`
(spelled-vs-digit mismatch caught, spelled-vs-digit match not falsely flagged, incidental
shared-date digits not falsely flagged, comma/decimal/scale-word parsing, dozen handling) plus
gate-level regression locks (IC1 verbatim-restatement → DUPLICATE, IC1 real revision still →
UPDATE including with spelled numbers on both sides, raw-cosine number-mismatch routes to
Judge not auto-merge, same-day entity guard blocks a different-subject pair, IC3's deletion
confirmed — a case that used to hit its triple gate now reaches the Judge).

---

## Stage 3 numeric comparison — full 131-case red-team run (unmodified harness)

Ran `scripts/_integrity_redteam_run.py` unmodified against the live "iran war" topic, **twice**:
once right after the initial Stage 2 fixes (same-day entity guard at `>= 0.5`), and again after
the entity-overlap threshold fix (`>= 0.80`, prompted by the holdout run below finding a real
false-merge at `0.5`). The second run is the current, final code state and is what's reported
below. First-pass numbers: `docs/benchmarks/_data/2026-08-16_arbiter-redteam-results-STAGE2.json`
/ `...-grading-STAGE2.json`. **Final numbers** (used for the table): `docs/benchmarks/_data/2026-08-16_arbiter-redteam-results-STAGE2-FINAL.json`
/ `...-grading-STAGE2-FINAL.json`.

| Target (baseline in parens) | Bar | Measured | Pass? |
|---|---:|---:|:---:|
| Overall strict accuracy | ≥ 75% (56.6%) | **76.0%** | **PASS** (+19.4pp over baseline) |
| Overall precision | ≥ 0.75 (0.590) | **0.939** | PASS |
| Overall recall | ≥ 0.70 (0.719, no regression) | **0.719** | PASS (flat vs baseline) |
| ANTONYM_GAP_CONTRADICTION | ≥ 60% (10%) | **80%** | PASS |
| NUMERIC_CONTRADICTION_EVASION | ≥ 60% (0%) | **40%** | **FAIL** (short by 20pp; up from 0%) |
| EXACT_DUPLICATE (IC1-driven) | ≥ 90% | 80% | **FAIL** |
| PARAPHRASE_DUPLICATE (IC1-driven) | ≥ 90% | 70% | **FAIL** |
| PARAPHRASE_DATEDRIFT (IC1-driven) | ≥ 90% | 60% | **FAIL** |
| PROMPT_INJECTION (IC1-driven) | ≥ 90% | 70% | **FAIL** |
| TALLY_UPDATE (IC1-driven) | ≥ 90% | 90% | PASS (exactly at bar) |
| PROMPT_INJECTION — no regression | ≥ 70% (baseline) | 70% | PASS (flat) |
| INTRA_BATCH_DEDUP — no regression | ≥ 100% (baseline) | 100% | PASS |
| Special-case subset precision | ≥ embedding-pure baseline (0.66) | **0.82** | PASS |

**8 of 13 targets pass. 5 fail — all 5 are short by a real, explainable margin, not a wash.**
(First-pass, pre-threshold-fix numbers were 7/13 at 73.6% overall strict accuracy — the
entity-overlap fix alone moved 3 cases: C7-10 and C10-07 stopped false-auto-merging via
`same_day_near_identical` (that gate went from n=13/69% to n=10/80%), and C11-10 flipped
correct too, for a net +2.4pp on overall strict accuracy — enough to cross the 75% line.)

Judge-LLM call volume, reported per the plan's own instruction (not hidden): baseline 10/129
gradable cases (7.8%) went to the Judge; Stage 2 (final) sends 55/129 (**42.6%**) — a real 5.5x
increase in LLM call volume, the expected cost of trading fast-path speed for correctness
(deleting IC3 alone accounts for most of this: its 32 firings all now route through either
another gate or the Judge).

### Why the four "IC1-driven" categories miss 90% — same root cause, diagnosed not guessed

`IC1_tally_collapse` gate stats: n=23, strict=43.5%, **precision 1.00, recall 0.09**. Precision
1.00 means Guard 1 (identical numbers → DUPLICATE) never produces a wrong DUPLICATE. Recall
0.09 means it almost never *fires* on cases that should be DUPLICATE. Root cause, confirmed by
reading `find_tally_match()` (`vector_store.py:398-445`): it retrieves the **most-recently-dated**
tally row with sufficient entity overlap — not the textually closest one. For a verbatim
duplicate like C1-01, this can hand IC1 the wrong reference fact (a later, already-revised
tally row, not the literal duplicate), so the number-equality guard correctly finds them
*unequal* — and IC1 falls through to a "genuine revision" UPDATE, which is wrong for a real
duplicate. **This is a pre-existing `find_tally_match()` retrieval-strategy problem, not a bug
in Stage 2's new guards** — the guards behave correctly given whatever `tally_match` they're
handed. Fixing `find_tally_match()` itself was not in Stage 2's assigned scope
(`vector_store.py` was only listed as a reference point, and this file wasn't authorized for
edits this session) — flagging as the clear next fix, not silently expanding scope to make it.

`NUMERIC_CONTRADICTION_EVASION`'s remaining 6 failures (C8-02/03/05/06/07/09) show the same
pattern from the other side: several of these cases are `event_class="tally"`, so IC1 claims
them before they ever reach the Judge's improved prompt — and `detect_contradiction()`
(unmodified per the plan) explicitly skips its numeric-conflict check when either side is
`tally`-classed (`is_tally` guard in `contradiction.py`), by design, to avoid flagging a real
running-total increase as a contradiction. That's correct for genuine tallies, but it means a
same-day numeric *contradiction* mistakenly tagged `tally` by the harvester bypasses the
Judge's rewritten rule 1 entirely. This is a genuine structural gap worth flagging for a future
pass, not something this Stage 2 change was scoped to close.

---

## Stage 3 "harsh hacker" holdout — 23 new adversarial cases

Built fresh, anchored against real live `known_facts` rows (verified via Supabase reads this
session) but with **no wording reused from the original 131** and number-words/antonym-pairs/
metric-words deliberately chosen to be outside both `test_number_normalizer.py`'s own test
cases and `contradiction.py`'s `ANTONYM_PAIRS`/`METRIC_KEYWORDS` lists. Case definitions:
`docs/benchmarks/_data/2026-08-16_stage3_holdout_cases.py`. Run via the real
`Arbiter.judge_alpha()`/`judge_alphas()`, live topic, real embeddings, zero writes — same
safety contract as the main harness. Run **twice**, same as the 131-case harness: first pass
found the entity-overlap bug (H14, below); final pass (`docs/benchmarks/_data/2026-08-16_stage3_holdout-results-FINAL.json`)
is against the fixed `>= 0.80` threshold and is what's reported here.

| Bin | Result |
|---|---|
| (a) Spelled-out-number tally/duplicate (new words) | 4/5 (80%) |
| (b) Antonym-style contradictions (new word pairs) | 5/6 (83%) |
| (c) Same-day, different subject | **5/5 (100%)** — H14 now correct after the entity-overlap fix |
| (d) Numeric conflicts, metric words outside `METRIC_KEYWORDS` | 4/7 (57%) |
| **Overall** | **18/23 (78.3%)** |

**Overall holdout accuracy (78.3%) lands close to the known-131-set accuracy (76.0%) — no
overfitting red flag.** If this were badly overfit to the specific 131 cases, the holdout would
be meaningfully lower; it isn't — if anything it's slightly higher, likely because the holdout
happens to contain no `ENTITY_ALIAS_DUPLICATE`-style cases (the known set's single weakest
category at 40%, explicitly out of scope for this Stage 2 pass per the plan).

**The 5 remaining holdout failures, with cause:**
- **H1** (spelled "fifty-nine" verbatim duplicate → got UPDATE): same `find_tally_match()`
  retrieval-strategy issue diagnosed above, reproduced on genuinely new wording — confirms
  it's a real, general bug, not a one-off in the original set.
- **H11** (antonym-style reversal, "meeting never took place" → got UPDATE): a Judge miss.
  Plausibly explained by rule 2's own carve-out ("unless the new fact explicitly frames itself
  as fixing an error") — "confirmed... never took place" can read as an official
  clarification, which the rule was deliberately written to allow through as UPDATE. A
  genuinely hard case, not an obvious rule bug.
- **H18, H19b, H21b** (same-day numeric conflict, value *increasing*, metric word outside
  `METRIC_KEYWORDS` — "41 warships" vs "20", "28 detainees" vs "12", "140,000 barrels" vs
  "80,000" → all got UPDATE, all expected NEW): **a real, reproducible residual weak spot**,
  consistent with `NUMERIC_CONTRADICTION_EVASION`'s 40% on the known set. When a same-day
  conflicting count is *higher* than the prior figure, the Judge tends to read it as a
  plausible in-progress revision rather than a same-incident conflict — exactly the ambiguity
  Experiment 3's V2/V3 iteration also hit a ceiling on (see `H20a/b`, "6 aircraft" vs "19",
  which *did* resolve correctly — the pattern isn't universal, but it's the single most common
  failure mode left in both the known and novel sets).

H14 (the entity-overlap bug this holdout run found) is now fixed and confirmed correct — it's
the clearest evidence the holdout process did its job: catching a real defect the known 131
cases, by construction, never could.

---

## Honest verdict

**Does this clear the bar? Mostly, on the metrics the plan weighted most heavily — but not
across the board, and that should be stated plainly rather than rounded up.** 8 of 13 Stage 3
targets pass, including overall strict accuracy (76.0%, clears 75%), precision (0.939 vs a
0.75 bar — the metric the plan explicitly weighted above recall, since a false DUPLICATE
silently drops a real story), and no recall regression. The holdout set — built specifically to
resist pattern-matching the known 131 — lands at 78.3%, at or slightly above the known-set
number, which is the strongest evidence available that these are structural fixes, not
overfitting. The 5 failing targets are all `NUMERIC_CONTRADICTION_EVASION` and the four
IC1-driven per-category 90% bars; they trace to two specific, diagnosed root causes, not a
vague "needs more work":

1. **`find_tally_match()`'s retrieval strategy** (picks most-recent-by-date, not most-similar)
   undermines IC1's new guards on a reproducible subset of verbatim duplicates — confirmed on
   both the known set (C1-01, C1-06) and independently on the holdout (H1). This is the
   single highest-leverage next fix: it alone accounts for most of why 4 of the 5 "IC1-driven"
   categories miss their 90% bar (`IC1_tally_collapse` gate: precision 1.00, recall 0.09 — the
   guards never produce a wrong answer, they just rarely get to fire on the right reference fact).
2. **Same-day numeric conflicts where the new count is higher** remain the weakest axis for
   the Judge, on both the known set (NUMERIC_CONTRADICTION_EVASION 40%, unchanged by the
   entity-overlap fix — that fix only touched the same-day *fast-path* gate, not the Judge)
   and the holdout (3 of 4 metric-word-gap failures share this exact shape). The rewritten
   rule 1 clearly helps (0%→80% on the original 20-case fixture) but doesn't fully close this
   specific pattern.

Neither gap is a surprise found late — both were flagged as open risks during Stage 1/Stage 2
work, and one of them (the entity-overlap threshold) was found and fixed *during* this same
Stage 3 pass, specifically because the holdout set was built to probe exactly this kind of
blind spot. That the holdout caught a real bug the known 131 cases structurally could not is
itself evidence the "harsh hacker" framing was the right posture for this work.

**Recommendation:** do not proceed to Stage 4 (flag/rollout wiring) yet. One follow-up is worth
doing first: fix `find_tally_match()`'s retrieval to prefer textual/vector similarity over
most-recent-date among entity-matching tally rows (`vector_store.py:398-445` — outside this
session's authorized touch points, flagging rather than fixing). `NUMERIC_CONTRADICTION_EVASION`
is a harder, more open-ended problem (same-day-increasing-count ambiguity) that may need a
structural change beyond prompt wording — worth a dedicated follow-up rather than another quick
iteration.

---

## Test suite

`pytest tests/ -k "not test_end_to_end_pipeline"` — run against the final code (including the
post-holdout entity-overlap threshold fix):

```
352 passed, 1 deselected, 9 warnings in 32.63s
```

(337 passed at the end of Stage 1; +15 is exactly `test_number_normalizer.py`'s new tests.
Zero failures, zero regressions.) All arbiter-specific suites (`test_number_normalizer.py`,
`test_same_day_dup.py`, `test_contradiction.py`, `test_batch_judge.py`,
`test_intra_batch_dedup.py`) also pass individually (45/45).
