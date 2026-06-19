# TrueBrief — Roadmap (single source of truth)

> Rewritten 2026-06-19. The AI updates this file and commits after every step.
> **Legend:** C = Complexity (1–20) · M = Recommended model · `[x]` done · `[~]` partial · `[ ]` todo
>
> | Model | Use case |
> |---|---|
> | **FLASH** | C 1–8: UI, boilerplate, docs, simple logic |
> | **SONNET** | C 9–18: complex logic, auth, integrations |
> | **OPUS** | C 19–20: architecture, massive refactors, deep reasoning |

---

## 0. Where we are today (honest snapshot)

A working news-intelligence app: create topics → scheduled scans collect articles → harvester
extracts atomic facts → arbiter dedups (NEW/UPDATE/DUPLICATE) → briefs render on the topic page.
Auth (Clerk), billing scaffolding (Paddle), email digest, web push, rate limiting, and deployment
(Railway + Vercel) all exist. The V3 quality/cost migration (M1) is done **behind feature flags**.

**What works in the product right now:** dashboard feed, sidebar topic list, topic page with
briefs (🆕 NEW / 📈 UPDATES envelope), source chips, live scan progress, settings, admin metrics +
**full per-run pipeline trace** (`/admin/runs`).

**Built but gated/blocked:** V3 quality flags (ON locally, **OFF in Railway**); batch judge
(`V3_BATCH_JUDGE`, off, pending A/B); email digest (built, blocked on a verified domain).

**Designed & agreed but NOT built** (see §4 — they all sit on the delta engine):
the per-user **delta engine**, the **smart history page**, the **calm v3-briefing surface**, and the
**in-app daily digest**.

**The plan in one line:** soft-launch the current app to free users → watch the pipeline via the
admin trace → then build the **delta engine**, which unlocks the history page, the calm brief
surface, and the daily digest — in that dependency order.

---

## 1. 🚀 LAUNCH PATH — the ordered critical path to go live

> Two tiers: **Soft** (free, no money, days) then **Public/Paid** (needs domain + billing).
> Everything in §4+ is *after* this. Don't block go-live on it.

### L0 — Make the live pipeline debuggable ✅ DONE (de-risks everything after)
- [x] **A.7 Pipeline Observability / Admin Trace Panel** — per-run trace of the whole pipeline
      (query+tools chosen & why → articles each tool returned → MMR selection → exact LLM
      prompt/response per stage → per-fact judge decisions). Founder-only `/admin/runs/{id}`.
      Migration 012 applied to Supabase 2026-06-18.

### L1 — Soft launch (free tier only — no domain/billing needed)
- [ ] **S0. Push backend to Railway** — deploy current `main` so prod runs the new model
      (gemini-3.1-flash-lite), UCB1 rotator, A.7 trace capture, and batch-judge code. (C: 2)
