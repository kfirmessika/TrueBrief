# TrueBrief — Architecture v2 (Redesign from the Goal)

> **Status:** Proposal. The original [architecture.md](architecture.md) is preserved untouched.
> This document redesigns the product from first principles — the goal first, then the user jobs,
> then the system, then the UI, then the backend. It reuses ~80% of the existing pipeline code;
> the changes are to the **data model**, the **product shape**, and the **UI**.
>
> Read the v1↔v2 comparison + red lights at the bottom (§12) if you read nothing else.

---

## 0. Why a v2 at all

v1 is a strong engineering design with one product-level flaw: **it treats the "brief" as the primary object.**
The pipeline generates a brief document every run, briefs accumulate as a chat-style thread, and then —
to recover the story structure that got fragmented across briefs — v1 bolts on a separate *Stories* tab and
an *Insights* tab. The result is **three different representations of the same underlying events**
(briefs, stories, insights). For a product whose entire thesis is *max signal / min noise*, shipping the user
three views of the same facts is the original sin.

v2 fixes this by inverting the model: **the brief is a computed diff, not a stored document.**

---

## 1. First principles

### The goal
Keep a person current on what they care about, delivering **maximum new signal with minimum noise, in the least time.**
The product is *attention efficiency*. News is just the first domain.

### The inversion that dictates the whole design
Every news product optimizes **time-on-app** (scroll, autoplay, "more below"). TrueBrief's promise is the opposite:
**spend less time.** A great session is *short* — open, learn what changed, feel caught up, leave.

| Normal news product | TrueBrief |
|---|---|
| Rewards scrolling | Rewards **closure** |
| Empty state = failure | Empty state = **the product working** |
| Infinite bottom | **Finite bottom** — the page ends |
| Shows everything happening | Shows only what **changed for you** |
| "What's happening" | "What changed **since you last looked**" |

### One sentence
> *Stop reading the news. Read a memo about it — one that remembers what it already told you.*

---

## 2. What we actually give the user (jobs to be done)

Before any system or screen, the five jobs the product exists to do:

| # | Job | Priority | How v2 serves it |
|---|-----|----------|------------------|
| **J1** | *"What changed since I last looked?"* | **Primary** | The Briefing (home): the ranked delta across all threads |
| **J2** | *"Do I have enough context to understand this change?"* | **Primary** | Each thread carries a living "story so far" summary, shown on demand |
| **J3** | *"Show me the full history of this story."* | Secondary | Thread detail: the fact timeline, newest-first |
| **J4** | *"Am I caught up? Is the system actually watching?"* | **Primary** | The "all quiet" state + "we read N articles, M passed" closure stat |
| **J5** | *"Watch this new thing for me."* | Entry | New-topic flow |
| J6 | *"Tune the signal — mute this, more/less often."* | Support | Per-thread mute + per-topic frequency |
| J7 | *"Is this true / where's it from?"* | Always-on | Provenance + verified-source count, shown subtly everywhere |

J1 and J4 are the product. J2/J3 are *context on demand* — present but never in the way. Everything else supports.

**The design rule that falls out:** the default surface shows **only deltas**, ranked, with context one tap away.
Stable knowledge is collapsed to near-nothing. *Signal is created by suppressing noise, not amplifying signal.*

---

## 3. The core model shift: the Living Thread

### The three units, and why "thread" is the right one

| Unit | Granularity | Problem |
|------|-------------|---------|
| **Brief** (v1 primary) | One per pipeline run | A single story gets fragmented across many brief documents; user must mentally stitch |
| **Topic blob** ("one giant story per topic") | One per topic | Too coarse — blurs distinct events (FTC probe ≠ funding round) into mush; loses signal |
| **Story Thread** ✅ | One per evolving story | Just right: a topic is a *handful* of living threads, each a single evolving document |

A **Story Thread** is the durable object. It owns:
- a **title** ("OpenAI Funding Round"),
- a **living summary** — the rolling "story so far," edited *incrementally* as facts arrive,
- a **fact timeline** — the atomic facts under it, ordered by event date,
- **movement metadata** — `last_moved_at`, `importance`, `momentum`, `source_count`.

