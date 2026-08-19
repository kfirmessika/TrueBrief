# Stage 1 Validation Experiments — Arbiter Integrity Fix Plan

**Date:** 2026-08-13/16
**Plan:** `watt-integrity-read-the-raport-resilient-blossom.md`, Stage 1 (cheap validation
experiments, before writing any Stage 2 cascade code)
**Scope:** Read-only. No writes to `known_facts`. `VectorStore.add_fact()` never called.
No production source file (`arbiter.py`, `contradiction.py`, `temporal.py`, `prompts.py`)
was modified — all experiments ran against the live code unmodified, with one exception
(Experiment 3's second pass patches `ARBITER_SYSTEM` **in the Python process's memory
only**, restored before the process exits; the file on disk is untouched).

Source data: `docs/benchmarks/_data/2026-08-13_arbiter-redteam-results.json` (131-case
red-team run), `scripts/_integrity_redteam_cases.py` (`CASES`), and live `known_facts`
rows on `topic_id = dd67825c-552d-4606-bfdd-9bc538783fba` ("iran war").

Scripts written for these experiments live in the session scratchpad, not the repo
(read-only analysis tooling, not shipped code): `exp2_digit_runs.py`,
`exp4_ic3_grey_zone.py`, `exp3_judge_only.py`, `exp3b_judge_with_rule.py`. Their raw
output is saved under `docs/benchmarks/_data/2026-08-13_stage1_exp*.json` for anyone who
wants to re-derive these numbers.

---

## Experiment 2 — Digit-run guard: does a spelled-out number create a false match?

**Hypothesis under test:** the proposed guard (compare `_digit_runs()` — `re.findall(r"\d+", text)`
— on both texts, treat equal digit-runs as evidence of a real match) silently fails when a
number is spelled out ("sixty" vs "59"), because the regex can't see it at all.

**Method:** identified all 67 cases where IC1 tally-collapse, raw-cosine auto-merge, or
same-day near-identical fired (22 + 33 + 12). Fetched each case's real matched fact from
`known_facts` (34 distinct `matched_alpha_id`s; 27 resolved — the other 7 all belong to
C12 intra-batch cases, whose "match" is another in-memory Alpha from the same batch, never
written to the DB, so a miss there is expected, not a data-loss finding). Ran the exact
`_digit_runs()` regex from `arbiter.py:60-62` on both the case's own `alpha_text` and the
matched fact's real `alpha_text`.

**Results:**
- 67 relevant cases analyzed.
- **16/67 (23.9%)** have `digit_runs_equal == True` while a spelled-out number
  ("eight", "five", "twelve"...) appears in one or both texts — the exact blind-spot risk
  the plan asked about.
- Of those 16, 13 already show `expected_decision != actual_decision` in the live audit
  (though not all 13 fail *because of* this specific blind spot — some fail for unrelated
  reasons, e.g. IC1 absorbing a real value change into UPDATE regardless of digits).

**Concrete examples:**
1. **C4-02** (`TALLY_UPDATE`) — case: *"The United States has halted **five** vessels
   since reinstating its blockade on July 14, 2026."* vs. the real stored fact: *"The
   United States has halted **three** vessels since reinstating its blockade on July 14,
   2026."* `_digit_runs()` on both texts returns `['14', '2026']` — identical — because
   the only digits present are from the date; the actual changed quantity (three→five) is
   spelled out and invisible to the regex. This is exactly the failure mode the experiment
   was built to catch: a naive "digits match → treat as duplicate" guard would see a
   vacuous match here and miss a real numeric change. (Today's system gets this case right
   via IC1's entity-overlap tally match, not digit comparison — but a Stage 2 guard that
   *adds* digit-equality as a signal for DUPLICATE-vs-UPDATE would need to account for
   this, not just bolt the regex on as-is.)
