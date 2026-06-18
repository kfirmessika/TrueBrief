# TrueBrief — Execution Plan (ship → test → sell → scale)

> **Principle: you already have a deployed, mostly-working V1. Stop planning. Build the *pipeline diffs that make V3 actually V3* (the whole reason we started: fewer LLM calls + clean dedup), behind flags so V1↔V3 can be measured head-to-head — then validate, sell, and only then build the heavy infra.**
> Rationale: [docs/core/architecture_v3.md](core/architecture_v3.md). This file is the *do* list.

---

## Reality check — what's ALREADY built (don't rebuild)

- ✅ Full pipeline deployed (Railway + Celery + Redis), frontend on Vercel.
- ✅ Auth (Clerk), billing scaffolding (Paddle), shared-topics, scheduling, **existing AYR**, MMR, dual vectors.
- ✅ `event_date` fix landed → dedup already works, recurrence handled.
- ✅ V1 UI is acceptable for launch.

**The gap to sellable = the V3 pipeline diffs + clearing launch blockers. Much of the rest already exists — reuse it.**

---

## What we DEFER (do NOT build now — use what exists)

Per the decision to build only "what makes V3 → V3": these are real, but **not** needed to test V3 or to go live, so they wait.
- ❌ Full cost tracking / prediction / **budget controller** → build only a **light measurement counter** (calls + tokens + $/run) for the A/B. The full system is M4.
- ❌ Per-(topic×tool) AYR + **fast-adaptive AYR** → **use the existing AYR** (slightly tuned at most) for now.
- ❌ Multi-tier billing + cost-model Option B (incremental attribution, soft/hard limits, margin shield) → **one tier (the existing one) is enough to test.**
- ❌ Coalescing window, timing-pattern learning, linked-thread graph, spliced timeline.

---

## M0 — Checkpoint the working product  ✅ (this session)

Tag the current working V1 in git as the rollback point **before** any pipeline change. (Done — see end of this session: tag `v1-working-baseline`, pushed.) Per the save-point rule: always checkpoint + push before significant changes.

---

## M1 — Build the V3 pipeline core (behind feature flags)  ⏱ ~1–2 weeks · the heart of V3

Every change goes behind a **feature flag** (run V1 or V3 per stage by config) so we can (a) A/B the two on the same topics and (b) flip back to V1 instantly if anything regresses. **First task:** add a tiny **measurement counter** — log `{llm_calls, tokens_in, tokens_out, est_cost, facts, duplicates}` per run. This is what makes the A/B real; it's NOT the full cost system.

### 1a. Quality diffs — strict wins (apply + verify, no A/B needed)
These are unambiguously better; verify via DB re-inspection, don't gate on a tradeoff.
| # | Task | Area |
|---|---|---|
| 1a.1 | Date/year guard: `event_date` mandatory, publish-year for relative dates, clamp `[publish−1y, today]`. **+ date the DEVELOPMENT not the background subject; emit `date_basis` (`explicit`/`relative`/`inferred`); carry `published_at` onto the fact** (the second clock) | backend |
| 1a.2 | Relevance gate: drop off-topic facts | backend |
| 1a.3 | Entity-aware dedup: arbiter uses `semantic + temporal + entity/location` | backend |
| 1a.4 | Pause story graph + `story_summarizer`; hide Stories/Insights tabs | backend + small FE |
| 1a.5 | **Development-lag gate** (arch §8B): `lag = published_at − event_date` → small=feed, medium=feed-framed, large→history-test (connects=backfill to history; orphan=suppress + muted-items log). Gate the feed on **development recency, not `first_seen_at`** | backend |

