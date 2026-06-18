# TrueBrief — Task Tracker

> **The single source of truth.** The AI must update this file and commit changes after every step.
> **Legend:** C = Complexity (1-20) | M = Recommended Model

| Model (M) | Use Case |
|---|---|
| **FLASH** | C 1–8: UI, Boilerplate, Docs, Simple Logic |
| **SONNET** | C 9–18: Complex Logic, Auth, Integrations |
| **OPUS** | C 19–20: Architecture, Massive Refactors, Deep Reasoning |

---

## 🚀 LAUNCH PATH — ordered critical path to go-live (added 2026-06-18)

> The single ordered list of what actually has to happen to go live, fastest first.
> Everything else in this file is backlog. Two launch tiers: **Soft** (free, no money, days)
> then **Public/Paid** (needs domain + billing, ~1–2 weeks after soft).

### L0 — Make the live pipeline debuggable (DO FIRST — de-risks everything after)
- [ ] **A.7 Pipeline Observability / Admin Trace Panel** — per-run trace of the *entire* pipeline
      (query+tools chosen & why → articles each tool returned → MMR selection → exact LLM
      prompt/response per stage → per-fact judge decisions). Founder-only. This is the tool that
      makes the soft-launch validation below actually diagnosable. (C: 14 | M: **SONNET**)

### L1 — Soft launch (free tier only — no domain/billing needed)
- [ ] **S1. Enable V3 flags in staging + smoke-scan 3 real topics** — flip V3_DATE_GUARD,
      V3_RELEVANCE_GATE, V3_ENTITY_DEDUP, V3_PAUSE_STORY_GRAPH on Railway; run a scan on each;
      use A.7 to confirm dates/relevance/dedup behave and cost looks right. (C: 6)
- [ ] **S2. Verify model quota** — confirm `gemini-3.1-flash-lite` has real daily quota on the
      prod key (the dev key kept hitting `limit: 0`). Watch llm_call_log for 429s. (C: 3)
- [ ] **S3. Fix stale frontend tests** — `history.test.tsx` + any onboarding refs to deleted
      routes (build/CI must be green before inviting anyone). (C: 4)
- [ ] **S4. Invite 5–10 free users on the bare Vercel/Railway URLs** — everyone free tier,
      no emails, no payments. Watch A.7 + /admin/metrics daily. (C: 2)

### L2 — Public / paid launch (needs the pre-launch blockers below)
- [ ] **P1. Buy domain** → unblocks Resend + Paddle + Clerk prod (see Pre-launch blockers).
- [ ] **P2. Resend:** verify domain, set `DIGEST_FROM_EMAIL=briefs@<domain>`.
- [ ] **P3. Paddle:** finish merchant setup with the live URL; set price/keys; smoke a test checkout.
- [ ] **P4. Clerk:** swap dev instance → production instance.
- [ ] **P5. C.5 Pre-Production Smoke Script** — preflight gate before flipping public.

> **Deferred until after launch** (do NOT block go-live on these): A.2/A.3/A.5 deeper test
> harnesses, B.REF→B.5 UI redesign (current UI ships), Phase 4 B2B API, Phase 5/6.
> The UI is "good enough to ship"; iterate it on real feedback, not before users exist.

---

## V3 Pipeline Migration (execution_plan.md)

### M0 — Checkpoint V1 ✅
### M1 — V3 pipeline diffs behind feature flags
- [x] Switch model gemini-3.1-flash-lite-preview → gemini-2.0-flash-lite (fix quota exhaustion)
- [x] Add 5 V3 feature flags to settings.py (all False = V1 preserved)
- [x] 1a.1 Date/year guard in harvester (V3_DATE_GUARD)
- [x] 1a.2 Relevance gate — drop off-topic facts (V3_RELEVANCE_GATE)
- [x] 1a.3 Entity-aware dedup in arbiter (V3_ENTITY_DEDUP)
- [x] 1a.4 Pause story graph + story_summarizer; hide Stories tab (V3_PAUSE_STORY_GRAPH)
- [ ] 1b.1 Batch grey-zone judge calls (V3_BATCH_JUDGE) — pending M2 measurement
- [ ] 1b.2–1b.5 Other cost diffs — pending M2 A/B results
- [ ] Create Supabase pipeline_run + llm_call_log tables ✅ (done)

### M2 — Measure + validate (A/B + 20-user test) — next
### M3 — Commercialize (billing, landing, domain)
### M4 — Scale infra (after M2 passes)

---

## Phase 0: Project Skeleton ✅
## Phase 1: Core MVP ✅
## Phase 2: Delta Engine + Scheduling ✅

---

## Phase 3: Frontend + Monetization

