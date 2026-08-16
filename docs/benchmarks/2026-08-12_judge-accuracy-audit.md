## Run status / known limitations for this specific run

**⚠️ THIS IS A SMALL PARTIAL SAMPLE, NOT THE FULL INTENDED CORPUS.** By explicit founder
instruction (2026-08-13), this report is being finalized NOW on the data already
collected and fully graded/scored -- 1 topic (Trump), 14 pairs -- instead of continuing
to wait on a blocked corpus expansion. Treat every percentage below as a **directional
first read on n=14**, not a validated verdict. The full intended corpus (80-120 pairs
across 5-8 topics: Iran war, Israel, Trump, US stock market outlook, Ukraine war,
Federal Reserve interest rates) was NOT completed.

**Collection history:**
- **2026-08-12:** stopped after 1/6 topics on a hard error -- the then-configured
  `gemini_search` model (`gemini-2.5-flash-lite`) returned `404 NOT_FOUND` ("no longer
  available to new users") on the backup key, while the primary key had separately hit
  its literal daily cap (`limit: 20, GenerateRequestsPerDayPerProjectPerModel-FreeTier`).
- **2026-08-13:** `gemini_search` was switched to `gemini-3.5-flash-lite` (500/day limit)
  specifically to fix the above. A live sanity check confirmed the environment itself was
  healthy (real grounded call succeeds/fails on real API responses, no import/env
  issues), but the grounding-specific quota was found exhausted project-wide on BOTH
  `GOOGLE_API_KEY` and `GOOGLE_API_KEY_BACKUP` (generic `429 RESOURCE_EXHAUSTED` on the
  grounding call specifically) -- confirmed NOT a per-minute burst limit (persisted
  after an 80s wait, and again after a further ~55 minutes of scripted retries with
  exponential backoff). Non-grounded calls (grader, JudgeLLM/arbiter) were not
  re-exercised today beyond what's already in this report -- 2026-08-12's finding that
  those succeed independently of the grounding quota still stands.
- Given the outage didn't clear within a reasonable retry window and the founder wants
  real numbers now rather than continued waiting, all further collection attempts were
  stopped (all background retry/polling processes killed, no further API calls made)
  and this report was finalized on the existing 14-pair corpus instead.
- **To complete the full corpus later:** `python scripts/judge_accuracy_audit.py
  --load-corpus docs/benchmarks/_data/2026-08-12_judge-accuracy-corpus.json` once
  grounding quota is confirmed available again -- already-collected topics (Trump) are
  skipped automatically (resume), only the missing 5 topics trigger new `collect()`
  calls. The script now also supports `--max-wait-hours` / `--retry-initial-wait` /
  `--retry-max-wait` (added 2026-08-13) for in-script retry-with-backoff on quota-like
  errors, though note that a single long-lived process was empirically observed to be
  killed by the execution environment after roughly 50-60 minutes regardless of that
  budget -- for an outage longer than that, re-invoke the script (or the smaller
  collection-only driver at `scripts/_quota_retry_collect.py`) periodically instead of
  relying on one process to survive the whole wait.
- ACTION ITEM worth flagging to the founder separately: if production's primary key ever
  hits its own daily grounding cap mid-day, confirm `GOOGLE_API_KEY_BACKUP` is actually
  usable as a fallback for whatever model is live at the time -- on 2026-08-12 it was
  permanently 404'ing for the then-current model, and on 2026-08-13 it was exhausted at
  the same time as the primary (same shared project-level grounding quota), so there is
  currently no evidence the backup key provides real redundancy for this specific
  step.

# Judge/Dedup Accuracy Audit -- 2026-08-12

**Topics:** Iran war, Israel, Trump, US stock market outlook, Ukraine war, Federal Reserve interest rates
**Total pairs:** 14  |  same_day_rescan: 7  |  multi_day_proxy: 7  |  cross_topic: 0
**Grader-labeled pairs (non-cross-topic):** 14 (5 SAME_EVENT, 9 DIFFERENT_EVENT)

**Ground truth caveat (read before trusting these numbers):** cross-topic pairs are the ONLY pairs with CERTAIN ground truth (unrelated topics cannot be the same event, by construction). All same_day_rescan/multi_day_proxy labels come from a second LLM call (a distinct grader prompt/model, gemini-3.1-flash-lite) -- this is a second opinion, not ground truth. It can be wrong, especially on genuinely ambiguous MERGE-vs-UPDATE calls (see the caveat under §2). Treat the flagged list at the end of this report as the pairs worth a human eyeball before trusting the aggregate percentages.

**multi_day_proxy caveat:** built within a single script run by pairing a 7-day-window collect() call's older-dated facts against a same-day-window collect() call's facts on the same topic -- NOT two collect() calls literally days apart (GeminiSearchCollector.collect() has no way to fake 'today' for a past-dated run). This approximates the intended scenario but is weaker evidence than same_day_rescan, which uses two real, independently-timed collect() calls.

## 1. Cosine gate accuracy

Of 5 grader-labeled SAME_EVENT pairs (same_day_rescan + multi_day_proxy):
- **Silent leak (scored below GREY_ZONE_MIN=0.75, never reached the judge, auto-inserted as NEW):** 0/5 = **0.0%**
- Zone distribution over SAME_EVENT pairs: AUTO_MERGE=1 (20.0%), GREY_ZONE=4 (80.0%)

## 2. JudgeLLM accuracy (grey-zone pairs only)

Grey-zone pairs with both a grader label and a real JudgeLLM verdict: 6

**Confusion matrix (rows = JudgeLLM verdict, cols = grader label):**

| predicted \ grader | SAME_EVENT | DIFFERENT_EVENT |
|---|---|---|
| MERGE | 1 | 0 |
| UPDATE | 3 | 1 |
| NEW | 0 | 1 |

**Binary collapse (MERGE+UPDATE = 'flagged as duplicate-like' vs grader SAME_EVENT):** caveat above -- this treats UPDATE and MERGE as equally 'correct' against a SAME_EVENT label, since the grader doesn't distinguish MERGE-worthy from UPDATE-worthy pairs.
- Precision: 0.800  (of pairs flagged MERGE/UPDATE, 80.0% were really SAME_EVENT)
- Recall: 1.000  (of grader SAME_EVENT pairs, 100.0% were caught as MERGE/UPDATE)
- Overall accuracy: 0.833 (5/6)

## 3. False-positive rate (certain true-negative cross-topic pairs)

No cross-topic pairs were built (insufficient topic diversity in the corpus).

## 4. Auto-merge zone (cosine >= 0.97) sanity check

Pairs auto-merged without any LLM call: 1
- Of those with a ground-truth/grader label: 1; disagreed with auto-merge (grader/construction says DIFFERENT_EVENT): 0/1 = 0.0%

## 5. End-to-end pipeline accuracy (true duplicates: caught vs leaked)

Of 5 grader-labeled true duplicates (SAME_EVENT):
- **Caught by some stage** (auto-merge cosine gate OR JudgeLLM MERGE/UPDATE): 5/5 = **100.0%**
- **Leaked through as NEW** (auto-new cosine gate OR JudgeLLM NEW): 0/5 = **0.0%**
- Breakdown of catches: AUTO_MERGE=1, MERGE=1, UPDATE=3

## Please eyeball these (most important/ambiguous pairs)

Selected by proximity to a decision boundary (cosine near 0.75/0.97) or predicted/grader disagreement -- the cases where a wrong ground-truth label or a wrong judge call would matter most.

1. [DISAGREEMENT] category=same_day_rescan cosine=0.777 zone=GREY_ZONE predicted=UPDATE grader=DIFFERENT_EVENT
   A (Trump): "U.S. District Court Judge Indira Talwani blocked the core components of President Trump's executive order on June 25."
   B (Trump): "A federal judge ruled against a Trump administration executive order intended to create a federal voter list and involve the U.S. Postal Service in election operations."
   grader reason: The facts describe two distinct judicial rulings occurring over a month apart concerning different aspects of executive orders.

2. [near boundary] category=same_day_rescan cosine=0.905 zone=GREY_ZONE predicted=UPDATE grader=SAME_EVENT
   A (Trump): "U.S. District Court Judge Indira Talwani issued a ruling against an executive order by President Donald Trump regarding federal voter lists and U.S. Postal Service operations."
   B (Trump): "A federal judge ruled against a Trump administration executive order intended to create a federal voter list and involve the U.S. Postal Service in election operations."
   grader reason: Both facts describe the exact same court ruling against the same Trump executive order issued on the same date.

3. [near boundary] category=multi_day_proxy cosine=0.693 zone=AUTO_NEW predicted=AUTO_NEW grader=DIFFERENT_EVENT
   A (Trump): "PolitiFact reported that President Donald Trump produced nearly 45,000 words regarding construction projects during the first seven months of 2026."
   B (Trump): "Donald Trump signed two executive orders aimed at protecting American citizenship and ending birth tourism."
   grader reason: Fact A discusses public statements regarding construction, while Fact B describes the signing of executive orders on birth tourism.

4. [near boundary] category=multi_day_proxy cosine=0.700 zone=AUTO_NEW predicted=AUTO_NEW grader=DIFFERENT_EVENT
   A (Trump): "President Donald Trump stated that his focus on construction projects is to keep the country beautiful and safe."
   B (Trump): "Donald Trump signed two executive orders aimed at protecting American citizenship and ending birth tourism."
   grader reason: The facts refer to unrelated activities: one concerns public infrastructure philosophy and the other involves specific executive orders regarding immigration policy.

5. [near boundary] category=same_day_rescan cosine=0.924 zone=GREY_ZONE predicted=UPDATE grader=SAME_EVENT
   A (Trump): "The Trump administration requested the Supreme Court to halt lower court decisions that blocked the executive order regarding voter lists and mail-in voting."
   B (Trump): "The Trump administration requested the Supreme Court to overturn lower court decisions that blocked changes to election operations."
   grader reason: Both facts refer to the same administrative appeal to the Supreme Court regarding legal blocks on election operation policies, occurring on consecutive days.

6. [near boundary] category=same_day_rescan cosine=0.789 zone=GREY_ZONE predicted=UPDATE grader=SAME_EVENT
   A (Trump): "The Department of Health and Human Services is involved in the implementation of the executive order regarding childhood vaccinations."
   B (Trump): "President Donald Trump signed an executive order to reduce the recommended childhood vaccination schedule in the United States to 11 immunizations."
   grader reason: Fact A discusses the implementation phase of the executive order that Fact B identifies as being signed by President Trump.

7. [near boundary] category=multi_day_proxy cosine=0.719 zone=AUTO_NEW predicted=AUTO_NEW grader=DIFFERENT_EVENT
   A (Trump): "A federal judge ruled against a Trump administration executive order intended to create a federal voter list and involve the U.S. Postal Service in election operations."
   B (Trump): "Donald Trump signed two executive orders aimed at protecting American citizenship and ending birth tourism."
   grader reason: The facts refer to distinct executive orders targeting different policy areas, specifically voter list creation versus birth tourism and citizenship.

8. [near boundary] category=multi_day_proxy cosine=0.722 zone=AUTO_NEW predicted=AUTO_NEW grader=DIFFERENT_EVENT
   A (Trump): "The Trump administration requested the Supreme Court to overturn lower court decisions that blocked changes to election operations."
   B (Trump): "The Trump administration threatened to cut Head Start program rules."
   grader reason: The facts describe two unrelated policy actions: one concerning election operations and the other concerning Head Start program rules.

9. [near boundary] category=multi_day_proxy cosine=0.775 zone=GREY_ZONE predicted=NEW grader=DIFFERENT_EVENT
   A (Trump): "President Donald Trump signed an executive order to reduce the recommended childhood vaccination schedule in the United States to 11 immunizations."
   B (Trump): "Donald Trump signed two executive orders aimed at protecting American citizenship and ending birth tourism."
   grader reason: The facts describe two distinct executive actions: one concerning childhood vaccination schedules and the other regarding birth tourism and citizenship.

10. [near boundary] category=same_day_rescan cosine=0.733 zone=AUTO_NEW predicted=AUTO_NEW grader=DIFFERENT_EVENT
   A (Trump): "President Donald Trump stated that a proposed White House ballroom expansion would cost $400 million and be funded by himself and donors."
   B (Trump): "President Donald Trump stated that his focus on construction projects is to keep the country beautiful and safe."
   grader reason: Fact A reports a specific infrastructure project and budget, while Fact B reports a general policy philosophy or sentiment.

11. [near boundary] category=same_day_rescan cosine=0.956 zone=GREY_ZONE predicted=MERGE grader=SAME_EVENT
   A (Trump): "PolitiFact documented approximately 45,000 words spoken by President Donald Trump regarding construction projects since January 2026."
   B (Trump): "PolitiFact reported that President Donald Trump produced nearly 45,000 words regarding construction projects during the first seven months of 2026."
   grader reason: Both facts describe the same PolitiFact analysis regarding the volume of Trump's words on construction projects throughout early 2026.

12. [near boundary] category=multi_day_proxy cosine=0.744 zone=AUTO_NEW predicted=AUTO_NEW grader=DIFFERENT_EVENT
   A (Trump): "President Donald Trump's executive order suggests separating the measles, mumps, and rubella (MMR) vaccine into three individual injections."
   B (Trump): "Donald Trump signed two executive orders aimed at protecting American citizenship and ending birth tourism."
   grader reason: The facts describe two distinct executive orders addressing completely different policy areas: vaccine administration and birth tourism/citizenship.

13. [near boundary] category=same_day_rescan cosine=0.972 zone=AUTO_MERGE predicted=AUTO_MERGE grader=SAME_EVENT
   A (Trump): "President Donald Trump signed an executive order seeking to reduce the number of recommended childhood vaccinations in the United States."
   B (Trump): "President Donald Trump signed an executive order to reduce the recommended childhood vaccination schedule in the United States to 11 immunizations."
   grader reason: Both statements describe the same executive order concerning the reduction of childhood vaccinations, with the second fact providing additional numerical detail.

14. [near boundary] category=multi_day_proxy cosine=0.748 zone=AUTO_NEW predicted=AUTO_NEW grader=DIFFERENT_EVENT
   A (Trump): "President Donald Trump's executive order suggests limiting vaccine recommendations for hepatitis A, hepatitis B, and meningococcal disease to high-risk populations."
   B (Trump): "The Trump administration threatened to cut Head Start program rules."
   grader reason: Fact A discusses vaccine recommendations, while Fact B concerns Head Start program regulations; these are distinct policy developments.