**Gate:** re-run the 2 live topics → no pre-2026 dates in briefs, no magnet node, no off-topic facts, **and no year-old fact shown as a "today" item** (it lands in history or is suppressed — §8B red light #4).

### 1b. Cost diffs — A/B-measured (flag + compare, keep only if quality holds)
These trade cost for a possible quality risk → measure V1 vs V3 with the counter, keep what wins.
| # | Task | A/B question |
|---|---|---|
| 1b.1 | Batch the judge (grey-zone facts in one call) | fewer calls, same decisions? |
| 1b.2 | Batch the harvester *only if* quality holds (else keep 1/article) | tokens/calls vs attribution quality |
| 1b.3 | Article-level + URL dedup before extraction | tokens saved, no facts lost? |
| 1b.4 | Cache QueryBuilder (per topic, not per scan) + gate scans on new content | calls→~0 on quiet scans |
| 1b.5 | Harvester emits `context` inline → remove live-path briefer | cost cut vs output quality (you liked V1 output — verify) |

**Decision rule:** keep a cost diff if it cuts calls/tokens **without** a visible quality drop in the briefs. Track the numbers per change.

---

## M2 — Measure + validate  ⏱ 2–3 weeks (parallel) · the make-or-break

- **A/B (engineering):** run V1 vs V3 on the same set of topics; report call/token/cost reduction + dedup quality. Lock the V3 flags that win.
- **Product validation (business):** put **V3** in front of **10–30 real users** with a genuine tracking pain (founders/analysts/investors/journalists). The one question: *"vs Google News/Feedly on the same topic — noticeably less repetitive?"* → **>60% yes = go.**
- Don't build M4/M5 until this passes.

---

## M3 — Commercialize  ⏱ ~1 week (overlaps M2) · turn on selling

- **Clear blockers:** domain → Resend verify → Paddle merchant setup (keys/prices) → Clerk prod instance.
- Landing rewrite around the pitch; pricing page (Free / Pro $9 / Researcher $39) live.
- Conversion levers ("you saved ~X hours", soft paywall at topic limit).
- First revenue = convert beta lovers to Pro. B2B (compliance) outreach in parallel.

---

## M4 — Scale infra (margins)  ⏱ after validation, before growth

Now build the deferred heavy infra:
- Full per-run cost telemetry → **cost-aware AYR** → **budget controller** (graceful, tier-aware).
- **Fast-adaptive (spike-responsive) AYR**; per-(topic×tool) AYR + coalescer.
- Cost-model **Option B** (incremental attribution + soft/hard limits + margin shield); multi-tier.

## M5+ — Better product

- **UI update — needed** (will rebuild around [reports/v3-briefing.html](../reports/v3-briefing.html); V1 is fine to launch on). **Can be built in parallel during M2's test window** (doesn't collide with pipeline work).
- History doc (no-LLM first), B2B API on the shared ledger, timing-pattern learning (social-pivot moat).

---

## Parallelization (keep moving while tests run)

Testing windows (M2's A/B + 20-user run) are days–weeks. **Program non-colliding work in parallel** so we go live ASAP:
- New UI (M5) — touches frontend, not the pipeline.
- Landing page + pricing copy (M3).
- Clearing launch blockers (M3) — account/infra setup, no code conflict.
- The measurement counter feeds straight into M4's cost telemetry — build it forward-compatible.

---

## Selling points (build M3 around these)

1. **"Stop reading the news. Read a memo about it."** — the memo, not the feed.
2. **It remembers what it already told you** — per-user delta memory; no competitor has it.
3. **The all-caught-up moment** — "we read 124 articles, 3 mattered." Sells *time saved*.
4. **Trustable facts** — atomic facts + dates + sources = a B2B audit trail.
5. **Open-language topics** — track anything in plain English.

**Sell first to** people whose job is tracking things — analysts, investors, founders, journalists, compliance.

---

## One-line order of operations

**Checkpoint V1 (done) → build V3 pipeline diffs behind flags + a measurement counter (M1) → A/B V1↔V3 and put V3 in front of 20 real users (M2) → if it's less repetitive, turn on billing + landing (M3) → only then the heavy cost/AYR infra (M4) and the new UI/features (M5).**

Do **not** build M4/M5 before M2 passes. The most expensive mistake available is polishing infra instead of running the A/B + the 20-user test.
