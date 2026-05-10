# 🛰️ TrueBrief Execution Plan (Run-Based)
> **Format:** Tasks grouped into Execution Runs by Model + shared file context.
> FLASH runs cost $0 — context grouping is a quality hint, not a hard constraint.
> Source of truth for order-of-operations. Status tracked in `docs/roadmap.md`.

---

## ⛓️ Dependency Order (must respect across all runs)
- 3.5 → 3.4 | 3.8 → 3.7 | 3.14/3.15/3.16 → 3.6
- 4.7 → 4.5 | 4.6 → 4.3
- 5.2 → 5.1 | 5.7 → 3.7
- 6.1 → 5.1 | 6.2/6.3/6.4 → 6.1 | 6.5 → 6.1 | 6.6 → 5.3

---

## PHASE 3 — PLAN Runs

### RUN 01 — Model: OPUS
**Context:** `src/truebrief/billing/stripe_client.py`, `billing/webhooks.py`
**Tasks:**
1. **3.4 Plan** — Stripe Integration
**Goal:** Design checkout, webhook handler, and subscription lifecycle before any code.

---

### RUN 02 — Model: SONNET
**Context:** `src/truebrief/billing/tiers.py`, `api/auth.py`, `api/routes.py`, `models/`
**Tasks:**
1. **3.5 Plan** — Tier Enforcement
2. **3.7 Plan** — Auth (Clerk + JWT backend verification)
**Goal:** Design the user auth → tier → enforcement chain end-to-end.

---

### RUN 03 — Model: SONNET
**Context:** `src/truebrief/tasks/email.py`, `tasks/push.py`, `frontend/public/sw.js`
**Tasks:**
1. **3.15 Plan** — Email Digest
2. **3.16 Plan** — Web Push Notifications
**Goal:** Design both async delivery channels — shared Celery task pattern.

---

### RUN 04 — Model: SONNET
**Context:** `api/routes.py`, `frontend/pages/share/`, `src/truebrief/tasks/`
**Tasks:**
1. **3.12 Plan** — Onboarding Flow
2. **3.14 Plan** — Public Sharing Pages
**Goal:** Design first-user experience and viral sharing surface.

---

### RUN 05 — Model: GEM-PRO
**Context:** `src/truebrief/api/middleware.py`
**Tasks:**
1. **3.18 Plan** — Rate Limiting & Abuse Prevention
**Goal:** Design rate limit algorithm, Redis counters, and tier-aware enforcement math.

---

### RUN 06 — Model: SONNET
**Context:** `src/truebrief/collector/brave_layer.py`, `collector/exa_layer.py`, `config/routing_rules.yaml`
**Tasks:**
1. **3.19 Plan** — Brave Search + Exa Plugins
**Goal:** Design source plugin interface + routing config for Phase 3+ sources.

---

### RUN 07 — Model: GEM-PRO
**Context:** `frontend/pages/topics/`, `frontend/components/BriefBlock.tsx`
**Tasks:**
1. **3.9 Plan** — Brief Display Page
2. **3.17 Plan** — Mobile-Responsive Design
**Goal:** Design the visual layout for the core product UI and responsive breakpoints.

---

### RUN 08 — Model: FLASH
**Context:** `frontend/`, `config/`, `railway.toml`, `Dockerfile`
**Tasks:**
1. **3.6 Plan** — Next.js Skeleton
2. **3.8 Plan** — Topic Management UI
3. **3.10 Plan** — Brief History Page
4. **3.11 Plan** — Landing Page
5. **3.13 Plan** — Time Saved Metric
6. **3.20 Plan** — Deployment (Vercel + Railway)
**Goal:** Scaffold all remaining frontend pages and DevOps config.

---

## PHASE 3 — BUILD Runs (all FLASH)

### RUN 09 — Model: FLASH
**Context:** `src/truebrief/billing/`, `src/truebrief/api/auth.py`, `src/truebrief/api/routes.py`
**Tasks:**
1. **3.4 Build** — Stripe Integration
2. **3.5 Build** — Tier Enforcement
3. **3.7 Build** — Auth (Clerk backend)
**Goal:** Wire payments, tier limits, and JWT verification into the backend.

---

