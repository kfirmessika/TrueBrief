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
| Rate + depth as two axes, shared-scan schedule | §9 |
| Cost monitoring + the budget controller | §10 |
| **Cost & sharing — 3 options** | §11 |
| Shared memory + B2B/API | §12 |
| UI | §13 |
| Business / pricing / positioning | §14 |
| Build sequence | §15 |
| Decisions, red lights, open questions | §16 |

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
├── event_date (date)          ★ MANDATORY + sanity-clamped to [publish−1y, today]
├── importance (float 0–1)     ★ emitted free by harvester; drives ranking
├── confidence (float)
├── verified_count (int)       independent corroborating sources
├── source_url, source_domain
├── first_seen_at

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
2. **Harvester** — reuse, three prompt changes:
   - **`event_date` mandatory**, clamped to `[publish_date − 1y, today]`; "June 7"-type relative dates take the **publish year**. (Fixes the year-hallucination red light.)
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

**Delivery rhythm is a user preference, not a second system:** a *digest hour* (daily "your brief is ready") and a *breaking toggle* (push the moment something high-importance lands). Same engine, same screen — open once/day = digest feel; open often = real-time feel.

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
- **UI = one surface, radical subtraction** (`v3-briefing`).
- **Budget controller = graceful degradation, never hard-block, tier-aware.**

### 🔴 Red lights (from live data — fix regardless)
1. Date *year* hallucination reaches delivered briefs.
2. Story-clustering magnet node (45% of facts in one 2-year node) — paused.
3. Relevance leaks (off-topic facts).

### Open questions
- **Cost model:** lock Option A for launch, commit to Option B's timeline post-telemetry? (§11)
- **Soft/hard thresholds:** exact numbers — calibrate on real cost data.
- **Depth definition:** measure depth-cost by article-count proxy or by measured average cost? (affects attribution + the merge schedule)
- **History doc:** does the no-LLM timeline read well enough, or is the one glue-pass needed? (empirical, post-build)
- **Shared "sale" UX:** marketplace vs. soft nudge — test when there.