### The brief becomes a query, not a document
"What's new for this user" = **the threads whose `last_moved_at` is newer than this user's `last_seen_at`**, ranked by importance.
- No brief documents stored as the source of truth.
- The home screen is assembled from already-clean stored text (facts are already standalone sentences; summaries already exist) → **zero LLM cost to render the most-used screen.**
- The Briefer LLM is demoted: it only runs to phrase the **email digest** (and optionally polish a delta). It no longer generates a document every run — removing both cost and a hallucination surface.

### Summaries: regenerate from facts, do NOT recurse
The instinct *"don't re-run the whole summary, just merge the new bit"* is right, but the obvious implementation (`new_summary = LLM(old_summary + new_delta)`, applied over and over) is a **telephone game** — after ~50 updates the summary silently drops numbers and hallucinates. That's a real scale failure.

Fix: **the facts are the source of truth; the summary is derived.** Keep every fact structured; **regenerate the summary from the thread's recent/important facts when it's actually viewed** — not incrementally on every fact. Regenerating *from source facts* (never from the previous summary) eliminates drift, and it's cheaper: one summarize call per thread *per view-day*, not one per fact. Batch naturally (a thread viewed once a day = one call).

### Threads are a linked graph, not immortal blobs and not a global tree
A topic's threads form a **loose, weighted graph**:
- **Small, bounded threads** stay coherent (no 500-fact mega-thread that drifts or merge-creeps).
- **Edges link related threads.** When a dormant story reignites, we don't reopen one immortal node and we don't run a "thread lifetime" timer (both were wrong). Instead a **new thread spawns, linked to its predecessor** — "Iran conflict resumes" → edge → "Iran ceasefire, March." The story stays alive *through the edges*; each node stays small. The "ending" of a thread is emergent, never a setting.
- **Threads never leave the vector index.** "Quiet/dormant" is a *display + ranking* state (low momentum), not deletion. A new fact always searches *all* threads, hot and cold — so the 50-days-later reconnection just works. Vectors are tiny; keeping dormant threads costs ~nothing.
- **Never materialize the whole graph.** Edge-detection is a real (but lower-stakes, lower-volume) coreference problem — a wrong edge is nearly invisible, unlike a wrong fact-assignment which is visible noise. Query the graph **only in local neighborhoods** ("threads linked to *this* one"). The moment you try to maintain one globally-consistent "big tree," you are back in the collapse-at-scale corner. Local graph = fine forever; global tree = the trap.

> **Scope discipline (the honest part):** durable cross-week event threading is the *hard* corner of an unsolved NLP problem (online event coreference) and degrades worst on broad, long-lived topics. So **B2C MVP = rolling-window dedup with light, short-lived linked threads** (reliable, cheap). The full persistent linked-graph is hardened as a **B2B** feature, where the timeline *is* the product and the compute is paid for. Edges are an **additive layer**: ship threads without them; turn them on later; if an edge is wrong you still have working threads (graceful failure).

- **Batching:** 3+ updates to one thread in a single run → one regenerate call.

---

## 4. Data model (the objects v2 needs)

```
topics                         (shared — one row per unique query; unchanged from v1)
├── id, raw_query (unique, lowercased)
├── scope/search_strategy (jsonb)
├── poll_interval_seconds, last_run_at, next_run_at

story_threads                  ★ ELEVATED to primary object (v1 "story_nodes" + new fields)
├── id, topic_id → topics
├── title                      short label
├── living_summary             rolling "story so far" (~70 words)
├── summary_embedding          vector — clusters incoming facts into the right thread
├── importance         float   0–1 aggregate; drives ranking on the Briefing
├── momentum           int     facts in last 7d; feeds ranking + AYR
├── status                     active | quiet | dormant
├── source_count       int     distinct corroborating domains
├── fact_count         int
├── first_seen_at, last_moved_at   ← last_moved_at is THE field that powers deltas

facts                          (= v1 known_facts / Alpha; tightened)
├── id, topic_id, thread_id → story_threads
├── text                       clean standalone sentence
├── embedding                  vector
├── entities (jsonb)
├── event_date         date    ★ MANDATORY (see §5) — no fact without a verifiable date
├── importance         float   0–1, emitted free by the Harvester
├── confidence         float
├── verified_count     int     ★ how many independent sources stated it (Verifier, §5)
├── source_url, source_domain
├── first_seen_at

user_topic_state               ★ NEW — the object that makes per-user deltas free
├── user_id, topic_id          (PK pair)
├── last_seen_at               deltas = threads.last_moved_at > last_seen_at
├── muted_thread_ids (jsonb)   per-thread noise control (J6)

pipeline_runs                  ★ telemetry, powers the "closure" stat (J4)
├── id, topic_id, run_at
├── articles_collected, articles_read, facts_extracted, facts_passed, duplicates
├── llm_cost_usd

briefs                         (OPTIONAL now — a denormalized snapshot for email/history/sharing,
                                NOT the source of truth)
```