### RUN 10 — Model: FLASH
**Context:** `frontend/pages/`, `frontend/components/`, `frontend/lib/`
**Tasks:**
1. **3.6 Build** — Next.js Skeleton
2. **3.8 Build** — Topic Management UI
3. **3.9 Build** — Brief Display Page
4. **3.10 Build** — Brief History Page
5. **3.11 Build** — Landing Page
6. **3.13 Build** — Time Saved Metric
7. **3.17 Build** — Mobile-Responsive Design
**Goal:** Build the entire frontend in one context-loaded session.

---

### RUN 11 — Model: FLASH
**Context:** `frontend/pages/onboarding.tsx`, `frontend/pages/share/`, `src/truebrief/tasks/`
**Tasks:**
1. **3.12 Build** — Onboarding Flow
2. **3.14 Build** — Public Sharing Pages
3. **3.15 Build** — Email Digest
4. **3.16 Build** — Web Push Notifications
**Goal:** Build delivery channels and user flow features.

---

### RUN 12 — Model: FLASH
**Context:** `src/truebrief/api/middleware.py`, `src/truebrief/collector/`, `railway.toml`, `vercel.json`
**Tasks:**
1. **3.18 Build** — Rate Limiting
2. **3.19 Build** — Brave + Exa Plugins
3. **3.20 Build** — Deployment Config
**Goal:** Finish backend infrastructure and deploy to production.

---

## PHASE 3 — TEST Runs

### RUN 13 — Model: SONNET
**Context:** `tests/`, `src/truebrief/billing/`, `src/truebrief/api/`
**Tasks:**
1. **3.4 Unit + Intg** — Stripe webhooks (mock Stripe events + live checkout)
2. **3.5 Unit + Intg** — Tier enforcement (free user → 402, pro user → pass)
3. **3.7 Unit + Intg** — Auth (valid JWT → user, invalid → 401)
4. **3.18 Unit + Intg** — Rate limits (exceed limit → 429, headers correct)
**Goal:** Verify all monetization + auth acceptance criteria.

---

### RUN 14 — Model: FLASH
**Context:** `tests/`, `frontend/`
**Tasks:**
1. **3.6 / 3.8 / 3.9 / 3.10 / 3.11 / 3.13 / 3.17 Unit** — Frontend page renders
2. **3.15 / 3.16 Unit** — Email + push task unit tests
3. **3.19 Unit** — Brave + Exa layer returns `List[RawArticle]`
**Goal:** Verify all frontend and delivery components in isolation.

---

## PHASE 4 — PLAN Runs

### RUN 15 — Model: OPUS
**Context:** `src/truebrief/billing/usage.py`, `billing/metered.py`
**Tasks:**
1. **4.6 Plan** — Usage Tracking + Metered Billing
**Goal:** Design the Redis counter → DB flush → Stripe metered billing pipeline.

---

### RUN 16 — Model: SONNET
**Context:** `src/truebrief/api/api_keys.py`, `models/api_key.py`, `api/routes.py`
**Tasks:**
1. **4.1 Plan** — Public API + API Key Auth
2. **4.3 Plan** — GET /delta Endpoint
3. **4.4 Plan** — GET /nodes Endpoint
**Goal:** Design the full B2B read API surface — auth to response schema.

---

### RUN 17 — Model: SONNET
**Context:** `src/truebrief/models/webhook.py`, `tasks/webhook_delivery.py`
**Tasks:**
1. **4.5 Plan** — POST /webhooks Registration
2. **4.7 Plan** — Webhook Delivery Engine
**Goal:** Design webhook lifecycle: register → verify → deliver → retry → disable.

---

### RUN 18 — Model: SONNET
**Context:** `src/truebrief/api/middleware.py`, `api/server.py`
**Tasks:**
1. **4.9 Plan** — Rate Limits by B2B Tier
2. **4.10 Plan** — API Versioning + Deprecation Headers
**Goal:** Design B2B-tier rate limits and long-term versioning strategy.

---

### RUN 19 — Model: FLASH
**Context:** `src/truebrief/api/server.py`, `frontend/pages/admin/`
**Tasks:**
1. **4.2 Plan** — API Docs
2. **4.8 Plan** — Admin Dashboard
**Goal:** Plan OpenAPI enrichment and admin page structure.

---

## PHASE 4 — BUILD + TEST Runs

