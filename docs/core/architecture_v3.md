# TrueBrief — Architecture v3 (Consolidated Definitive Plan)

> **What this is.** The single consolidated design, pulling together everything settled across the redesign sessions.
> [architecture.md](architecture.md) (v1, original) and [architecture_v2.md](architecture_v2.md) (first redesign) are left **intact as history** — read them for rationale; read *this* for the current plan.
> **Verified against the live Supabase DB on 2026-06-10** — findings in §2 are evidence, not theory.
> **Cost model is presented as three options (§11)** — not yet locked; the rest of the document is settled.

---

## 0. Reading guide

| If you want… | Go to |
|---|---|
| Why the product exists / the one rule | §1 |
| What the live data actually showed | §2 |
| The core object model (threads, deltas) | §3 |
| Tables & fields | §4 |
| The pipeline, stage by stage | §5 |
| Search routing, scan timing, article selection | §6 |
| Context, history, the spliced timeline | §7 |
| Per-user "what's new" engine | §8 |
| **Two-clock model: new-to-us vs new-to-world** | §8B |
| Rate + depth as two axes, shared-scan schedule | §9 |
| Cost monitoring + the budget controller | §10 |
| **Scoring, eval, feedback & LLM-cost techniques** | §10B |
| **Cost & sharing — 3 options** | §11 |
| Shared memory + B2B/API | §12 |
| UI | §13 |
| Business / pricing / positioning | §14 |
| Build sequence | §15 |
| Decisions, red lights, open questions | §16 |
| Source layers & plugin architecture | §17 |
| Tech stack & "what NOT to use" | §18 |
| Monetization detail (conversion levers, B2B, projections) | §19 |
| Key risks & mitigations | §20 |
| Long-term moat & domain pipelines | §21 |
| Legal & copyright posture | §22 |

---

## 1. First principles

**The goal.** Keep a person current on what they care about, delivering **maximum new signal with minimum noise, in the least time.** News is the first domain; the product is *attention efficiency*.

**The inversion that drives everything.** Every news product optimizes time-on-app. TrueBrief optimizes the opposite — *less* time. A great session is short: open, see what changed, feel caught up, leave.

| Normal news product | TrueBrief |
|---|---|
| Rewards scrolling | Rewards **closure** |
| Empty state = failure | Empty state = **the product working** |
| Infinite bottom | **Finite bottom** |
| Shows everything happening | Shows only what **changed for you** |

**One sentence:** *Stop reading the news. Read a memo about it — one that remembers what it already told you.*

**Jobs to be done:**
- **J1** "What changed since I last looked?" — the delta (primary)
- **J2** "Do I have enough context to understand it?" — story-so-far on demand (primary)
- **J3** "Show me the full history" — the timeline (secondary)
- **J4** "Am I caught up / is it watching?" — closure + all-quiet (primary)
- **J5** "Watch this for me" — topic creation (entry)
- **J6** "Tune the signal" — rate, depth, mute (support)
- **J7** "Is it true / where's it from?" — provenance, always-on subtle

The design rule that falls out: **the default surface shows only deltas; context is one tap away; stable knowledge is collapsed to near-nothing.** Signal is created by *suppressing noise*, not amplifying signal.

---

## 2. Verified state of the system (live DB, 2026-06-10)

Inspected `iran war` (60 facts / 7 stories / 10 briefs) and `trump` (21 facts / 5 stories).

**✅ Working:**
- **`event_date` now 100% populated** (was 13%). The core dedup functions; the old "8–15× duplicate fact" problem is **gone**.
- **The recurrence case works** — semantically similar facts with different dates kept separate (Tyre strike Jun 8 vs Jun 9; Hezbollah Jun 8 vs Jun 9). *This is temporal+semantic dedup at the fact level — not the story graph.*

**🔴 Broken / to fix:**
1. **Date *year* hallucination.** The harvester guesses the wrong year on relative dates ("June 7" → 2024 instead of 2026). 8/60 iran facts dated before 2026; oldest 2020; two `2025-01-01` defaults. **It reaches delivered briefs** — the Jun-10 brief shows "June 7, 2024" for 2026 events from a June-2026 article. The 365-day sanity rule is not effectively applied.
2. **Story-clustering magnet node.** One `story_node` holds **27/60 facts (45%)** spanning **2024→2026** under an arbitrary title. Generic summary embedding → everything matches ≥0.70 → runaway pile-up. Plus singleton fragmentation. This is the "messy / confusing" feeling — and `story_summarizer` burns LLM generating these junk-drawer summaries. **Spaghettification confirmed at only 60 facts.**
3. **Relevance leaks.** Off-topic facts captured (Myanmar landmines, FIFA World Cup, Knicks tickets in the wrong topics).

**The conclusion that shapes v3:** dedup works *without* the story graph; the story graph is the worst-performing, most expensive component. So **dedup is load-bearing; the story graph is paused.**

---

## 3. The core model

### Thread, not brief, is the durable object
A "brief" is **not** a stored document — it is a **computed diff**. The durable object is the **story thread**: a topic is a handful of living threads, each one an evolving record (a set of facts + a context summary). The home screen is *assembled* from already-clean stored text → **$0 LLM to render the most-used screen.**

Why not the alternatives: a *brief* fragments one story across many documents; a *topic-blob* ("one giant story per topic") blurs distinct events. The *thread* is the only unit that matches how stories evolve. (See v2 §3.)

