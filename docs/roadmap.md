# TrueBrief — Task Tracker

> **The single source of truth.** The AI must update this file and commit changes after every step.
> **Legend:** C = Complexity (1-20) | M = Recommended Model

| Model (M) | Use Case |
|---|---|
| **FLASH** | C 1–8: UI, Boilerplate, Docs, Simple Logic |
| **SONNET** | C 9–18: Complex Logic, Auth, Integrations |
| **OPUS** | C 19–20: Architecture, Massive Refactors, Deep Reasoning |

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
- [x] **3.10 Brief History Page** (C: 5 | M: **FLASH**)
- [x] 3.11 Landing Page (C: 5 | M: **FLASH**)
- [x] 3.12 Onboarding Flow (C: 12 | M: **SONNET**)
- [x] 3.13 "Time Saved" Metric (C: 5 | M: **FLASH**)
- [x] 3.14 Public Sharing Pages (C: 10 | M: **SONNET**)
- [x] 3.15 Email Digest (C: 15 | M: **SONNET**) ← NEXT
- [x] 3.16 Web Push Notifications (C: 15 | M: **SONNET**)
- [x] 3.17 Mobile-Responsive Design (C: 8 | M: **FLASH**)
- [x] 3.18 Rate Limiting & Abuse (C: 18 | M: **SONNET**)
- [x] 3.19 Brave Search + Exa (C: 15 | M: **SONNET**)
- [x] 3.20 Deployment (C: 10 | M: **SONNET**)

---

## Phase 3.5: Pre-Deployment (A→B→C before 3.20)

### Phase A · Backend Validation

- [x] A.1 Cost & Latency Telemetry — pipeline_run + llm_call_log tables, LLMClient instrumentation, /admin/cost-summary (C: 25 | M: **SONNET**)
- [ ] A.2 Accuracy Test Harness — 6 reproducible harnesses (grounding, arbiter P/R, story assign, summary stability, briefer faithfulness, confidence floor) (C: 18 | M: **SONNET**)
- [ ] A.3 Longitudinal Stress Tests — 30-day fast-news sim, slow-burn, topic-overlap (C: 15 | M: **SONNET**)
- [x] A.4 Failure-Mode Tests — 10 tests covering temporal boundary, story merge creep, orphaned fact, batch mismatch, idempotent schedule, hallucination smoke, rotator starvation, briefer zero alphas (C: 12 | M: **SONNET**)
- [ ] A.5 Competitor Benchmark — head-to-head vs Perplexity / ChatGPT Tasks / Feedly AI (C: 10 | M: **SONNET**) ← run post-deploy
- [ ] A.6 Admin Metrics Dashboard — /admin/metrics endpoint + UI (C: 8 | M: **FLASH**)

### Phase B · Premium UI/UX

- [x] B.0 Design System Foundation — OKLCH tokens, dark mode (next-themes), Framer Motion primitives, Radix UI, EmptyState/Skeleton/ErrorBoundary (C: 15 | M: **SONNET**)
- [x] B.1 Critical Gaps — Topic Detail (3-tab: Briefs/Stories/Insights + live scan button), Settings (account/billing/notifications/danger zone), ScanButton with polling (C: 18 | M: **SONNET**)
- [ ] B.2 New Surfaces — Story Node timeline, AYR insight, Query variants panel, Real-time scan progress, Command palette, Notification inbox (C: 20 | M: **SONNET**)
- [ ] B.3 Polish Layer — Skeletons, optimistic mutations, page transitions, confetti, OG images (C: 10 | M: **FLASH**)
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