### The delta query (the whole home screen, ~1ms, $0 LLM)
```sql
SELECT th.*
FROM story_threads th
JOIN topic_subscriptions ts ON ts.topic_id = th.topic_id AND ts.user_id = :me
JOIN user_topic_state    us ON us.topic_id = th.topic_id AND us.user_id = :me
WHERE th.last_moved_at > us.last_seen_at
  AND NOT (th.id = ANY (us.muted_thread_ids))
ORDER BY th.importance DESC, th.last_moved_at DESC;
```
- **"Quiet"** = subscribed threads where `last_moved_at <= last_seen_at`.
- **"All quiet"** = the query returns zero rows.
- **Closure stat** = `SUM(articles_read), SUM(facts_passed)` over `pipeline_runs` since `last_seen_at`.
- **Personalization on shared topics** = automatic: the same thread shows a different "what's new" line to each user, because each user's `last_seen_at` differs. *This is the per-user delta v1 promised but never delivered.*

Indexes: `story_threads(topic_id, last_moved_at)`, `story_threads(topic_id, importance)`.

---

## 5. The pipeline (6 stages)

```
COLLECTOR → HARVESTER → VERIFIER → ARBITER → LEDGER (threads + living summary) → [BRIEFER*]
   reuse      reuse+      NEW       reuse        reuse + thread elevation         email only
            importance
```

What changes from v1, stage by stage:

1. **Collector** — *unchanged*, plus one cheap win: **URL-dedup against `facts.source_url` (last 14d) before MMR**, so the same article is never re-processed across runs. (Fixes a known v1 waste.)
2. **Harvester** — *unchanged* except the prompt:
   - `event_date` is **mandatory**. *"If the article does not anchor the event in time, do not extract the fact."* Plus a sanity window: drop/flag dates >365d from the article's publish date. (Fixes the v1 "87% missing date / 2020 leak" bug that silently breaks dedup.)
   - emit **`importance` 0–1** per fact — free, the LLM is already reading the article.
3. **Verifier** — **NEW, zero extra LLM calls.** Per fact: (a) **cross-source confirmation** — is this stated by ≥2 independent domains in the same window? set `verified_count`; (b) **date sanity** vs publish date; (c) **entity grounding** — do the claimed entities actually appear in the text (cheap regex)? This is what lets B2C show "verified · 3 sources" and lets B2B trust the feed enough to pay 10×.
4. **Arbiter** — *unchanged logic* (fast-path auto-merge/auto-new + grey-zone Judge LLM + temporal adjustment). It now also **routes the fact to a thread** (which beat it updates). Tune thresholds *after* event_date is fixed, not before — the score distribution will change.
5. **Ledger / Thread manager** — assigns fact to the right `story_thread` via `summary_embedding` similarity (≥0.70) or opens a new thread; updates `living_summary` incrementally; bumps `last_moved_at`, `importance`, `momentum`, `source_count`.
6. **Briefer\*** — **demoted.** Renders nothing for the home screen (assembled from stored text). Runs **only** to phrase the email/push digest. Optional.

**Net effect on cost:** runs that produce no new signal cost ~$0 of generation (no brief doc). The expensive call (per-run document generation) is gone.

---

## 6. The per-user delta engine

The home screen for any user is the delta query in §4. Properties:
- **$0 LLM** to render. Pure Postgres.
- **Personalized for free** even on shared topics, via `last_seen_at`.
- **Scales linearly in DB, not in LLM** — 10,000 users on a shared topic = one pipeline run + 10,000 cheap indexed queries.
- On view, advance `last_seen_at = now()` (or to the newest thread shown), so tomorrow's delta is clean.