### Correctness vs. context — the load-bearing split
- **Correctness (is this new?) = fact-level dedup: semantic + temporal + entity/place.** Reliable. **This carries the product.**
- **Context (what's the story?) = a derived layer** (history doc / paused story graph). Allowed to be imperfect; **must never be load-bearing for correctness.**

This split is *why* we can pause the fragile clustering without breaking anything the user sees.

---

## 4. Data model

```
topics                         shared; one row per unique normalized query
├── id, raw_query (UNIQUE lowercased — auto-subscribe on dup, never scan the same thing twice)
├── scope/search_strategy (jsonb)        ← cached QueryBuilder output (built once, refreshed rarely)
├── last_run_at, next_run_at

facts                          (= known_facts; the load-bearing object)
├── id, topic_id
├── text                       clean standalone sentence
├── context                    ★ short "why it matters", emitted INLINE by harvester (no extra call)
├── embedding (vector)
├── entities (jsonb)           ★ USED in the dedup decision (not just stored)
├── location                   ★ place, part of the entity discriminator
├── event_date (date)          ★ MANDATORY; date of the DEVELOPMENT, not background subjects (§8B)
├── date_basis (enum)          ★ explicit | relative | inferred — trust level for event_date (§8B)
├── published_at (timestamptz) ★ when the ARTICLE was released — the SECOND clock, carried onto the fact (§8B)
├── importance (float 0–1)     ★ emitted free by harvester; drives ranking
├── confidence (float)
├── verified_count (int)       independent corroborating sources
├── source_url, source_domain
├── first_seen_at              when WE first stored it — "new to us", NOT "new to the world" (§8B)

story_threads                  ★ PAUSED (schema kept; assignment + summarizer OFF — see §5/§7)
├── id, topic_id, title, living_summary, summary_embedding, importance, momentum,
│   status, source_count, fact_count, first_seen_at, last_moved_at

history_docs                   ★ NEW; the context layer that replaces the paused graph (§7)
├── topic_id, doc (structured timeline, no-LLM-first), last_built_at

user_topic_state               ★ enables per-user deltas for free
├── user_id, topic_id, last_seen_at, muted_thread_ids (jsonb)

subscriptions                  per (user, topic) demand
├── user_id, topic_id, rate (fast|med|slow), depth (low|mid|max), tier

source_stats                   ★ per (topic × search_tool) AYR inputs (§6)
├── topic_id, tool, yield_ema, cost_ema, ayr, last_ready_at, scans, exploration_state

pipeline_runs                  ★ cost telemetry (§10)
├── id, topic_id, run_at, tool, articles_collected, articles_read, facts_extracted,
│   facts_passed, duplicates, llm_tokens_in, llm_tokens_out, llm_cost_usd, api_cost_usd

briefs                         OPTIONAL snapshot for email/history/sharing — NOT source of truth
```

### The delta query = the whole home screen (~1ms, $0 LLM)
```sql
SELECT f.*  -- or threads, when un-paused
FROM facts f
JOIN subscriptions s   ON s.topic_id = f.topic_id AND s.user_id = :me
JOIN user_topic_state u ON u.topic_id = f.topic_id AND u.user_id = :me
WHERE f.first_seen_at > u.last_seen_at
ORDER BY f.importance DESC, f.first_seen_at DESC;
```
"Quiet" = subscribed topics with nothing past `last_seen_at`. "All quiet" = zero rows. Personalization is automatic via each user's `last_seen_at`.

---

## 5. The pipeline

```
COLLECTOR → HARVESTER(+context+importance) → [dedup: semantic+temporal+ENTITY] → LEDGER → [history doc]
   reuse           reuse + 2 cheap fields              reuse + entity gate         reuse      no-LLM first
                                                                                              ↑
                                         story graph + briefer + verifier-stage = PAUSED/REMOVED
```

Stage by stage:

1. **Collector** — reuse. Add **URL-dedup** (skip already-processed `source_url`, last 14d) before selection. Search routing per §6.
2. **Harvester** — reuse, four prompt changes:
   - **`event_date` mandatory**, clamped to `[publish_date − 1y, today]`; "June 7"-type relative dates take the **publish year**. (Fixes the year-hallucination red light.)
   - **date the DEVELOPMENT, not the background.** "Trump moves *today* to reallocate the *2025* fund" → `event_date = today`; the 2025 fund goes in `context`. **Also emit `date_basis` (`explicit` | `relative` | `inferred`)** so the lag gate (§8B) can trust or distrust the date. (Dating the background subject instead of the action is the single biggest source of the "year-old fact shown as breaking" leak.)
   - **emit `importance` 0–1** per fact (free — the model is already reading the article).
   - **emit `context` inline** — `fact:` + `context:` in the same call. Grounded (written from the same article), a few extra output tokens, **no new LLM call.** This is what lets us **kill the separate briefer on the live path** (assemble, don't generate).
   - Keep **1 call per article** (attribution quality). Cut tokens by *article dedup*, not by batching extraction.
3. **Relevance gate** — drop off-topic facts (the Myanmar/World-Cup leak). Cheap check against topic scope/entities.
4. **Dedup (arbiter)** — reuse fast-path (auto-merge / auto-new) + grey-zone judge, **but the decision now uses `semantic similarity + temporal distance + entity/location overlap`.** Two facts are the *same event* only if all three agree. (The "two lions, two safaris, same day = different events" case.) **Batch the grey-zone judge** (self-contained tuples — safe to batch, unlike extraction).
5. **Ledger** — store fact with all fields; bump topic freshness.
6. **History doc** — rebuild the topic's timeline (no-LLM first, §7). **Story-graph assignment + `story_summarizer` are PAUSED** — keep the code, stop the spend, revisit post-launch.
7. **Briefer — REMOVED from the live path** (assembled from `fact`+`context`). Optional later, only for the polished email digest.

**Net cost effect:** quiet scans ≈ $0 generation; productive scans ≈ 1 (harvest, batched per article) + 0–1 (batched judge). ~90% fewer LLM calls than v1, *and* the date/relevance/entity fixes raise quality.

---

## 6. Search routing, scan timing, article selection

### Per-(topic × tool) AYR
Each topic runs a **multi-armed bandit over its search tools** (RSS / GoogleNews / Tavily / Brave / Exa). Each `(topic, tool)` has an **AYR = value ÷ cost**. High-AYR tools for that topic are called often; low-AYR rarely. The cost term auto-favors free tools (RSS) when they yield and makes paid tools earn their price — *per topic.*
- **Cold-start:** explore all tools for the first few runs, then exploit.
- **Exploration floor:** keep a small minimum call-rate per tool so a tool that goes quiet isn't abandoned forever (news shifts).

### Fast-adaptive AYR (spike-responsive) — build now
News is spiky (a quiet war explodes in one day). The current EMA (α=0.3) is too sluggish. Replace with a **responsive estimator**:
- **Adaptive gain** — trust new readings heavily when they're *surprising* (Kalman-style, high process noise); smooth when stable.
- **Surprise/derivative term** — a sudden jump in yield *immediately* accelerates scanning; don't wait for the average to drift.
- **Asymmetric** — snap *up* fast on a positive surprise, decay *down* gently (catches breaking news, resists thrashing).
- **Bounds** — tier min/max interval + the budget controller cap a spike from blowing cost.
> This same estimator predicts **cost** (for the limits in §11) — one estimator, two outputs (yield + cost).

### Coalescing window (between a topic's tools, not between topics)
Each tool has its own AYR-driven "ready" cadence. When the topic scans, **sweep up all tools past their ready point into one run.** (Timer-coalescing.) Cross-topic batching is *not* the goal — you can't merge two topics into one harvest call.

### Article selection (inside MMR, no hard rules)
1. **Domain-diversity penalty** — once an article from `bbc.com` is picked, further `bbc.com` candidates get a relevance discount (soft, not banned) so one outlet can't dominate.
2. **Syndication collapse** — near-identical text (>~0.95) across different URLs = the same article → keep one, bump a "seen in N outlets" counter.
3. **Never process the same article twice.**
4. **Threshold discipline:** very-high text similarity = syndication (collapse); moderate = *independent corroboration* → **keep** → feeds `verified_count`. (Don't kill the good duplicates.)

### Future (post-launch) — learn *when* to scan, not just how often
Learn the arrival-time distribution per `(topic × source × hour)` and schedule scans at the peaks — e.g., a creator posts at 4pm & 8pm, or a publisher has a daily cycle. Combine with depth-learning (how deep at which time). Needs months of arrival-time data → **defer.** It's a strong moat *specifically for the social/content-creator pivot* (predictable publish times). **1a (spike-adaptive) handles the unpredictable now; 1b (timing patterns) handles the predictable later.**

### Extraction efficiency — test before committing
Keep full-article→LLM as default (quality anchor). Safe token win first: **article-level dedup + near-dup skip.** Then **A/B two experiments** and decide on results: (a) paragraph **pre-filter** (send only relevant parts → cut tokens), (b) **highlight-hybrid** (send full text + "these lines look most relevant" → aim the model, same tokens). Don't commit blind.

---

## 7. Context & history

Three context mechanisms, cheapest first:

1. **Inline `context`** (from the harvester, §5) — every fact carries a one-line grounded "why it matters." Powers the tap-to-expand on the home screen with **zero extra calls.**
2. **History doc — no-LLM first.** Build the topic's "story so far" by **placing the (already-clean) fact-sentences in chronological order** with **zero LLM**. Evaluate how it reads. **Only if it's choppy**, add *one* "glue/summary" LLM pass. This replaces the paused story graph as the context layer and tests whether the LLM glue is even needed.
3. **Spliced timeline (B2B / power "full history")** — for the audit/analyst view: immutable fact anchors + LLM writes *only* the connective glue between adjacent facts (never mutates a fact); zero LLM at request; anchor-jump from a feed item into the timeline. Optimizes *micro-context* (what happened immediately before/after) — right for B2B, wrong for the B2C gist. (See v2 critique.)

> **Story graph (linked threads): paused now, deferred to B2B/future.** When revisited, it's a *loose linked graph queried only in local neighborhoods* — never a global "big tree" (collapses at scale), never load-bearing for dedup. Dormant threads never leave the index; a reignited story spawns a *linked successor*, not a reopened immortal node.

---

## 8. The per-user delta engine

Home = the delta query in §4. Properties:
- **$0 LLM** to render (pure Postgres).
- **Personalized for free** on shared topics via `last_seen_at`.
- **Scales in DB, not LLM** — 10,000 users on a shared topic = one pipeline run + 10,000 cheap indexed queries.
- On view, advance `last_seen_at`. "All quiet" = zero new since last look — a first-class hero state, not an error.
- **Gate the feed on development recency, not `first_seen_at` alone** — a fact first-seen today but *dated* a year ago is "new to us," not "new to the world." It belongs in history, not at the top of today. The mechanism is §8B.

**Delivery rhythm is a user preference, not a second system:** a *digest hour* (daily "your brief is ready") and a *breaking toggle* (push the moment something high-importance lands). Same engine, same screen, **two envelopes** (§13) — open once/day = digest feel; open often = real-time feel. The only variable is the `since` anchor: the live window uses each user's `last_seen_at`; the digest uses `last_digest_at` (two markers, one feed — they never contradict because the read always advances `last_seen_at`).

---

## 8B. The two-clock model — development-lag gating

Every fact carries **two timestamps that answer different questions**:
- **`published_at`** — when the article was released. Reliable (from the feed).
- **`event_date`** — when the development happened. LLM-extracted, less reliable.

**The bug this fixes (verified in a live brief).** The feed decided what to show by *"is this fact new to our ledger?"* — never by *"is the development recent in the world?"* A genuinely-2025 reference inside a June-2026 article passed the `[publish−1y]` clamp, became a NEW fact, and landed in "today" with no date and no context. **"New to us" ≠ "new to the world"** — one clock was doing two jobs. (Same bug survives the V1 briefer *and* the V3 delta query, which sorts by `first_seen_at`.)

**The lag classifier.** Per new fact, `lag = published_at − event_date`:
- **lag ≤ ~3 days** — fresh event → **feed** normally ("today / yesterday").
- **lag = days–weeks** — delayed report / follow-up → **feed, but framed** ("from last week") — never dressed as breaking.
- **lag ≥ months** — **red light** → route by the history test (never auto-show, never auto-drop).

**The history test — miss vs. noise (the load-bearing discriminator).** A large-lag fact gets asked: *does it connect to the topic's existing timeline?*
- **Connects** — shares entities / slots into a known thread / corroborated by another source → a **genuine backfill of a miss.** → write to **history/timeline silently**; surface in the feed only as *"filling a gap — Mar 2025,"* never as breaking. (Misses *will* happen — the first scan never catches everything — and history is exactly where they belong.)
- **Orphan** — no entity overlap, single source, low importance ("Trump 2025 allocation" in passing) → **noise or a bad date.** → suppress from the feed; log to the **muted-items audit (§10B.7)** so nothing is silently lost.

**`date_basis` — making `event_date` trustworthy enough to reason about the gap.** The harvester emits, per fact, *how it got the date*:
- `explicit` — article states an absolute date → trust even if old → **eligible for backfill.**
- `relative` — resolved from "yesterday / last week" against publish date → **clamp hard** to the publish window.
- `inferred` — weak guess → only allowed at small lag; **large-lag + inferred = drop.**

The filter falls out of the combination: *explicit old date that connects to history* = the miss you want to catch; *inferred old date that's an orphan* = exactly the junk that leaked.

**Root-cause prompt fix (the cheapest, highest-yield change).** Date the fact to the **action it reports, not the background subject it references.** Background references go in `context`, not `event_date` (§5).

**Where each fact lands:**
| lag | date_basis | history test | → destination |
|---|---|---|---|
| small | any | — | **feed** (normal) |
| medium | any | — | **feed** (framed "from last week") |
| large | explicit / relative | connects | **history** (+ optional "gap filled" feed note) |
| large | inferred | connects | history, low confidence |
| large | any | **orphan** | **suppress** → muted-items log |

Touches: the **harvester** (emit `date_basis`, date the development), the **ledger** (carry `published_at` onto the fact), the **delta engine** (gate on development recency, not `first_seen_at` alone). M1 task: 1a.1 + 1a.5.

---

## 9. Rate & depth as two axes; the shared-scan schedule

Two independent demand parameters per subscription:
- **Rate** — how often you're updated (fast/med/slow). **Differentiable in delivery** (a slow user genuinely receives fewer updates → no free-ride: request slow, get slow).
- **Depth** — how thoroughly each scan searches (articles read, confidence of completeness). **Not differentiable on a shared scan** (everyone on a given scan gets its full depth) → depth is governed by tier/demand, not a per-delivery slider.

**Shared-scan merge schedule.** A shared topic runs at the **max** rate/depth of its *due* subscribers; each scan serves every due user whose depth ≤ the scan's depth.

Example — subscribers {fast, low-depth}, {mid, max-depth}, {slow, mid-depth}, rate ratio 2:
```
scan 0: max-depth  → all update         (everyone due; take the max depth present)
scan 1: low-depth  → only fast update
scan 2: max-depth  → fast + mid update
scan 3: low-depth  → only fast update
scan 4: max-depth  → all update
...
(slow-mid-depth is never separately run — when slow is due it rides the max-depth scan)
```
This is the **minimal-work schedule**: each scan is exactly as deep as the deepest due user needs, and serves everyone due. The fastest user sets the rate; the deepest *due* user sets that scan's depth.

---

## 10. Cost monitoring & the budget controller

### Actual per-run cost tracking (founder-only, not user-facing)
Record per run in `pipeline_runs`: LLM tokens in/out × price, API calls × price (the **variable** cost). Amortize **fixed** costs (DB, deploy) as flat overhead — *don't* attribute CPU per-run (noise). This telemetry is the prerequisite for cost-aware AYR *and* the limits in §11 — **build it first.**

### The budget controller (graceful degradation — never hard-block)
Hard-blocking a *monitoring* product is suicide (you stop monitoring = it fails). Instead, a **feedback controller**:
- predict end-of-period spend (burn rate × time left),
- scale a **global rate-multiplier** on everyone's AYR to fit budget,
- with a **safety-margin asymptote** (set the effective cap below the true cap so the curve physically can't cross it).

Combined with **cost-aware AYR (value ÷ cost)**, it degrades the **least valuable** updates first. **Tier-aware:** throttle the free curated list first; protect paid SLAs longest (see §11/§12).

---

## 10B. Scoring, evaluation, feedback & LLM-cost techniques (restored from v1/v2 + 3 new)

> This section restores detail that exists in v1/v2 but was compressed out of the v3 draft. Tags: **[v1]** = in original architecture.md, **[v2]** = in architecture_v2, **[NEW]** = genuinely new (from the Squelch cross-check).

### 10B.1 The cheap gate before the expensive LLM (the cost spine)
Kill obvious cases for free *before* any LLM call. Layered, cheapest first:
1. **URL/exact dedup** — never process the same article twice (hash of canonical URL+title). **[v1: article cache]**
2. **Near-dup / syndication collapse** — `SimHash(64-bit), Hamming ≤ 3` **[NEW method]** *or* embedding cosine > 0.95; collapse to one, bump a "seen in N outlets" counter. Preserve *independent* corroboration (moderate similarity) → `verified_count`.
3. **MMR selection** (λ≈0.65) — pick the few best *diverse* articles from the pool before extraction. **[v1]**
4. **Candidate / relevance gate** — keep only items that clear `keyword match OR cosine(item, topic-centroid) > τ`. The topic centroid = mean(embed(seed texts from the compiled topic)). Recall-oriented (false positives are fine — the next stage kills them). **[v1: "Garbage Filter"]**
5. **Arbiter fast-path** — auto-DUPLICATE (>0.97) / auto-NEW (<0.75) skip the LLM entirely (~50% of judge calls); only the grey zone hits the LLM. **[v1: "Fast Path"]**

### 10B.2 Significance / importance scoring (the formula)
Per fact: `importance` 0–1 emitted free by the harvester; `verified_count` from corroboration. Aggregate:
```
score = w1·max(fact.importance)        // relevance/significance
      + w2·normalize(verified_count)   // corroboration  [v1: corroboration]
      + w3·momentum_decay(last_moved)  // is it moving now
      + w4·is_new_thread_bonus         // novelty
      + w5·source_authority
      + w6·recency_decay(~36h half-life)
      + personal_bias                  // ±, from feedback (10B.4)
```
Merges **[v2 §7]** importance + **[v1]** AYR weighting + the Squelch decomposition. Weights are config, re-fit against the golden set (10B.3) periodically. The Briefing sorts by this; the **noise-floor presets** (Thorough / Significant / Critical-only) are a *user threshold* on it — a visible instrument so a user who misses something blames the *setting* and adjusts, instead of churning. **[NEW framing]**

### 10B.3 AYR scoring (carried from v1, made cost-aware)
```
Density = (A+D)/T   ·   Freshness = A/(A+D)   ·   Utility = 0.4·Density + 0.6·Freshness
AYR_new = Utility·α + AYR_old·(1−α)         // EMA, α adaptive/spike-responsive (§6)
```
v3 change: AYR = **value ÷ cost**, tracked **per (topic × tool)**, with the spike-adaptive estimator (§6). **[v1 formula + v3 changes]**

### 10B.4 Feedback loop (Rocchio + few-shot, then a learned pre-filter)
- 👍/👎 stored as labeled examples. **Rocchio** centroid update: `centroid ← normalize(centroid + α·mean(pos) − β·mean(neg))`. **[NEW mechanism, v1 had the concept (Phase 5)]**
- Inject the few most recent/contrastive examples into the scoring rubric as few-shot lines.
- After ~200 labels, train a cheap **logistic-regression pre-filter** on embeddings → skip LLM scoring when `p < 0.15`. The long-term cost crusher + a small personalization moat. **[v1 Phase 6: fine-tuned classifier]**

### 10B.5 Evaluation & success metrics (build the harness *before* more app work)
- **North-star: `precision@5` ≥ 80%** — of the items delivered, how many the user judges worth their time. Below ~60% → churn is guaranteed regardless of UI. **[v1 metrics + Squelch framing]**
- **Golden set:** a few reference topics × hand-labeled items; a CI report on gate **recall**, scoring **precision/recall**, and digest **precision@5**; every beta 👎 becomes a labeled case. = roadmap **A.2 Accuracy Test Harness** — treat scoring quality as the product, the app as packaging.
- v1 targets to keep: **delta accuracy >90%**, **brief quality >80%**, **churn <5%**, **cost/brief <$0.02**.

### 10B.6 LLM cost techniques (the complete list)
| Technique | Saves | Source |
|---|---|---|
| Fast-path auto-merge/auto-new | ~50% of judge calls | [v1] |
| Score-only output at scoring; prose only for delivered winners | output tokens (the expensive ones) | A/B vs our inline-context |
| Within-run batching (judge, summary; N updates → 1) | call count | [v1]+[v2] |
| Article URL cache + SimHash near-dup before extraction | re-processing | [v1]+[NEW] |
| **Batch mode** (provider batch API) | ~−50% on non-real-time calls — **Gemini has Batch Mode** | **[NEW]** |
| **Context / prompt caching** of the fixed scorer/judge system prompt | discount on cached input — **Gemini has context caching** | **[NEW]** |
| Shared-topic execution (one run → all subscribers) | scales with topics not users | [v1] |
| Cache QueryBuilder per-topic; gate scans on new content | per-scan + quiet-scan cost | [v2] |
| Daily kill-switch token budget + per-stage cost logging | runaway protection | [v1 risk]→ budget controller (§10) |

> **Model-cost note (important):** we run on **Gemini Flash (cheap)**, *not* Claude — Claude is smart but far too expensive at per-scan volume. The good news: **both batch mode and context caching exist on Gemini**, so these cost wins apply to our cheap model. The −90% / −50% figures above are *Claude's*; **verify Gemini's current discounts** before relying on exact numbers. If a future cheap model lacks caching, only then compare *Claude-Haiku-with-caching* vs *cheap-model-without-caching* on total cost. Model choice always lives in `settings` / `LLMClient` — never hardcoded.

### 10B.7 Trust UX
- **Viewable muted-items log** — "212 items muted — view." Makes the filter *auditable*; directly fights false-negative anxiety ("did it miss something?"), the top churn driver. **[NEW, beyond our "we read N articles" line]**

---

## 11. Cost & sharing — THREE OPTIONS (not yet locked)

All three assume: **free users are a curated, founder-controlled list** (daily, shallow, bounded cost — a free user *cannot* overage because cost is per-topic, not per-user; if the free list's predicted total exceeds budget, slow it all equally — only the founder knows). The options differ in how **paid** cost is attributed and limited.

### Option A — Simple flat tiers (the simplest)
Flat price per tier; tier = a hard ceiling on (rate, depth, #topics). No per-user cost attribution beyond monitoring; price each tier above the cost of a *maxed-out* user; the budget controller handles aggregate spend.
- **Pros:** dead simple, predictable bills, no gaming possible (nothing metered to game), industry-standard.
- **Cons:** leaves money on the table (light user pays like a heavy user within a tier); coarse.
- **Free-rider:** impossible — there's no per-use bill to dodge.

### Option B — Flat tiers + incremental attribution + soft/hard limits + margin shield (RECOMMENDED)
Billing stays flat-tier. **Internally**, track two numbers per (user, topic):
- **True attributed cost** — *incremental/marginal* ("shared-taxi") split: the base level (cheapest subscriber's demand) splits across all subscribers; each increment of depth/rate is attributed only to the users who demanded ≥ that level. Every cost unit lands on a demander; total = full cost; the founder is always covered. (Used for *profitability monitoring*.)
- **Budget draw** — what counts against the user's tier cap, set **above** true marginal cost with margin baked in. The gap = profit + shock-absorber. More users on a shared topic → bigger margin (real cost ≈ 1/N, charge ≈ a modest flat rate) → popular shared topics fund spikes and the free tier.

**Two-tier limits (graceful):**
- **Soft limit** (≈ generous, e.g. 50% margin — *tune on real data*): **freeze growth** — can't create/join more topics without removing one, until the trajectory drops. **Existing topics keep full service** (no information delay). *User self-corrects.*
- **Hard limit** (≈ e.g. 80%): clear "you're over" message + **throttle the user's own private topics** enough to hold the line. **Shared topics untouched.** *System self-corrects.*

**Critical refinement — growth vs. spike.** The soft-freeze fixes *growth-driven* overage (user added topics). *Spike-driven* overage (a quiet topic explodes for a day) must be **absorbed by margin** — the soft→hard gap is the shock absorber — and you must **not throttle during a high-retention news event.** The predictor (§6) distinguishes "topic count growing" (throttle eligible) from "per-topic cost spiking" (absorb). Throttle only **sustained** elevation.

- **Pros:** per-user profitability visibility; founder always covered; *harmful* free-riding eliminated (you can't reliably get more than you cause; the residual windfall is zero-cost and is *correct* marginal accounting); graceful, never delays information.
- **Cons:** more machinery (predictor + two cost numbers + two limits); thresholds need real cost data to calibrate → it's "billing v2," built after launch.

### Option C — Original split / weights / fines model (documented, not recommended)
Each user weighted by `speed × depth`; the shared topic's cost is **split** among subscribers by weight; users over their predicted limit are **fined** (delayed delivery) and their unpaid share is **redistributed** to others; only if 100% are over does the topic slow.
- **Pros:** maximally "fair" per-use accounting in principle.
- **Cons (why not recommended):** (1) **invites free-riding** — splitting metered cost makes "set my depth low and ride the high-requester" the rational strategy; (2) **delay-as-fine destroys a news product** for the paying user you most want to keep; (3) **redistribution surprise-bills compliant users** for someone else's overage; (4) heavy machinery (per-user time counters, simulated scans, fine sizing). The delay options explored (actual delay / next-scan placement / simulated scan from old briefs) all deliver a *worse* feed to a paying customer.

### Recommendation
**Launch on Option A** (flat tiers + caps + budget controller — simple, ship-able, ungameable). **Grow into Option B** once cost telemetry exists, for per-user profitability + graceful limits + margin shield. **Keep Option C documented as the rejected baseline** (it's the source of the free-rider problem). For **B2B/API**, metered per-call is correct (private quotas, no shared good to free-ride).

---

## 12. Shared memory & B2B/API

**One fact ledger; every channel is an access layer on top.** A B2B customer tracking "Apple" *subscribes to the same topic* a B2C user does — one scan, one set of facts, served to the UI, email, push, **and** the API. Mechanism already exists: `topics.raw_query` UNIQUE/normalized → a duplicate auto-subscribes instead of creating a second topic. **Never scan the same thing twice** — this is both the cost-optimal move and the moat (one ever-deepening memory).

- **Private topics** (a proprietary B2B watchlist) don't pool — full cost to that customer, metered against their API plan.
- B2B subscribers slot into the **same incremental-attribution + merge-schedule** model — if a B2B customer wants Apple deep+fast, that increment is attributed to them; B2C riders benefit at zero marginal cost.
- API surface (future Phase 4): `GET /topics/{id}/delta?since=`, `GET /topics/{id}/timeline`, webhook delivery.

---

## 13. UI

**One surface, radical subtraction.** The home screen reads like a brief from a smart friend: a calm count, a few plain sentences, silence confirmed. *For every element: does removing it lose signal? If not, it's gone.* (The first v2 draft was busy because it surfaced proof-of-value = noise.)

```
TrueBrief                              all topics ▾   Jun 9
● 3 new today

OpenAI closed its funding round at $40B, valuing it at $300B
— the biggest private tech raise ever.
   openai · 2h
[tap → "story so far" (inline context) + sources, expand in place]

The FTC opened an antitrust probe into Microsoft's cloud deal with OpenAI.
   openai · 5h

──
Nothing else moved across your other 4 topics.
```
- **Topics are a filter, not a sidebar of dots.** Context expands **in place** (the inline `context`), not a separate fact-by-fact panel. The full timeline is a rare power/B2B view.
- **"All caught up."** is a hero state (what users see most days) — calm, no numbers, feels like a gift.
- **Killed:** chat-bubble brief feed, Stories tab, Insights tab, stat bars, verified-chips-everywhere, topic-dot sidebar.
- Reference mock: **`reports/v3-briefing.html`** (with the all-quiet toggle). v2-app/v2-new-topic kept only as "too busy" references.

### Two channels = one feed, two envelopes (NOT two screens)
The "daily summary" and the "live window when you open" are the **same delta feed** with a different `since` anchor (§8) and a different *header ceremony*. Pick the envelope by **how long since the user last looked** — don't build a second UI.

- **Live envelope** (gap < a few hours — the always-connected user): minimal header (`● 2 new since you looked`), no sectioning, instant. This is `v3-briefing.html`.
- **Digest envelope** (gap ≈ a day, **or** the scheduled digest hour — the once-a-day reader): dated header (`Your brief · Tue Jun 16`), optional grouping by topic, an explicit close (`That's everything`). Delivered to email/push **and** mirrored in-app as a dated card.

```
LIVE                                  DIGEST
● 2 new since you looked              Your brief · Tue Jun 16
                                      ● 6 across 5 topics since yesterday
FTC opened a probe into the
MSFT–OpenAI deal.  openai · 40m         OPENAI
                                        OpenAI closed its round at $40B.  9h
Fed minutes: two cuts likely.           FTC opened a probe into the deal. 5h
fed rates · 2h                          FED RATES
──                                      Fed held; signaled two cuts.      6h
Nothing else moved.                   ──
                                      That's everything. See you tomorrow.
```
The digest is the **re-engagement hook for people who don't stay connected**; the always-connected user lives in the live envelope and may never need it. The all-caught-up hero state serves both. (Mechanism: two markers `last_seen_at` / `last_digest_at`, one feed — §8.)

---

## 14. Business

**Positioning: the memo, not the feed.** Anti-positioning: no chat interface (GNOMI owns that frame; open-ended = noise), no article summaries (you extract facts), no engagement mechanics.

**Tiers (B2C):**
| Tier | Price | Who | Hook |
|---|---|---|---|
| Free | $0 | wedge | curated shared list, daily, web only |
| Pro | $9/mo | power readers | 15 topics, hourly, email+push, history |
| Researcher | $39/mo | analysts/journalists/founders | unlimited topics, 15-min, PDF/Notion + citation export, read-only API key |
| Team/API | $499/mo+ | B2B | webhook + raw fact/timeline stream, SLA, seats |

**B2B wedge — compliance/regulatory first** (atomic facts + `event_date` + `verified_count` + `source_url` = an audit trail; sticky annual contracts). Hedge-fund event-tracking second (churns harder, demands uptime).

**The Verifier function** (cross-source `verified_count`, date sanity, entity grounding) is what justifies the 10× B2B price — but it's *cheap bookkeeping folded into the harvester/dedup*, **not a separate stage**.

**Revenue path (conservative):** ~$450 (mo 3, 50 Pro) → ~$2.3K (mo 6, +1 compliance) → ~$11.5K (mo 12) → ~$45K (mo 24). The architecture is more enterprise-shaped than consumer-shaped — expect B2B to over-index vs v1's projection.

---

## 15. Build sequence

**Now (cheap, evidence-backed, independent, fixes the §2 red lights + cuts cost):**
1. Harvester: mandatory `event_date` + year/sanity clamp; emit `importance` + `context` inline.
2. Relevance gate (drop off-topic facts).
3. **Entity-aware fact dedup** (semantic + temporal + entity/place) — the load-bearing correctness fix.
4. Drop the live-path briefer (assemble from `fact`+`context`).
5. **Pause** the story graph + `story_summarizer` (keep code).
6. Within-run batching (judge), URL/article dedup, cache QueryBuilder, gate scans on new content.
7. Per-run cost telemetry.

**Next:**
8. Fast-adaptive (spike-responsive) AYR; per-(topic×tool) AYR + coalescing window.
9. History doc (no-LLM first).
10. `user_topic_state` + the delta query + the one-surface Home (`v3-briefing`).
11. Cost-aware AYR; set-time digest + breaking toggle.
12. Shared-memory access layers (UI/email/API share one ledger).

**Later / at scale:**
13. Budget controller (once telemetry can predict); Option B limits + margin shield.
14. Timing/pattern scan learning (the social-pivot moat).
15. Spliced timeline + (un-paused) linked-thread graph for B2B; the shared "sale" UX (test).

> Nothing here is a from-scratch rebuild — ~80% of the pipeline (collector, harvester, dedup, vector store, AYR, MMR, infra/auth/billing) is reused. Steps 1–5 alone fix the live red lights.

---

## 16. Decision log · red lights · open questions

### Locked decisions
- **Thread-primary, brief-as-computed-delta** ($0 home render, free personalization, no three-representation noise).
- **Fact-level dedup = semantic + temporal + entity/place is load-bearing**; the story graph is **paused** (it was the worst, most expensive component on real data).
- **`event_date` mandatory + year clamp; relevance gate** (fix the verified red lights).
- **Harvester emits `context` inline → briefer removed** from live path.
- **History doc no-LLM-first**; spliced timeline reserved for B2B.
- **Per-(topic×tool) cost-aware AYR**, spike-responsive estimator, coalescing window.
- **Article selection:** domain-diversity penalty + syndication collapse + corroboration preserved.
- **One shared fact ledger; B2C/B2B are access layers; never scan the same topic twice.**
- **UI = one surface, radical subtraction** (`v3-briefing`); **two channels = one feed in two envelopes** (live vs digest), chosen by gap-since-last-seen (§13).
- **Two-clock model:** every fact carries `published_at` (release) + `event_date` (development) + `date_basis`; the feed gates on **development recency, not `first_seen_at`**; large-lag facts route to history (if they connect) or are suppressed (if orphan) — §8B.
- **Budget controller = graceful degradation, never hard-block, tier-aware.**

### 🔴 Red lights (from live data — fix regardless)
1. Date *year* hallucination reaches delivered briefs.
2. Story-clustering magnet node (45% of facts in one 2-year node) — paused.
3. Relevance leaks (off-topic facts).
4. **Old-but-newly-seen fact shown as breaking** — a year-old event extracted from a fresh article landed in "today" with no date/context. Root: feed gated on "new to us" not "new to the world" (two clocks conflated). Fix = §8B.

### Open questions
- **Cost model:** lock Option A for launch, commit to Option B's timeline post-telemetry? (§11)
- **Soft/hard thresholds:** exact numbers — calibrate on real cost data.
- **Depth definition:** measure depth-cost by article-count proxy or by measured average cost? (affects attribution + the merge schedule)
- **History doc:** does the no-LLM timeline read well enough, or is the one glue-pass needed? (empirical, post-build)
- **Shared "sale" UX:** marketplace vs. soft nudge — test when there.

---

## 17. Source layers & plugin architecture

### Plugin interface
Every source is a self-contained plugin:
```python
class SourceLayer(ABC):
    def search(self, query: SearchQuery) -> List[RawArticle]:
        ...
```

> **Why plugins?** You must be able to add, remove, and swap sources without touching core code. Sources die, APIs change pricing, new ones launch. This is config, not code.

### Phase 1 — MVP ($0 cost)
| Layer | API | Cost | Good for |
|---|---|---|---|
| `RSSLayer` | Direct RSS feeds (curated) | **Free, unlimited** | Publisher-direct, real-time, original URLs |
| `TavilyLayer` | Tavily API | **Free (1,000 credits/mo)** | Any topic, returns clean full text, no scraping |

> **Why NOT Google News RSS in Phase 1?** Links are encoded redirect URLs (`news.google.com/rss/articles/CBMi…`). Decoding them requires calling a Google internal endpoint that changes frequently and breaks decoders. Unreliable for production.

> **Why NOT NewsAPI.org?** Free tier has a 24-hour delay and their ToS **explicitly forbid production use**. Using it in a deployed product = license revocation. Never.

### Phase 2 — Adding coverage
| Layer | API | Cost | Good for |
|---|---|---|---|
| `RSSLayer` | Direct RSS | Free | Always the primary backbone |
| `TavilyLayer` | Tavily | Free / pay-per-use beyond 1K | Core; now metered beyond free limit |
| `GoogleNewsRSSLayer` | Google News RSS (with decoder) | Free (unofficial) | Broader coverage, accepted fragility |

### Phase 3+ — Scale
| Layer | API | Cost | Good for |
|---|---|---|---|
| `BraveLayer` | Brave Search | ~$5/mo (~1K requests) | Broad web search |
| `ExaLayer` | Exa API | $7/1K requests | Semantic deep search, PDFs |
| `SocialLayer` | Apify | Pay-per-use | Twitter/Reddit real-time |

### Source router
Which plugins fire for which topic — controlled by config, not code:
```yaml
# routing_rules.yaml
defaults:
  layers: [rss_layer, tavily_layer]   # Phase 1 defaults

overrides:
  - domain: finance
    add_layers: [sec_edgar_layer]
  - domain: tech
    add_layers: [github_layer]
```

**Router evolution (§21):** V1 = LLM classifier (~$0.001/call) → V2 = fine-tuned small classifier on our routing data → V3 = feedback loop (user says "missed finance context" → router adjusts).

### Article extraction
- Use `trafilatura` for clean full text (strips ads/nav/boilerplate). Tavily results skip this (already clean).
- Cache every article by URL hash — **never fetch or process the same article twice.**
- Respect rate limits and robots.txt.

---

## 18. Tech stack & "what NOT to use"

> **Principle:** Start boring. Add complexity only when proven necessary. Every extra service is ops burden.

### Backend
| Component | Tech | Why |
|---|---|---|
| Language | **Python** | LLM ecosystem, AI libraries |
| API Framework | **FastAPI** | Async, auto-docs, type-safe, production-ready |
| Task Queue | **Celery + Redis** | Background pipeline jobs, scheduled runs (Celery Beat) |
| Database | **Supabase** (PostgreSQL) | Zero-maintenance, pgvector built-in |
| Vector Search | **pgvector** via Supabase | No extra service; lives in Postgres |
| Cache | **Redis** | Already running for Celery; article cache, rate limiting |
| LLM — cheap | **Gemini Flash** | Default for all pipeline calls: fast, cheap, good enough |
| LLM — quality-critical | **Gemini Pro** (or swap via settings) | Harvester upgrade for production when budget allows |
| Content extraction | **trafilatura** | Best Python lib for clean article text; no browser needed |

All model names live in `settings.py` / `LLMClient` — **never hardcoded anywhere.**

### Frontend
| Component | Tech | Why |
|---|---|---|
| Framework | **Next.js 14** (App Router) | SSR for SEO, file-based routing |
| Styling | **Tailwind CSS** | Fast iteration, consistent |
| State/data | **React Query** | Server state, caching, auto-refetch |
| Auth | **Clerk** | Never build auth yourself |

### Infrastructure costs
| Component | Tech | Monthly cost |
|---|---|---|
| Backend | Railway | $5–20 |
| Frontend | Vercel | $0–20 |
| PostgreSQL + pgvector | Supabase (free → Pro $25) | $0 → $25 |
| Redis | Railway/Upstash | $0–10 |
| LLM (production) | Gemini Flash pay-per-use | $10–50 |
| News APIs Phase 1 | RSS (free) + Tavily (1K free/mo) | **$0** |
| News APIs Phase 3+ | Tavily / Brave / Exa | $5–30 |
| Domain + CDN | Cloudflare | ~$1 |
| Payments | Paddle | % of revenue |
| **Total prototype (mo 1–6)** | | **~$10–50** |
| **Total production (mo 6+)** | | **~$50–150** |

### What NOT to use (and when to upgrade)
| Don't use | Use instead | Upgrade when |
|---|---|---|
| Qdrant / Pinecone / Weaviate | pgvector via Supabase | 500K+ vectors with latency issues |
| Kubernetes | Railway/Render | Multi-region or 10+ services needed |
| Kafka / RabbitMQ | Celery + Redis | Processing 10K+ messages/sec |
| Microservices | Monolith | Team grows to 3+ people |
| Native mobile app | PWA | 10K+ active users requesting native |
| NewsAPI.org | Direct RSS + Tavily | Never (24h delay + ToS violation) |
| Google News RSS | Direct RSS first | Phase 2 only, accept fragility |

---

## 19. Monetization detail

### The core argument
> *"Why pay for news when it's free everywhere?"*

**You're not paying for news. You're paying for TIME.** Free news costs hours of scrolling, clicking, filtering. TrueBrief costs 30 seconds per topic. The product is **attention efficiency**, not journalism.

### B2C tiers (current)
| Tier | Price | Who | Hook |
|---|---|---|---|
| Free | $0 | wedge | curated shared list, daily, web only |
| Pro | $9/mo | power readers | 15 topics, hourly, email+push, history |
| Researcher | $39/mo | analysts/journalists/founders | unlimited topics, 15-min, PDF/Notion export, read-only API key |
| Team/API | $499/mo+ | B2B | webhook + raw fact/timeline stream, SLA, seats |

**Per-user cost at Pro ($9):** ~$0.80/mo in LLM+API → **~91% gross margin.** (Estimate; re-derive from real telemetry post-launch.)

### Conversion levers
| Trigger | Action |
|---|---|
| After 7 days of use | Show "You saved X hours this week" |
| User tries to add 3rd topic | Soft paywall: "Upgrade for more topics" |
| User clicks a brief that's delayed | "Get real-time updates with Pro" |
| Free email digest | Persistent value reminder → "Upgrade for hourly" |
| Public shared briefs | Viral loop: "Powered by TrueBrief" |

### B2B revenue (the real money)
| Offering | Price | Target customer |
|---|---|---|
| **API access** | $0.01–0.05 per brief / metered | Developers embedding news intel |
| **White-label** | $500–2K/mo | Agencies, media companies |
| **Enterprise** | $1K–5K/mo (custom) | PR, risk, competitive intel, compliance |

**Target B2B use cases:** PR/comms (brand monitoring), investment firms (portfolio tracking), competitive intelligence, risk/compliance (regulatory monitoring), research (policy, industry trends).

> Even 5 enterprise clients at $2K/mo = $120K/year. That's a sustainable solo-dev business.

### Revenue projections (conservative B2C + B2B blend)
| Milestone | Timeline | B2C/mo | B2B/mo | Total |
|---|---|---|---|---|
| 50 Pro, first compliance pilot | Month 3 | $450 | $0 | ~$450 |
| 300 Pro, 1 compliance contract | Month 6 | $2.7K | $2K | ~$4.7K |
| 1,500 Pro, 5 B2B | Month 12 | $13.5K | $10K | ~$23.5K |
| 5K Pro, 15 B2B | Month 24 | $45K | $30K | ~$75K |

> v3 revenue path skews more B2B than v1's projection (the atomic facts + `event_date` + `verified_count` + `source_url` = audit trail that compliance will pay for). Calibrate these against actual conversion data.

---

## 20. Key risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| **LLM costs spike** | Margin destruction | Shared pipelines + fast-path + caching + budget controller (§10); never one model hardcoded |
| **News APIs shut down / change pricing** | No data | Multiple redundant source plugins (§17); never depend on one; RSS is always the backbone |
| **Users won't pay** | No revenue | Focus B2B early (B2C = growth engine, not primary revenue); M2 validation before M3 investment |
| **Hallucinated facts** | Trust destroyed / B2B churn | Always link sources (`source_url`); confidence thresholds; `verified_count` as the Verifier signal |
| **Legal / copyright** | Shutdown | Extract facts (transformative use — see §22); never republish full articles; respect robots.txt |
| **Competitor with a data flywheel** | Irrelevant | Our moat: per-user delivered-fact memory + AYR source reputation + shared ledger. More users → better AYR → better routing → network effect. First-mover on this specific architecture matters. |
| **Solo dev burnout** | Everything dies | Ship in phases; get paying customers early; reinvest in help; don't build M4/M5 before M2 validates |
| **Date hallucination (verified live)** | Brief quality / trust | Year guard + sanity clamp in harvester — already in §5 / §16 red lights |
| **Magnet-node clustering (verified live)** | Confusing output / LLM waste | Story graph paused; entity-aware dedup is load-bearing — §3/§5 |

---

## 21. Long-term moat & domain pipelines

### The five compounding moats
1. **Per-user fact memory** — longer usage → better delta detection → more trust. No competitor has this at the fact level.
2. **Source quality data (AYR)** — system learns which sources are reliable *per topic*. Gets smarter automatically.
3. **Shared intelligence** — more users → more topics covered → more efficient for everyone. Shared ledger = cost drop with scale.
4. **Domain pipelines** — 12+ months of domain-specific training data, custom prompts, specialized sources. Can't be quickly replicated.
5. **Habit** — once someone replaces their news routine, switching cost is high. The all-quiet hero state is *itself* a retention mechanic.

### Domain intelligence pipelines (Phase 6 / Year 2+)
The general pipeline works for any topic but is sub-optimal for specialized fields. Domain pipelines are custom configurations:
- **Specialized sources** (SEC EDGAR for finance, PubMed for medical, court dockets for legal)
- **Custom harvester prompts** (financial fact extraction needs numerical precision; legal needs citation tracking)
- **Custom arbiter rules** ("1% change in EPS = UPDATE, not MERGE")
- **Domain-specific fact fields** (`ticker`, `financial_metric`, `ruling_citation`)

```
USER PROMPT → ROUTER (which domains?) → run matching pipelines → merge facts → Arbiter → Brief
```

| Domain | Differentiator | B2B target |
|---|---|---|
| `finance` | SEC filings, ticker tracking, earnings precision | Hedge funds, analysts |
| `legal` | Court dockets, citation-aware facts | Law firms, compliance |
| `medical` | PubMed, clinical trials, drug approvals | Pharma, biotech |
| `geopolitics` | Diplomatic sources, conflict trackers | Think tanks, defense |

**Build sequence:** general pipeline first (M1–M3). Pick the domain your first B2B customer needs. Build ONE completely before the next. Each domain = a new market segment funded by B2B revenue.

**Future features (Phase 5, post-launch):**
- Contradiction detection: two sources disagree on the same fact → flag for user
- Multi-language support (multilingual embeddings)
- Source quality reputation network (AYR shared across users = system-level source ranking)
- Specialized source plugins: SEC EDGAR, FDA, PubMed, EU regulatory feeds

---

## 22. Legal & copyright posture

**Core argument: extracting facts = transformative use.** TrueBrief does not republish articles, paraphrase at length, or substitute for the original publication. It extracts atomic, verifiable facts — a form of analysis and commentary that is widely recognized as transformative under fair use doctrine.

**Operational rules (non-negotiable):**
1. **Never store or display full article text** — store only extracted facts + the `source_url` pointing back to the original.
2. **Always display source attribution** — every fact shows its `source_domain` and links to `source_url`. This is also a feature (J7: provenance).
3. **Respect robots.txt** — the collector checks robots.txt before scraping any URL. Tavily / RSS sources don't require scraping and handle this natively.
4. **DMCA takedown process** — if a publisher objects, we can remove all facts traced to their `source_domain` in one query. Document this process before B2B launch.
5. **Never process behind a paywall** — only publicly accessible content. Paywalled articles that Tavily/RSS can't access are skipped, not scraped.

**The B2B angle:** the fact-extraction model is *more legally defensible* for enterprise customers than a summarization model (summaries are closer to derivative works; atomic facts are closer to reported data). This is a selling point for compliance/legal B2B use cases.

> **Not legal advice.** Consult a lawyer before B2B launch, particularly around jurisdiction-specific rules (EU/GDPR, German press law Leistungsschutzrecht, etc.).