2. **C1-06 / C3-10** (`EXACT_DUPLICATE` / `PARAPHRASE_DATEDRIFT`) — *"The number of
   vessels transiting the Strait of Hormuz fell to **eight**."* — both `alpha_digits` and
   `matched_digits` are `[]` (empty lists, vacuously "equal"). Harmless here (it really is
   a duplicate), but shows the guard has **zero discriminating power** whenever a quantity
   is entirely spelled out on both sides — it can't tell "eight" from "eighty" if both were
   spelled that way.
3. **C1-08 / C3-06** — *"Strait of Hormuz shipping traffic hit its lowest point in a
   week"* vs. *"Shipping traffic in the Strait of Hormuz reached a one-week low"* — no
   digits in either text at all; same vacuous-match issue.

**Verdict: SUPPORTS the concern, with a scoped mitigation.** The blind spot is real and
measurable (24% of the guard's relevant cases), but it's a *silent no-op*, not a
false-positive generator — the guard just contributes no signal on spelled-out numbers,
it doesn't actively mislead. Stage 2 should not treat digit-run equality as sufficient
evidence of "no numeric change" by itself; either (a) normalize spelled-out numbers to
digits before comparing (a small `word2num` pass would cover the ~10 common cases seen
here — "eight", "twelve", "five", "three", "dozen"...), or (b) treat an empty
`_digit_runs()` result on either side as "inconclusive" and fall through to the Judge
rather than trusting the vacuous equality.

---

## Experiment 3 — Does the Judge LLM catch what IC4's keyword gate misses?

**Hypothesis under test:** "delete IC3, let the Judge see these cases" is enough on its
own to fix the `ANTONYM_GAP_CONTRADICTION` / `NUMERIC_CONTRADICTION_EVASION` categories,
because the Judge already reads full text and doesn't depend on a hardcoded antonym/metric
keyword list.

**Method:** the 20 case IDs (C7-01..10, C8-01..10). For each, fetched the real matched
fact from `known_facts`, built the exact `(alpha, adjusted_matches)` tuple
`Arbiter._prepare()` would produce (temporal + `V3_ENTITY_DEDUP` entity-overlap
adjustment), and called `JudgeLLM.call()` **directly**, bypassing IC1/IC3/IC4/raw-cosine/
same-day entirely. Real Gemini calls (LLMClient's built-in 60s per-call timeout applied;
primary key hit its quota partway through and the client's existing backup-key fallback
kicked in automatically — no manual intervention needed).

**Baseline result (current `ARBITER_SYSTEM`, unmodified): 0/20 (0%).** Every single case
was classified **UPDATE**, never NEW. Inspecting the `delta` field shows the LLM *does*
correctly read the contradiction semantically — e.g. for C7-04: *"Abbas Araghchi publicly
stated that Iran is vulnerable in its conflict with the United States and Israel,
**contradicting** his previous claim of invincibility."* It names the contradiction in
plain language, then still emits `UPDATE`. Root cause, found by reading the prompt: rule 1
of `ARBITER_SYSTEM` ("*A change in numbers... = UPDATE, never MERGE*") and the UPDATE
definition ("*new information that extends **or corrects** a known fact*") give the model
zero incentive to output NEW for a reversal — a polarity flip or conflicting number reads
exactly like a legitimate "correction" under the current rules. There is no third option
in the taxonomy for "this is a contradiction, not a correction."

**Second pass — same 20 cases, one explicit contradiction rule appended to
`ARBITER_SYSTEM` in memory only** (rule text distinguishes a same-time incompatible claim
from a self-identified correction; full text in `exp3b_judge_with_rule.py`):
**9/20 (45%)**. Breakdown: 7/10 correct on `ANTONYM_GAP_CONTRADICTION` (C7), only 3/10 on
`NUMERIC_CONTRADICTION_EVASION` (C8). The antonym cases responded well to the added rule;
the numeric ones mostly stayed UPDATE — plausibly because the added rule directly competes
with the existing, unconditional rule 1 ("a change in numbers = UPDATE"), and rule 1 sits
earlier in the prompt with its own worked examples reinforcing it.

**Verdict: FALSIFIES the simple "just delete IC3, trust the Judge" hypothesis** — 0/20
baseline is a clean, unambiguous failure, not a fast-path artifact; even given a fair,
fast-path-free look, the current Judge prompt has no path to output NEW for these cases.
**PARTIALLY SUPPORTS "add an explicit contradiction rule"** as the right shape of fix
(0%→45%), but 45% is below a usable bar, and the experiment localizes exactly why: rule 1
needs to be *amended*, not just supplemented, so it stops unconditionally rewarding
numeric reversals as legitimate updates. This confirms Stage 2's own plan text — "pending
Experiment 3's result, add one explicit contradiction rule to `ARBITER_SYSTEM`" — was the
right call, but the fix needs real prompt engineering (reconciling with rule 1), not a
one-paragraph bolt-on.

---

## Experiment 4 — Does deleting IC3 lose its 21 (measured: 15) correct cases?

**Hypothesis under test:** IC3's correct firings all land back in the grey zone
`[0.75, 0.97)` once its bypass is removed, so deleting IC3 outright costs nothing — the
standard Judge-LLM path picks them back up.

**Method:** all 32 cases where IC3 fired. Fetched each real matched fact's `event_date`
and `entities`. Recomputed `adjusted_similarity()` (temporal.py) and the
`V3_ENTITY_DEDUP` entity-overlap multiplier (`0.80 + 0.20 * entity_overlap`,
`arbiter.py:334-338`) from the real raw cosine score and real stored data — the exact
Step 3 formula, with IC3's Step 3b bypass simply not applied.

**Results:**
- 32 IC3-fired cases; 2 skipped (both C12 intra-batch cases — their "match" is an
  in-memory batch-pool alpha, not a DB row, same expected gap as Experiment 2).
- Of the 30 with real data: **30/30 (100%) land in `GREY_ZONE_MIN ≤ adjusted < AUTO_MERGE_THRESHOLD`
  (0.75–0.97)`. Zero fall to AUTO_NEW (<0.75). Zero fall to AUTO_MERGE (≥0.97).**
- Of those 30, **15 were IC3's correct firings** (`expected_decision == actual_decision`
  — the plan's own per-gate table cites "21," a rounder estimate from an earlier informal
  slice; this experiment's precise count on the same 131-case dataset is 15) and all 15
  land in the grey zone. The other 15 were IC3's *wrong* firings (all in C5/C7/C8 — exactly
  the categories Experiment 3 investigated) and land there too, meaning deleting IC3 stops
  forcing them into a wrong auto-DUPLICATE and instead gives the Judge a shot at them —
  though Experiment 3 shows the Judge's current prompt won't reliably take that shot yet.

**Examples:** C1-02 (raw=0.969, entity_overlap=1.00, final=0.969 → grey zone), C2-03
(raw=0.918 → 0.918, grey zone), C2-04 (raw=0.916 → 0.916, grey zone) — all well inside the
window with real production data, not synthetic.

**Verdict: SUPPORTS deleting IC3 outright.** No case is silently lost to AUTO_NEW, and
none slips past the Judge via AUTO_MERGE either — every single one of IC3's firings, right
or wrong, becomes a Judge-LLM case once the bypass is gone. Combined with Experiment 3,
though: deleting IC3 alone converts IC3's 15 wrong cases from "guaranteed wrong (auto-
DUPLICATE)" to "probably still wrong under today's prompt, potentially right under a fixed
one" — real progress, but Stage 2 shouldn't claim victory on IC3-adjacent categories until
the `ARBITER_SYSTEM` fix from Experiment 3 actually ships.

---

## Experiment 5 — Is `ENTITY_ALIAS_DUPLICATE`'s near-miss a normalization problem?

**Hypothesis under test:** the ~5 near-miss cases (adjusted score 0.687–0.744, just under
`GREY_ZONE_MIN = 0.75`) are cases where the entities genuinely refer to the same
thing but never overlap as literal strings (e.g. "Iran's Supreme Leader" vs "Khamenei").

**Method:** read-only inspection. Pulled the 5 cases (C6-03: 0.720, C6-04: 0.687, C6-05:
0.744, C6-06: 0.708, C6-10: 0.733) and fetched the real `entities` array from both the
case fixture and its matched `known_facts` row.

**Results — entity arrays, side by side:**

| Case | Case entities | Matched (real) entities | Literal overlap |
|---|---|---|---|
| C6-03 | `["Tehran", "U.S. government"]` | `["Iran", "Washington"]` | **0** |
| C6-04 | `["Iran's top diplomat", "Washington", "Tel Aviv"]` | `["Abbas Araghchi", "Iran", "United States", "Israel"]` | **0** |
| C6-05 | `["Iran's Supreme Leader", "IRGC"]` | `["Mojtaba Khamenei", "Ahmad Vahidi", "IRGC"]` | 1 ("IRGC") |
| C6-06 | `["Islamabad", "Iranian capital"]` | `["Mohsin Naqvi", "Pakistan", "Tehran", "Iran"]` | **0** |
| C6-10 | `["Iraq's PM", "CENTCOM"]` | `["Ali al-Zaidi", "Brad Cooper", "U.S. Central Command"]` | **0** |

4 of 5 have **zero** literal entity overlap despite being genuine paraphrase/alias
duplicates — role-for-name substitution ("Iraq's PM" / "Ali al-Zaidi"), abbreviation vs.
full name ("CENTCOM" / "U.S. Central Command"), and capital-city-as-country-alias
("Islamabad" / "Pakistan", "Iranian capital" / "Tehran"/"Iran") — exactly the pattern the
hypothesis named. One aside worth flagging separately, not part of this question: C6-05's
case text names "Ali Abdollahi" as the new appointee while its real DB match is about
"Ahmad Vahidi" — a different name — which may be a test-fixture mismatch rather than a
system flaw; noting it here for whoever picks up entity normalization next, not
diagnosing it further.

**Verdict: SUPPORTS the normalization hypothesis**, measured directly on live data. This
is not a threshold problem — nudging `GREY_ZONE_MIN` wouldn't fix 0.0 entity overlap. A
real fix needs entity canonicalization (alias/abbreviation/role resolution) before Jaccard
overlap is computed, not a threshold tweak. Given the clear zero-overlap pattern on 4/5
real cases, no exploratory LLM sanity-check call was needed to justify recommending this
direction to Stage 2.

---

## Test suite

`pytest tests/ -k "not test_end_to_end_pipeline"` (the excluded test is the known
pre-existing hang against the frozen V4 `PipelineRunner`, unrelated to this work):

```
337 passed, 1 deselected, 9 warnings in 91.46s
```

No source file was modified during these experiments (`arbiter.py`, `contradiction.py`,
`temporal.py`, `judge.py`, `prompts.py` all read-only). The 337/337 pass rate confirms the
baseline described in the plan is unchanged and nothing here introduced a regression.

---

## Summary for Stage 2

| Experiment | Verdict | Stage 2 implication |
|---|---|---|
| 2 — digit-run guard | Supports concern (24% blind-spot rate) | Pair the digit-run check with spelled-number normalization, or treat empty digit-runs as inconclusive rather than a match |
| 3 — Judge on antonym/numeric evasion | Falsifies "delete-and-trust"; partially supports "add a rule" (0%→45%) | `ARBITER_SYSTEM` needs a real rewrite of rule 1's numeric-change language, not just an appended contradiction rule |
| 4 — IC3 deletion safety | Supports deletion | IC3 can be deleted outright; 100% of its firings land safely in the grey zone, none lost to AUTO_NEW/AUTO_MERGE |
| 5 — entity-alias near-misses | Supports normalization hypothesis | Build entity canonicalization before touching `GREY_ZONE_MIN` |