### RUN 20 — Model: FLASH
**Context:** `src/truebrief/api/`, `src/truebrief/billing/`, `src/truebrief/models/`, `src/truebrief/tasks/`
**Tasks:**
1. **4.1 Build** — API Key Auth
2. **4.3 Build** — /delta endpoint
3. **4.4 Build** — /nodes endpoint
4. **4.5 Build** — /webhooks registration
5. **4.6 Build** — Usage tracking
6. **4.7 Build** — Webhook delivery engine
7. **4.9 Build** — Rate limits by tier
8. **4.10 Build** — API versioning
**Goal:** Build entire B2B API layer in one backend context session.

---

### RUN 21 — Model: FLASH
**Context:** `src/truebrief/api/server.py`, `frontend/pages/admin/`
**Tasks:**
1. **4.2 Build** — Polish API docs
2. **4.8 Build** — Admin dashboard
**Goal:** Build documentation and internal tooling.

---

### RUN 22 — Model: SONNET
**Context:** `tests/`, B2B API routes
**Tasks:**
1. **4.1 / 4.3 / 4.4 / 4.5 / 4.7 / 4.9 / 4.10 Intg** — End-to-end API key auth, delta/nodes responses, webhook delivery + retry
**Goal:** Verify all B2B API acceptance criteria with real DB and Stripe.

---

## PHASE 5 — PLAN Runs

### RUN 23 — Model: OPUS
**Context:** `src/truebrief/arbiter/contradiction.py`
**Tasks:**
1. **5.4 Plan** — Contradiction Detection
**Goal:** Design the LLM contradiction prompt, fast-path conditions, and brief rendering.

---

### RUN 24 — Model: SONNET
**Context:** `src/truebrief/collector/registry.py`, `config/plugins.yaml`, `ledger/ayr_network.py`
**Tasks:**
1. **5.1 Plan** — Plugin Architecture (formalized)
2. **5.2 Plan** — Global AYR Network
**Goal:** Design config-driven plugin registry and cross-user AYR aggregation layer.

---

### RUN 25 — Model: SONNET
**Context:** `src/truebrief/collector/`, `config/routing_rules.yaml`
**Tasks:**
1. **5.5 Plan** — Multi-Language Support
2. **5.6 Plan** — Specialized Source Plugins (SEC, PubMed, FDA, EUR-Lex)
**Goal:** Design multilingual embeddings swap and domain-specific source plugin specs.

---

### RUN 26 — Model: SONNET
**Context:** `src/truebrief/models/org.py`, `api/org_routes.py`, `frontend/`
**Tasks:**
1. **5.7 Plan** — Team / Org Accounts
2. **5.9 Plan** — Mobile App (React Native)
**Goal:** Design org data model + RBAC, and mobile app architecture.

---

### RUN 27 — Model: FLASH
**Context:** `src/truebrief/api/feedback.py`, `api/tenant.py`, `config/tenants/`
**Tasks:**
1. **5.3 Plan** — User Feedback Loop
2. **5.8 Plan** — White-Label B2B UI
**Goal:** Plan feedback signal routing and tenant config system.

---

## PHASE 5 — BUILD + TEST Runs

### RUN 28 — Model: FLASH
**Context:** `src/truebrief/collector/`, `src/truebrief/ledger/`, `config/`
**Tasks:**
1. **5.1 Build** — Plugin Architecture
2. **5.2 Build** — Global AYR Network
3. **5.5 Build** — Multi-Language Support
4. **5.6 Build** — Specialized Source Plugins
**Goal:** Build the data layer scale features: plugin registry, AYR network, new sources.

---

### RUN 29 — Model: FLASH
**Context:** `src/truebrief/arbiter/`, `api/feedback.py`, `tasks/`, `models/org.py`, `api/tenant.py`
**Tasks:**
1. **5.3 Build** — User Feedback Loop
2. **5.4 Build** — Contradiction Detection
3. **5.7 Build** — Team / Org Accounts
4. **5.8 Build** — White-Label B2B UI
**Goal:** Build intelligence + enterprise features.

---

### RUN 30 — Model: SONNET
**Context:** `tests/`
**Tasks:**
1. **5.1 / 5.2 Intg** — Plugin loads correctly per tier; global AYR updates after pipeline run
2. **5.4 Intg** — Two conflicting articles → contradiction flagged in brief
3. **5.7 Intg** — Org invite → member sees shared topics
**Goal:** Verify scale + moat features end-to-end.

---

## PHASE 6 — PLAN Runs

### RUN 31 — Model: OPUS
**Context:** `src/truebrief/router/domain_router.py`, `config/domain_config.yaml`
**Tasks:**
1. **6.1 Plan** — Domain Router Brain
**Goal:** Design the LLM classifier, multi-domain fan-out, and domain config schema.