- [ ] **S1. Flip V3 flags ON in Railway env** — `V3_DATE_GUARD`, `V3_RELEVANCE_GATE`,
      `V3_ENTITY_DEDUP`, `V3_PAUSE_STORY_GRAPH` (they're already ON locally, still False in prod). (C: 1)
- [ ] **S2. Verify model quota on prod key** — confirm `gemini-3.1-flash-lite` has real daily
      quota. **CONFIRMED BLOCKER (smoke test 2026-06-19):** dev key batch-embed returns 1 vector for
      any N inputs → MMR falls back → relevance gate over-fires (dropped 14/15 facts in one scan).
      Briefs still produce but quality is unreliable. Must verify prod key before deploy. (C: 3)
- [ ] **S3. Smoke-scan 3 real topics** — run each, open `/admin/runs` to confirm dates / relevance
      gate / dedup behave and cost looks right. Gate with `python scripts/preflight.py --base-url …`. (C: 4)
- [x] **S4. Frontend CI green** — removed stale `topics.intg`/`briefs.intg` suites + fixed drifted
      assertions. 16/16 tests pass, `npm run build` PASS. (done 2026-06-19)
- [ ] **S5. Invite 5–10 free users** on the bare Vercel/Railway URLs — everyone free tier, no
      emails, no payments. Watch `/admin/runs` + `/admin/metrics` daily. (C: 2)

### L2 — Public / paid launch (needs the pre-launch blockers in §6)
- [ ] **P1. Buy domain** → unblocks Resend + Paddle + Clerk prod.
- [ ] **P2. Resend:** verify domain, set `DIGEST_FROM_EMAIL=briefs@<domain>`.
- [ ] **P3. Paddle:** finish merchant setup with the live URL; set price/keys; smoke a test checkout.
- [ ] **P4. Clerk:** swap dev instance → production instance.
- [x] **P5. Pre-Production Smoke Gate** — `scripts/preflight.py` (secrets, no `-preview` model,
      Supabase, **migration 012 applied**, `/health` + public API). Exit 1 blocks launch.

---

## 2. V3 Pipeline Migration (M1 quality/cost diffs)

> Architecture build-sequence steps 1–7. Flags default **False** = V1 preserved; flip per-flag after A/B.

- [x] Switch model → `gemini-3.1-flash-lite` (stable; fixes the daily-quota=0 trap)
- [x] 1a.1 Date/year guard in harvester (`V3_DATE_GUARD`)
- [x] 1a.2 Relevance gate — drop off-topic facts (`V3_RELEVANCE_GATE`)
- [x] 1a.3 Entity-aware dedup in arbiter (`V3_ENTITY_DEDUP`)
- [x] 1a.4 Pause story graph + summarizer; hide Stories tab (`V3_PAUSE_STORY_GRAPH`)
- [x] UCB1 query rotator — 1 lifetime LLM call/topic, cached in `topics.search_strategy`
- [x] 1b.1 Batch grey-zone judge (`V3_BATCH_JUDGE`) — `judge.call_batch()` + `arbiter.judge_alphas()`,
      off by default; enable after M2 A/B confirms quality
- [ ] **1a.5 Two-clock dev-lag gate** (`published_at` on the fact + `date_basis` + lag classifier) —
      §8B. Decides "breaking" vs "framed" vs "history backfill". **Prereq for the smart history page.** (C: 10 | SONNET)
- [x] **1b.2 URL/article dedup** — exact-URL skip (14d window in `VectorStore.get_seen_urls()`) +
      near-dup/syndication collapse (`V3_NEARDUP_COLLAPSE`): SimHash-64 / Hamming≤3 drops wire-story
      copies before extraction. 6 unit tests; wired in `runner.py` step 2c.
- [ ] 1b.3 Gate scans on new content (quiet-scan = $0) (C: 6 | FLASH)
- [ ] 1b.4 Drop the live-path briefer — assemble from `fact`+`context` (folds into §4-C below) (C: 8 | SONNET)

### M2 — Measure + validate (the gate before building more)
- [ ] **A.2 Accuracy Test Harness** — golden set; CI report on gate recall, scoring precision/recall,
      digest precision@5 (north-star ≥ 80%). Treat scoring quality as the product. (C: 18 | SONNET)
- [ ] A/B the V3 flags on real scans — call count / tokens / cost / dedup quality vs V1 baseline,
      read from `pipeline_run` + `llm_call_log` via `/admin/metrics`. (C: 6)

---

## 3. ✅ DONE (collapsed)

- **Phase 0–2:** project skeleton, core MVP, delta-engine-v1 + scheduling.
- **Phase 3 (frontend + monetization):** 3.1–3.20 done — story nodes, dual vectors, Stripe→Paddle,
  tier enforcement, Next.js skeleton, Clerk auth, topic mgmt UI, brief display, landing, time-saved
  metric, public sharing, email digest, web push, mobile-responsive, rate limiting, Brave+Exa,
  Railway+Vercel deploy. (3.10 standalone history route **removed** — history is inline now.
  3.12 onboarding **cancelled** — decided unnecessary.)
- **Phase A (backend validation):** A.1 cost/latency telemetry, A.4 failure-mode tests,
  A.6 admin metrics, **A.7 trace panel**.
- **Phase B (design system):** B.0 OKLCH tokens + dark mode + primitives, B.1 critical gaps
  (topic detail tabs, settings, source chips, live scan bar).
- **Ops:** migration 012 applied; `scripts/preflight.py` launch gate; frontend CI green;
  **E2E smoke harness** (`scripts/smoke_scan.py`) + **test plan** (`docs/testing.md`) built;
  real scan on 2 prod topics passed all 7 quality invariants (2026-06-19).

---

## 4. POST-LAUNCH PRODUCT SURFACES — the history page, calm brief, and daily digest

> **This is the answer to "are we moving to the history page / briefs / daily summary yet?":**
> the design for all three is **agreed and locked** in the architecture, but none are built — and
> they share one foundation. Build them in this dependency order, **after the soft launch** validates
> the pipeline. Maps to architecture build-sequence #8–11.

### 4-A. Delta engine + `user_topic_state` — THE UNLOCK (build-seq #10) [START HERE post-launch]
- [ ] `user_topic_state` table with two markers: `last_seen_at` (live) + `last_digest_at` (digest).
- [ ] Per-user **delta query** — Home = "what's new for *this* user since their anchor", **$0 LLM**,
      pure Postgres; advance `last_seen_at` on view. "All quiet" is a first-class hero state.
- [ ] **Gate the feed on development recency, not `first_seen_at`** (needs 1a.5) — a fact dated a year
      ago but first-seen today belongs in history, not at the top of today.
      (C: 16 | SONNET) — *history, briefs, and digest all sit on this.*

### 4-B. Smart history page (build-seq #9 + §8B backfill)
- [ ] **No-LLM-first timeline** — render the topic's "story so far" by ordering the already-clean
      fact-sentences chronologically, **zero LLM**. Evaluate readability; add *one* glue/summary pass
      only if choppy.
- [ ] **Backfill-of-misses (§8B):** a large-lag fact that *connects* to the existing timeline
      (entity overlap / known thread / corroborated) is written to history silently and surfaced in
      the feed only as "filling a gap — Mar 2025", never as breaking. Orphans → muted-items log.
- [ ] UI: "tap a story → story-so-far expands in place" (not a separate route); full timeline is the
      power/B2B view. (C: 15 | SONNET) — *depends on 4-A + 1a.5.*

### 4-C. Calm v3-briefing surface + kill the live briefer (build-seq #4, roadmap B.REF→B.2)
- [ ] **B.REF Design reference** — founder generates/validates the mockup (Google AI Studio / Claude.ai),
      brings the approved reference here. *(Founder task — gates the code below.)*
- [ ] Implement the radically-subtracted home: `● 3 new today`, plain sentences, inline `context` on
      tap, "All caught up." hero state. Kill: Stories tab, stat bars, chat-bubble feed.
- [ ] **Assemble briefs from `fact`+`context`** instead of regenerating (drops the live-path briefer →
      cheaper). (C: 18 | SONNET) — *depends on 4-A; reads best with 4-B.*

### 4-D. Daily digest envelope (build-seq #11)
- [ ] **One feed, two envelopes** — the "daily summary" is NOT a second screen: same delta feed,
      digest header ceremony (`Your brief · Tue Jun 16`, grouped by topic, "That's everything"),
      auto-picked by time-since-last-look using `last_digest_at`.
- [ ] In-app dated digest card + a *digest hour* preference + a *breaking toggle* (push on
      high-importance). Email digest already exists — wire it to the same engine. (C: 12 | SONNET)
      — *depends on 4-A; email delivery still needs the domain (§6).*

### 4-E. Adaptive scanning & cost control (build-seq #8, 13)
- [ ] Spike-responsive AYR (snap up on surprise, decay gently) + per-(topic×tool) AYR + coalescing
      window. (C: 18 | SONNET)
- [ ] Budget controller (once telemetry can predict) + soft/hard limits + margin shield. (C: 15 | SONNET)
- [ ] Trust UX: viewable muted-items log ("212 items muted — view"). (C: 5 | FLASH)

---

## 5. Later / at scale (do NOT block go-live)

- **Phase B.3–B.5:** polish (optimistic mutations, transitions, OG images), copy/brand, a11y + mobile.
- **Phase C:** C.1 Playwright E2E, C.2 API contract types, C.3 perf budget, C.4 load/stress.
- **Phase A deferred:** A.3 longitudinal stress sims, A.5 competitor benchmark.
- **Phase 4 — B2B API:** public REST + auth, `/delta`, `/nodes`, webhooks, usage billing, versioning.
  (Architecture says B2B over-indexes vs B2C — the real money. Compliance/regulatory wedge first.)
- **Phase 5 — scale + moat:** plugins, global AYR network, feedback loop (Rocchio + learned
  pre-filter), contradiction detection, multi-language, teams/org, white-label, mobile app.
- **Phase 6 — domain pipelines:** domain router brain, finance/legal/medical pipelines.
- **Build-seq #14–15:** timing/pattern scan learning (the social-pivot moat); spliced timeline +
  un-paused linked-thread graph for B2B.

---

## 6. Pre-launch blockers (need a real domain first)

> For the **soft** launch all three are skipped — everyone is free tier, no emails, no payments.
> They gate only the **paid/public** launch (L2).

- **Resend:** `DIGEST_FROM_EMAIL` must be a verified domain → buy domain → verify → set it.
- **Paddle:** needs a live website URL to finish merchant setup → set `PADDLE_API_KEY`,
  `PADDLE_WEBHOOK_SECRET`, `PADDLE_PRICE_PRO`, `PADDLE_PRICE_POWER`.
- **Clerk:** switch dev instance (`integral-grackle-67…`) → production instance.

---

## 7. Locked decisions & red lights (from the architecture)

- **One surface, radical subtraction** — the brief *is* the home feed; topics are a filter, not a
  sidebar of dots. "All caught up" is a hero state.
- **"New to us" ≠ "new to the world"** (red light, verified live) — the feed must gate on development
  recency (§8B / 1a.5), not `first_seen_at`. This is the single biggest quality leak.
- **Story graph stays paused** — keep the code, stop the spend; revisit only for B2B, and only as a
  loose locally-queried graph, never a global tree, never load-bearing for dedup.
- **Briefer is removed from the live path** — assemble `fact`+`context`; keep generation only for the
  polished email digest.
- **Model choice always lives in `settings`/`LLMClient`** — never hardcoded. Run on Gemini Flash, not
  Claude (cost at per-scan volume).
- **North-star: precision@5 ≥ 80%** — below ~60% churn is guaranteed regardless of UI; build A.2 first.
