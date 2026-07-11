# TrueBrief — Business Plan (unit economics → pricing → go-to-market)

*Written 2026-07-11 from MEASURED production data (`llm_call_log`, last 7 days) and
provider prices verified the same day. Companion doc: `PRODUCT_PLAN.md` (what's built).
Currency: USD for pricing (global SaaS standard); your books stay in ILS.*

---

## 1. What it actually costs to run (measured, not guessed)

### Variable cost per scan

Measured from `llm_call_log` (1,000-call sample, Jul 4–9): the **harvester is >90% of
all LLM tokens** — ~2,650 input + ~290 output tokens per article read, ~12 articles per
busy scan. Everything else (arbiter, scorer, query builder) is noise in comparison.

| Component | Per BUSY scan | Source of number |
|---|---|---|
| LLM — harvest+arbitrate+score (~33k in / 4k out) | **~$0.014** | measured tokens × Gemini 3.1 flash-lite ($0.25/M in, $1.50/M out) |
| Same on Gemini 2.5 flash-lite ($0.10/$0.40) | ~$0.005 | cheaper fallback if 3.1 price bites |
| Same on Groq llama-3.1-8b ($0.05/$0.08) | ~$0.002 | cheapest, quality must be re-validated per stage |
| Search APIs (~6 queries × Tavily $0.008) | **~$0.048** | Tavily PAYG; free 1k credits/mo covers early usage |
| **Total, busy scan** | **~$0.06** | |
| Quiet scan (no new URLs → harvest skipped) | ~$0.005–0.01 | search queries only — the common case |

**The surprise: search credits cost 3–5× the LLM.** Cost control = fewer/smarter search
calls (RSS-first, AYR throttling, shared scans), not cheaper models.

### Per topic, per month

| Cadence | Busy-scan share (est. 20%) | Cost/topic-month |
|---|---|---|
| Daily (FREE) | 1 scan/day | **~$0.5–0.7** |
| Hourly (PRO) | 24 scans/day | **~$10–13 worst-case; ~$4–6 typical** (AYR + quiet skips) |
| 15-min (POWER) | 96 scans/day | **~$40+ worst-case** — must be capped by fair-use |

Shared topics divide these costs across every subscriber of the same topic — the
architecture's core economic moat. Two PRO users on "Iran war" = one pipeline bill.

### Fixed monthly (verify exact numbers at signup)
Railway ~$5–20 · Supabase Pro $25 · Clerk free tier to 10k MAU · Tavily $30 (4k credits)
when free tier is outgrown · Groq Dev tier ~$1–3. **Call it ~$60–80/mo at first revenue.**

---

## 2. Pricing, margins, and the caps that protect them

Paddle (merchant of record) takes **5% + $0.50/transaction** (effective ~7% globally).

| Tier | Price | Net after Paddle | Realistic COGS | Margin | Worst case |
|---|---|---|---|---|---|
| FREE | $0 | — | ~$1–1.5 (2 daily topics) | acquisition cost | fine |
| PRO | $19 | ~$17.55 | 3–5 typical topics ≈ $12–30… | **positive only with fair-use** | 15 hot hourly topics ≈ $150 → deep loss |
| POWER | $49 | ~$45.05 | similar shape, bigger | positive with caps | unlimited 15-min = unbounded |

**Decision needed (recommended now):**
1. **Fair-use scan budget per tier** — PRO ≈ 2,000 full-scan-equivalents/mo, POWER ≈
   8,000; over budget → scans degrade to daily cadence (never hard-block). This is
   architecture §11 option B's "margin shield" — implement before real users, it's a
   day of work on the scheduler.
2. **Shared-first topic economics** — public/shared topics stay cheap; PRO "private
   topics" are the expensive good. That's already the tier design — keep it.
3. Keep $19/$49. Feedly Pro+ is ~$12 for feeds-without-memory; market-intelligence
   tools are hundreds/mo. $19 for "never re-read the same story + evidence" is a fair
   wedge; don't price up until conversion data exists.

### Break-even
Fixed ~$80/mo → **~6 PRO subscribers** (or 2 POWER + 1 PRO) covers infrastructure.
25 PRO + 5 POWER ≈ $720/mo gross → ~$600 net after Paddle & COGS at typical usage.
That's a believable 3-month post-launch target from design partners + one niche.

---

## 3. Do we beat the alternatives? (honest read)

| Alternative | What it does | Where TrueBrief wins | Where it wins |
|---|---|---|---|
| **Gemini scheduled actions / ChatGPT tasks** | Daily "summarize news about X" push | **No memory** — re-tells the same stories daily; no dedup vs what YOU read; no evidence trail; can't do 15-min cadence | Free/bundled, zero setup, good prose |
| **Google Alerts** | Keyword email | No synthesis, no dedup, keyword-brittle | Free, trusted |
| **Feedly Pro/AI** | Feed reader + AI tagging | Feeds ≠ facts; you still read everything | Mature, integrations |
| **Perplexity** | Ask-when-you-want | Pull, not push; no per-user seen-state | Great ad-hoc research |

The defensible claim: **per-user delivered-fact memory** ("we know what you've already
seen and never repeat it") + per-fact source evidence + configurable cadence. Nobody in
the consumer tier does the memory part.

**Honest scorecard status (as of 2026-07-11):** the last completed judge run
(2026-07-05, `docs/benchmarks/`) had TrueBrief **losing 17–36** to the Gemini+Search
reference — bad lede, missing Hormuz stories, Lebanon false positives. Every named
cause was specifically fixed on 07-07 (SignalScorer 70b killed exactly those false
positives live; breaking-news fan-out captured the flagged Hormuz story at 10/10 within
the hour; dated queries + MAX_K 32 for coverage). The post-fix re-run — the number that
decides "sellable" — is **blocked on search quota**: the 07-11 attempt died with Tavily
AND Brave both over their free limits. Re-run it the day the paid search tier is on.
Until that scorecard flips, do not claim "better than Gemini" anywhere public — claim
the memory/evidence mechanism, which is true regardless.

## 4. Hybrid: our pipeline + Gemini Search (gap-fill & verification)

Gemini 3.x grounding pricing makes this cheap now: **5,000 grounded prompts/month
FREE**, then $14/1k. Design (build post-launch-gate, ~2–3 days):

1. **Coverage net (per topic, 1×/day, not per scan):** grounded flash-lite prompt —
   "top developments for <topic> in the last 24h" → embed-match against our stored
   facts → any unmatched development triggers ONE targeted collect. Cost: 1 grounded
   prompt/topic/day → free under 5k/mo up to ~160 topics.
2. **Verification stamp (high-stakes facts only):** STATE_CHANGE facts above a salience
   bar get one grounded cross-check → `verified` badge in UI/API. This becomes a PRO/API
   selling point ("evidence-checked facts").
3. Never let grounding COMPOSE the brief (that's the moat — our memory), only audit it.

This directly converts the judge that already beats us up in benchmarks into a
production safety net.

## 5. Exactly how to start selling (the next 14 days)

**Days 1–2 — turn the machine on (all user actions, see BACKLOG):**
apply migration 026 → Paddle live prices + env vars → `git push` deploy → Groq Dev tier
→ **Tavily paid plan ($30/mo) — both Tavily and Brave free tiers are ALREADY exhausted
as of 2026-07-11; scans are running degraded and the benchmark can't run** → verify one
real checkout with your own card.

**Days 3–9 — the 7-day launch gate (PRODUCT_PLAN.md):** scheduler runs unattended on
3+ topics; judge MISSING ≤2, noise ≈0; zero garbage rows. Fix what breaks. Do NOT sell
before this passes — one broken week of briefs burns a design partner permanently.

**Days 10–14 — first 10 design partners:**
- Pick ONE niche you can reach personally (e.g., Israeli tech/defense analysts,
  crypto desks, indie PMs tracking competitors). One niche = comparable feedback.
- Offer: free PRO for 30 days in exchange for a 15-minute weekly call. In writing.
- Your pitch is the mechanism, not adjectives: *"It read 300 articles about your topic
  this week. 12 mattered. Here they are, with sources. It will never show you the same
  story twice."* Show THEIR topic live in the first call.
- Success metric to ask for explicitly: "did you stop checking other news sources for
  this topic?" ≥6/10 yes → start charging (they convert at $19 or churn with reasons).
- Capture every "it missed X / it repeated Y" as a benchmark case.

**Revenue expectations, honest version:** month 1: $0 (partners). Month 2–3: 5–15 paid
($95–285/mo). The B2B/API stream (one $500–2k/mo enterprise feed deal via the
/developers page + personal outreach) is what changes the slope — treat every partner
org as an enterprise lead.

## 6. Kill criteria & risks

- **Kill/pivot signal:** if <40% of design partners report "stopped checking elsewhere"
  after 30 days of clean operation → the wedge isn't strong enough as a consumer
  subscription; pivot the same engine to the API/B2B feed (where dedup+evidence is
  valued more and paid better).
- **Cost blowout risk:** search credits at scale — mitigate with fair-use caps (§2),
  RSS-first collection, and shared topics. Watch `llm_call_log` + Tavily dashboard weekly.
- **Platform risk:** Gemini/OpenAI ship per-user news memory natively → moat shrinks;
  speed of niche ownership is the defense.
- **Quota fragility (today):** free tiers die mid-day. The $5/mo of paid tiers is the
  single highest-ROI spend in this document.

---
*Price sources (verified 2026-07-11): Gemini flash-lite & grounding — [ai.google.dev pricing](https://ai.google.dev/gemini-api/docs/pricing), [google-search grounding](https://ai.google.dev/gemini-api/docs/google-search); Groq — [groq.com/pricing](https://groq.com/pricing); Paddle — [paddle.com/pricing](https://www.paddle.com/pricing); Tavily — [tavily.com/pricing](https://www.tavily.com/pricing), [docs.tavily.com/api-credits](https://docs.tavily.com/documentation/api-credits).*