This is the literal implementation of v1's "shared topic, personalized deltas" insight ([architecture.md:492-501]) — which v1 designed economically but never built into the data model.

---

## 7. Importance & ranking (how "max signal" is enforced)

Not all deltas are equal; ranking *is* the signal filter. Computed with **no dedicated LLM call**:

```
fact.importance        ← emitted by Harvester (free)
fact.verified_count    ← Verifier (free)

thread.importance = w1 · max(fact.importance in thread)
                  + w2 · normalize(verified_count)
                  + w3 · momentum_decay(last_moved_at)
                  + w4 · is_new_thread_bonus
```
Tuned weights, recomputed on each update. The Briefing sorts by `thread.importance`. A user's "show me only high-signal" toggle is just a threshold on this number. The "quiet" zone is everything below the fold of relevance.

---

## 8. UI architecture — one surface, radical subtraction

> **Correction to the first v2 draft.** The first pass (`v2-app.html`: Home + sidebar + Topic page + Thread overlay) was designed around the *data model* (topic → thread → fact), not the user's moment. It read busy — it surfaced the product's *proof* (article counts, "verified" chips, topic dots, stat bars) instead of just the *answer*. Showing the evidence-of-value everywhere **is** noise; it violates the thing we sell. Clean is **subtraction**, not styling.

### The discipline
For every element on the surface: *does removing it lose signal?* If not, it's gone. Sources, counts, verification, timestamps, the fact-timeline → all moved *inside a tap* or deleted. The home screen reads like **a brief from a smart friend**: a calm count, a few plain sentences, silence confirmed.

### The one surface (default = "what's new")
```
TrueBrief                                   all topics ▾   Jun 9

● 3 new today

OpenAI closed its funding round at $40B, valuing it at
$300B — the biggest private tech raise ever.
   openai · 2h

The FTC opened an antitrust investigation into Microsoft's
exclusive cloud deal with OpenAI.
   openai · 5h

The Fed held rates steady but signaled two cuts before year-end.
   fed rates · 6h

──
Nothing else moved across your other 4 topics.
```
- **Tap a sentence → it expands in place**: one breath of "story so far" + the source domains, tucked underneath. Tap again to collapse. (This is the old "thread overlay," subtracted to its essence — *context*, not a fact-by-fact timeline. The atomic-fact timeline leaked the data model onto the screen; it becomes a rare power/B2B view, not the default.)
- **Topics are a filter, not a sidebar.** Default view merges everything new. "all topics ▾" narrows if you *choose* to — topics are not a wall of dots and badges you navigate.
- **Caught-up is a first-class screen:** just `✓  All caught up.` + one calm line. No numbers, no boast. It's what users see most days; it must feel like a gift, not a dead end.

### What exists, and where
| Surface | Job | Note |
|---------|-----|------|
| **The Briefing (the app)** | J1, J2, J4 | the one screen; deltas + tap-to-expand context + caught-up state |
| **Topic filter / manage** | J3, J6 | reach for it on purpose: see all threads of one interest, set frequency, mute |
| **Full thread history** | J3 (rare) | the fact-by-fact timeline + linked threads — power/B2B, behind a deliberate "see everything" |
| **New topic** | J5 | a text box + a live "here's what we'll watch" preview |

### Killed outright
- ❌ Chat-bubble brief feed · ❌ separate Stories tab · ❌ separate Insights tab (AYR/query variants → `/admin`, builder telemetry) · ❌ surface-level stat bars, verified chips, topic-dot sidebar, per-item eyebrows.

> HTML mockup of the real direction: **`reports/v3-briefing.html`** (one screen, plain sentences, tap-to-expand, caught-up toggle). Supersedes `v2-app.html`/`v2-new-topic.html`, which are kept only to show what "too busy" looked like.

---

## 9. Cost model

Per shared-topic run (~10 articles):
| Stage | Calls | Note |
|-------|-------|------|
| Harvester | ~10 flash (or 1 batched) | extracts facts + importance |
| Verifier | 0 | bookkeeping |
| Arbiter | ~50% of grey-zone facts | fast-path skips the rest |
| Summarizer | 1 per *moved* thread (few) | incremental |
| Briefer | **0** | assembled, not generated |
| Embeddings | ~30 | cheap |