- [x] 3.1 Story Nodes
- [x] 3.2 Dual vectors
- [x] 3.3 Recursive summary updates
- [x] 3.4 Stripe Integration
- [x] 3.5 Tier Enforcement
- [x] 3.6 Next.js Frontend Skeleton
- [x] 3.7 Auth (Clerk/NextAuth)
- [x] 3.8 Topic Management UI
- [x] 3.9 Brief Display Page
- [x] **3.10 Brief History Page** (C: 5 | M: **FLASH**) — note: standalone history route removed; history is now inline on the topic page. `history.test.tsx` is stale and tests a deleted route.
- [x] 3.11 Landing Page (C: 5 | M: **FLASH**)
- ~~3.12 Onboarding Flow~~ — **CANCELLED** (decided unnecessary for this product)
- [x] 3.13 "Time Saved" Metric (C: 5 | M: **FLASH**)
- [x] 3.14 Public Sharing Pages (C: 10 | M: **SONNET**)
- [x] 3.15 Email Digest (C: 15 | M: **SONNET**)
- [x] 3.16 Web Push Notifications (C: 15 | M: **SONNET**)
- [x] 3.17 Mobile-Responsive Design (C: 8 | M: **FLASH**)
- [x] 3.18 Rate Limiting & Abuse (C: 18 | M: **SONNET**)
- [x] 3.19 Brave Search + Exa (C: 15 | M: **SONNET**)
- [x] **3.20 Deployment — Railway (backend + Celery + Redis) + Vercel (frontend).** (C: 10 | M: **SONNET**)

---

## Pre-launch blockers (need a real domain first)
> - **Resend:** `DIGEST_FROM_EMAIL` must be a verified domain. Buy domain → verify in Resend → set `DIGEST_FROM_EMAIL=briefs@yourdomain.com`
> - **Paddle:** requires a live website URL to complete merchant account setup. Deploy → get domain → finish Paddle setup → set `PADDLE_API_KEY`, `PADDLE_WEBHOOK_SECRET`, `PADDLE_PRICE_PRO`, `PADDLE_PRICE_POWER`
> - **Clerk:** switch from `integral-grackle-67.clerk.accounts.dev` (dev instance) to a production Clerk instance when going public
> - For the test deploy, all three above are skipped — everyone is on free tier, no emails sent

## Phase 3.5: Post-Deployment Validation (A→B→C run against live Railway/Vercel URLs)

> **Decision (2026-05-21):** Deploy first (3.20), then run all validation against the live app.
> Local testing is abandoned — Celery/Redis stops when the PC sleeps, making longitudinal tests impossible.
> All A/B/C tests target the Railway backend URL and Vercel frontend URL.

### Phase A · Backend Validation

- [x] A.1 Cost & Latency Telemetry — pipeline_run + llm_call_log tables, LLMClient instrumentation, /admin/cost-summary (C: 25 | M: **SONNET**)
- [ ] A.2 Accuracy Test Harness — 6 reproducible harnesses (grounding, arbiter P/R, story assign, summary stability, briefer faithfulness, confidence floor) (C: 18 | M: **SONNET**)
- [ ] A.3 Longitudinal Stress Tests — 30-day fast-news sim, slow-burn, topic-overlap — run against Railway so it stays up 24/7 (C: 15 | M: **SONNET**)
- [x] A.4 Failure-Mode Tests — 10 tests covering temporal boundary, story merge creep, orphaned fact, batch mismatch, idempotent schedule, hallucination smoke, rotator starvation, briefer zero alphas (C: 12 | M: **SONNET**)
- [ ] A.5 Competitor Benchmark — head-to-head vs Perplexity / ChatGPT Tasks / Feedly AI (C: 10 | M: **SONNET**)
- [x] A.6 Admin Metrics Dashboard — /admin/metrics endpoint + UI (C: 8 | M: **FLASH**)
- [ ] **A.7 Pipeline Observability / Admin Trace Panel** — `pipeline_trace` table + prompt/response
      capture on `llm_call_log`; `/admin/runs` + `/admin/runs/{id}` endpoints; founder-only run-detail
      UI showing the full per-run pipeline trace (query→tools→articles→MMR→LLM I/O→judge decisions).
      The debugging spine for the soft launch. (C: 14 | M: **SONNET**)

### Phase B · UI/UX Redesign

> **Decision (2026-05-21):** Previous approach (implement design without a validated reference) failed.
> New workflow — 3 mandatory steps before any code is written:
> 1. **Generate** — use Google AI Studio or Claude.ai (claude.ai Projects) to produce HTML/screenshot mockups of the redesigned dashboard and topic detail page. Upload current screenshots, prompt for a Linear/Vercel-style clean dark-first design.
> 2. **Validate** — open the AI-generated HTML in a browser. Iterate prompts until it looks right to the founder.
> 3. **Implement** — bring the approved screenshot/HTML to Claude Code. Implement it 1:1. No guessing.
> Do NOT start B.2–B.5 until Step 1+2 are done and a design reference exists.