---

### RUN 32 — Model: OPUS
**Context:** `src/truebrief/domains/finance/`, `src/truebrief/domains/legal/`
**Tasks:**
1. **6.2 Plan** — Finance Intelligence Pipeline
2. **6.3 Plan** — Legal Intelligence Pipeline
**Goal:** Design domain-specific harvester prompts, arbiter rules, and custom alpha fields for finance + legal.

---

### RUN 33 — Model: OPUS
**Context:** `src/truebrief/domains/medical/`, `src/truebrief/router/classifier.py`
**Tasks:**
1. **6.4 Plan** — Medical Intelligence Pipeline
2. **6.5 Plan** — Fine-Tuned Local Router
**Goal:** Design medical pipeline (confidence floors, trial tracking) and classifier training pipeline.

---

### RUN 34 — Model: OPUS
**Context:** `src/truebrief/tasks/feedback_loop.py`, `scripts/retrain_router.py`
**Tasks:**
1. **6.6 Plan** — System-Wide Feedback Loop
**Goal:** Design the automated retraining pipeline and system health metrics.

---

## PHASE 6 — BUILD + TEST Runs

### RUN 35 — Model: FLASH
**Context:** `src/truebrief/router/`, `config/domain_config.yaml`, `src/truebrief/domains/`
**Tasks:**
1. **6.1 Build** — Domain Router Brain
2. **6.2 Build** — Finance Pipeline
3. **6.3 Build** — Legal Pipeline
4. **6.4 Build** — Medical Pipeline
**Goal:** Build router + all three domain pipelines in one domain-layer context session.

---

### RUN 36 — Model: GEM-HIGH
**Context:** `src/truebrief/router/classifier.py`, `scripts/train_router.py`, `models/router/`
**Tasks:**
1. **6.5 Build** — Fine-Tuned Local Router (training script + inference class)
**Goal:** Build and validate the ML training pipeline for the local domain classifier.

---

### RUN 37 — Model: FLASH
**Context:** `src/truebrief/tasks/feedback_loop.py`, `scripts/retrain_router.py`
**Tasks:**
1. **6.6 Build** — System-Wide Feedback Loop
**Goal:** Build the weekly Celery retraining task and health report generation.

---

### RUN 38 — Model: SONNET
**Context:** `tests/`
**Tasks:**
1. **6.1 Intg** — "FDA drug approval Pfizer" → routes medical(0.9) + finance(0.7)
2. **6.2 Intg** — SEC 8-K filing → finance alpha with ticker + metric fields
3. **6.3 Intg** — EU regulation → legal alpha with citation + jurisdiction
4. **6.4 Intg** — PubMed paper → medical alpha with trial_phase + p_value
5. **6.5 Intg** — Classifier < 10ms inference, ≥ 90% accuracy on test set
6. **6.6 Intg** — Weekly task runs, retraining triggers on 1000+ new samples
**Goal:** Verify all domain pipelines produce correct domain-specific alpha fields.

---

## 📊 Run Summary

| Runs | Phase | Model | Count |
|------|-------|-------|-------|
| 01 | P3 Plan | OPUS | 1 |
| 02–07 | P3 Plan | SONNET/GEM-PRO | 6 |
| 08 | P3 Plan | FLASH | 1 |
| 09–12 | P3 Build | FLASH | 4 |
| 13 | P3 Test | SONNET | 1 |
| 14 | P3 Test | FLASH | 1 |
| 15 | P4 Plan | OPUS | 1 |
| 16–18 | P4 Plan | SONNET | 3 |
| 19 | P4 Plan | FLASH | 1 |
| 20–21 | P4 Build | FLASH | 2 |
| 22 | P4 Test | SONNET | 1 |
| 23 | P5 Plan | OPUS | 1 |
| 24–26 | P5 Plan | SONNET | 3 |
| 27 | P5 Plan | FLASH | 1 |
| 28–29 | P5 Build | FLASH | 2 |
| 30 | P5 Test | SONNET | 1 |
| 31–34 | P6 Plan | OPUS | 4 |
| 35, 37 | P6 Build | FLASH | 2 |
| 36 | P6 Build | GEM-HIGH | 1 |
| 38 | P6 Test | SONNET | 1 |
| **Total** | | | **38 runs** |