**Target ≤ $0.03/run** (vs v1's ≤$0.05 — the per-run brief document is gone).
A run that yields no new signal ≈ **$0 generation**.

Per-user-month (cost is shared across all subscribers of a topic):
- Free (3 shared topics, daily): **< $0.05/mo** — Home renders are free DB queries.
- Pro (15 topics, hourly): **~$0.40/mo** → at $9/mo that's **>95% gross margin.**

The most-used action in the product (open Home, read the delta) has **zero marginal LLM cost.** This is the single biggest economic improvement over v1.

---

## 10. Business design

### Positioning: "the memo, not the feed"
Sell a closed-loop **memo per interest** ("since you last looked, here's what changed, here's the context, here's what *didn't*"). The delta engine is the hero, not an internal optimization. Anti-positioning: **no chat interface** (GNOMI owns that frame and it's open-ended = noise), no article summaries (you extract facts), no engagement mechanics.

### Tiers
| Tier | Price | Who | Hook |
|------|-------|-----|------|
| **Free** | $0 | wedge | 3 shared topics, daily, web only — generous on purpose |
| **Pro** | $9/mo | power readers | 15 topics, hourly, email + push, history search |
| **Researcher** | $39/mo | analysts, journalists, founders | unlimited topics, 15-min, **PDF/Notion export**, **citation export**, read-only API key |
| **Team / API** | $499/mo+ | B2B | webhook delivery, raw fact + thread-graph stream, SLA, 5 seats |

The old $20 "Power" tier is no-man's-land. Split into Researcher ($39) and Team/API ($499+) to capture both ends.
**The Verifier stage (§5) is what justifies the B2B price** — an auditable, source-triangulated fact stream is a compliance/finance product, not an $8 toy.

### B2B wedge: **compliance/regulatory monitoring first.**
`facts(text, event_date, verified_count, source_url)` *is* an audit trail. "Did our team know about regulation X on date Y?" is answered directly by the ledger. Sticky annual contracts, low logo-risk. (Hedge-fund event tracking is the second wedge but churns harder and demands trading-hours uptime.)

### Revenue path (conservative)
| Month | B2C | B2B | Total | Gate to pass first |
|-------|-----|-----|-------|--------------------|
| now | $0 | $0 | $0 | **close the dedup loop (event_date)** |
| 3 | 50 Pro = $450 | 0 | $450 | 50 hand-picked beta users say "cleaner than Google News" |
| 6 | 150 Pro + 5 Researcher | 1 compliance = $800 | ~$2.3K | pricing page + B2B landing |
| 12 | 600 Pro + 30 Researcher | 5 B2B | ~$11.5K | sales motion |
| 24 | 2k Pro + 200 Researcher | 15 B2B | ~$45K | hire |

---

## 11. Build sequence (realistic, reuse-first)

**What you reuse as-is (the good news):** Collector + all source layers, Harvester (prompt edit only), Arbiter (logic), vector store + pgvector, story nodes (renamed/elevated), AYR, MMR, shared-topic infra, Clerk/billing/Celery/FastAPI. The pipeline is ~80% intact.

| Step | Work | Complexity | Why this order |
|------|------|-----------|----------------|
| 1 | Harvester: mandatory `event_date` + sanity window + emit `importance` | S | Unlocks dedup + ranking |
| 2 | Collector: URL-dedup before MMR | S | Kills cross-run waste |
| 3 | Add `user_topic_state` table + advance `last_seen_at` on view | S | The delta engine |
| 4 | Elevate `story_nodes`→`story_threads` (+ importance, momentum, last_moved_at, source_count) | M | The primary object |
| 5 | Verifier stage (cross-source, date, entity grounding) | M | Unlocks B2B + "verified" UI |
| 6 | Home delta query + endpoint `GET /briefing` | S | $0 home screen |
| 7 | Demote Briefer → email-only; Home assembles from stored text | M | Cost + de-risk |
| 8 | Frontend: build Home (Briefing) + Thread overlay; keep old topic page behind a flag | L | Ship the new shape |
| 9 | Re-run 5 topics 48h, re-audit, tune Arbiter thresholds on clean data | M | Prove the moat |
| 10 | Kill Stories/Insights tabs; Topic page → living threads | M | Remove the three-representations noise |

Nothing here is a from-scratch rebuild. Steps 1–3 alone (a few days) already make the current product measurably better.

---

## 12. v1 ↔ v2 comparison + RED LIGHTS

### What's the same (so the change is safe)
5-pillar pipeline, shared-topic economics, AYR, dual vectors, fast-path Arbiter, MMR, plugin sources, the entire infra/auth/billing stack. **v2 is a remodel of the data model + UI on top of v1's engine, not a teardown.**

### What's different (and why)
| Dimension | v1 | v2 | Why v2 |
|-----------|----|----|--------|
| Primary object | Brief (document) | **Story Thread (living)** | Stops fragmenting one story across many briefs |
| "What's new" | Stored generated brief, same for all | **Computed delta vs your `last_seen`** | Real per-user personalization; $0 LLM |
| Representations | Briefs + Stories + Insights (3) | **Threads (1)** | Three views of the same facts *is* noise |
| Briefer | Generates a doc every run | **Email only** | Cuts cost + hallucination surface |
| Home cost | LLM per run | **DB query** | The most-used screen is free |
| event_date | "optional / unknown" | **Mandatory + sanity** | Without it, dedup silently degrades to cosine-only |
| Verification | none | **Verifier stage** | The thing B2B pays 10× for |

### 🔴 RED LIGHTS in the current build (fix regardless of v1/v2)
1. **`event_date` is 87% empty → the delta engine is currently degraded to plain cosine similarity → paraphrases are stored 8–15× as "new."** The moat does not work today. This is the #1 thing. (Root cause: the Harvester prompt explicitly permits `"unknown"`.)
2. **Per-user deltas are promised but not implemented.** v1 serves one identical brief to every subscriber; there is no `last_seen` model. The headline feature ("only what's new *to you*") isn't real yet.
3. **Three-representation UI (briefs/stories/insights).** Directly contradicts "min noise." Users must reconcile three views of the same events.
4. **Briefer generates a document every run** — pays LLM cost and risks hallucination even when nothing changed.

### 🟢 GREEN LIGHTS (de-risk the migration)
- 80% of pipeline code is reused.
- Story nodes already exist → becoming `story_threads` is additive, not new.
- Recursive summaries already implemented → the living-thread summary is already there.
- The most impactful fixes (steps 1–3) are small and independently shippable.

### My recommendation
Adopt v2's **model** (thread-primary, brief-as-delta, mandatory dates, Verifier) and **UI** (Home/Overlay/Topic).
Do it as the incremental sequence in §11 — you never stop having a working product. The first three steps fix
the current red lights even if you decided to keep the old UI.

---

## Decision log (what I chose and why)
- **Thread, not brief, as the durable object** — because the brief fragments a story; the topic-blob blurs distinct stories; the thread is the only unit that matches how stories actually evolve.
- **Brief = computed delta, not stored document** — because it makes the home screen free, makes personalization automatic, and deletes the three-representations problem.
- **Threads = a loose linked graph, never a global tree** — small bounded nodes stay coherent; edges keep the narrative alive; a dormant story reignites by **spawning a linked successor**, not by a lifetime timer or one immortal node. Query only local neighborhoods. A global tree collapses at scale.
- **Threads never leave the vector index** — "quiet" is display-only; deletion would break the 50-days-later reconnection. Vectors are cheap; keep them all.
- **Summaries regenerate from facts, not recursively** — repeated `old_summary + delta` rewrites are a telephone game that drifts; regenerating from source facts on view is both drift-free and cheaper.
- **Scope discipline: B2C = rolling-window dedup + light threads; durable linked-graph = B2B** — online event coreference is genuinely hard and worst on broad/long topics; don't make the moonshot load-bearing for consumers. Edges are additive and fail gracefully.
- **Briefer demoted to email-only** — facts are already clean sentences; generating a per-run document adds cost and hallucination risk for no signal gain.
- **event_date mandatory** — it is the load-bearing field for dedup; optional dates are why the moat is currently broken.
- **Verifier added** — cheap, and it's the difference between an $8 consumer toy and a $500 compliance product.
- **One giant story per topic: rejected** — too coarse, destroys signal. Replaced with *a handful of small linked threads per topic.*
- **UI = one surface, radical subtraction** — the first v2 draft was data-model-driven and busy (it surfaced proof-of-value = noise). The real direction is one screen of plain sentences, tap-to-expand context, caught-up as a hero. See `reports/v3-briefing.html`.

---

## Session-2 refinements (locked decisions)

**Verified against live DB (June 10):** `event_date` now 100% → fact-level dedup works and the recurrence case is handled; the residual problems are (a) hallucinated *years* on relative dates, (b) a story-clustering **magnet node** (45% of facts in one 2-year node), (c) relevance leaks. See the project memory for the data.

**Dedup (correctness, load-bearing):** semantic **+ temporal + entities/place**. The arbiter must *use* the already-stored `entities` (and location) in the decision — "two lions, two safaris, same day = different events." This, not the story graph, is what makes dedup trustworthy.

**Events / story graph: PAUSED, not deleted.** Stop assigning to story_nodes and stop `story_summarizer` spend. Safe because dedup is fact-level and needs no story nodes; context comes from the history doc. Keep the code; revisit after a working product exists. Linked-thread graph → B2B/future.

**History doc (context): no-LLM first.** Build a chronological timeline by placing the (already-clean) fact-sentences in date order with **zero LLM**. Evaluate. Only if it reads choppy, add *one* "glue/summary" LLM pass. (Tests whether the spliced-timeline's glue is even needed.)

**Harvester emits `fact` + `context` inline** — one call, few extra output tokens, grounded context → kills the separate briefer on the live path (assemble, don't generate).

**Search = per-(topic × tool) AYR (value ÷ cost).** A bandit per topic over its search tools (RSS/GoogleNews/Tavily/Brave/Exa). Cost term auto-favors free tools when they yield; paid tools must earn their price; routing is topic-specific. Caveats: cold-start (explore all tools first), exploration floor (don't permanently abandon a quiet tool). A **coalescing window** groups the tools past their "ready" cadence into one scan run (between engines, within a topic).

**Article selection refinements (inside MMR, no hard rules):** (1) **domain-diversity penalty** — discount further candidates from a domain already picked, so one outlet can't dominate; (2) **syndication collapse** — near-identical text (>~0.95) across different URLs = same article → keep one, bump a "seen in N outlets" counter; (3) **never process the same article twice.** Threshold discipline: very-high text similarity = syndication (collapse); moderate = independent corroboration (keep → feeds `verified_count`).

**Extraction efficiency: test before committing.** Keep full-article→LLM as default. Write and A/B both the paragraph **pre-filter** (cut tokens) and the **highlight-hybrid** (aim the model); decide on results. Safe token win first: article-level dedup + near-dup skip.

**Cost control — two pools + a budget controller:**
- **Platform pool = shared topics.** Cost = (#shared topics) × frequency, bounded by topic count not user count. Free users add zero marginal cost → structurally cannot overage.
- **Per-user pool = private topics** (paying users). Throttle against the owner's plan budget; one user's overage never touches another.
- **Shared-topic speed** = highest-tier subscriber (existing tier trigger). Paid presence shields a shared topic from throttling.
- **Throttle order when over budget:** free-only shared topics → low aggregate-value shared topics → (protect any shared topic with a paying subscriber) → private topics against their own owner only. Tier-awareness lives at the **topic** level.
- **Budget controller** = feedback loop (predict end-of-period spend → scale a global rate-multiplier with a safety-margin asymptote → never hard-block). Combined with cost-aware AYR, it degrades the *least valuable* updates first.
- **Three topic types:** free-shared (platform pool, unlimited free users) · paid-shared (cost split across paying subscribers — home of the "sale" mechanic) · private (one paying user, full cost).

**Shared-topic "sale" UX — write both, decide at build time:** (a) marketplace — show follower count + per-hour discount on the time-picker, user can shift to a cheaper hour; (b) soft nudge — "most people get this at 7am, join them," cost hidden. Keep the amortization economics in the backend regardless.

**Usage/cost tracking:** per-run actual cost in DB (variable = LLM tokens×price + API calls; fixed = DB/deploy amortized flat — don't attribute CPU per-run). Backend/founder-only bar, not user-facing.