- [x] B.0 Design System Foundation — OKLCH tokens, dark mode (next-themes), Framer Motion primitives, Radix UI, EmptyState/Skeleton/ErrorBoundary (C: 15 | M: **SONNET**)
- [x] B.1 Critical Gaps — Topic Detail (Briefs/Stories tabs + inline scan button + live scan progress bar), Settings (account/billing/danger zone), topic thread with source chips + tooltips (C: 18 | M: **SONNET**)
- [ ] **B.REF Design Reference** — founder generates mockups via Google AI Studio / Claude.ai, validates visually, brings approved reference here (C: 0 | founder task, not AI)
- [ ] B.2 New Surfaces — Story Node timeline view, AYR insight panel, Query variants panel, Command palette, Notification inbox — implement against B.REF. *(Real-time scan progress already done in B.1.)* (C: 18 | M: **SONNET**)
- [ ] B.3 Polish Layer — Optimistic mutations, page transitions, OG images — implement against B.REF (C: 8 | M: **FLASH**)
- [ ] B.4 Copy & Brand — Empty states, onboarding interstitial, landing rewrite (C: 5 | M: **FLASH**)
- [ ] B.5 Accessibility & Mobile — axe-core, ARIA, focus traps, reduced-motion, touch targets (C: 8 | M: **FLASH**)

### Phase C · Integration & E2E Testing

- [ ] C.1 Playwright E2E Suite — 8 critical user journeys (C: 15 | M: **SONNET**)
- [ ] C.2 API Contract Tests — openapi-typescript generated types, no `any` (C: 8 | M: **FLASH**)
- [ ] C.3 Performance Budget — LCP, TTFB, bundle size, cold scan p95 (C: 5 | M: **FLASH**)
- [ ] C.4 Load & Stress — k6 concurrent users + Celery, Redis outage drill (C: 10 | M: **SONNET**)
- [ ] C.5 Pre-Production Smoke Script — preflight.sh gating deployment (C: 5 | M: **FLASH**)

---

## Phase 4: B2B API

- [ ] 4.1 Public REST API + Auth (C: 15 | M: **SONNET**)
- [ ] 4.2 Polished API Docs (C: 5 | M: **FLASH**)
- [ ] 4.3 GET /delta Endpoint (C: 12 | M: **SONNET**)
- [ ] 4.4 GET /nodes Endpoint (C: 12 | M: **SONNET**)
- [ ] 4.5 POST /webhooks (C: 15 | M: **SONNET**)
- [ ] 4.6 Usage Tracking & Billing (C: 20 | M: **OPUS**)
- [ ] 4.7 Webhook Delivery Engine (C: 18 | M: **SONNET**)
- [ ] 4.8 Admin Dashboard (C: 12 | M: **SONNET**)
- [ ] 4.9 Rate Limits by Tier (C: 12 | M: **SONNET**)
- [ ] 4.10 API Versioning (C: 10 | M: **SONNET**)

---

## Phase 5: Scale + Moat

- [ ] 5.1 Plugin Architecture (C: 18 | M: **SONNET**)
- [ ] 5.2 Global AYR Network (C: 15 | M: **SONNET**)
- [ ] 5.3 User Feedback Loop (C: 10 | M: **SONNET**)
- [ ] 5.4 Contradiction Detection (C: 20 | M: **OPUS**)
- [ ] 5.5 Multi-Language Support (C: 12 | M: **SONNET**)
- [ ] 5.6 Specialized Source Plugins (C: 15 | M: **SONNET**)
- [ ] 5.7 Team / Org Accounts (C: 18 | M: **SONNET**)
- [ ] 5.8 White-Label B2B UI (C: 15 | M: **SONNET**)
- [ ] 5.9 Mobile App (RN) (C: 20 | M: **OPUS**)

---

## Phase 6: Domain Intelligence Pipelines

- [ ] 6.1 Domain Router Brain (C: 20 | M: **OPUS**)
- [ ] 6.2 Finance Pipeline (C: 20 | M: **OPUS**)
- [ ] 6.3 Legal Pipeline (C: 20 | M: **OPUS**)
- [ ] 6.4 Medical Pipeline (C: 20 | M: **OPUS**)
- [ ] 6.5 Fine-Tuned Local Router (C: 18 | M: **SONNET**)
- [ ] 6.6 System-Wide Feedback (C: 15 | M: **SONNET**)
