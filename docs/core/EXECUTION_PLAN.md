# 🛰️ TrueBrief Execution Plan (Run-Based)
> **Format:** Tasks grouped into Execution Runs by Model + shared file context.
> **Philosophy:** Vertical Chaining with Complexity-Based Patterns. ATOMIC tasks are 1 run. SPEC+SHIP is 2. GUIDED BUILD is 3. FULL CYCLE is 4.
> **Pattern Reference:** See `.ai/refs/MODEL_ROUTER.md §Complexity-Based Execution Patterns`
> **Status Protocol:** FREE Models (Flash) MUST update the `[ ]` status in this file after completing their work.
> **Source of truth:** Optimized via `scripts/plan_packer.py`.

---

## ⛓️ Dependency Order (must respect across all runs)
- 3.5 → 3.4 | 3.8 → 3.7 | 3.14/3.15/3.16 → 3.6
- 4.7 → 4.5 | 4.6 → 4.3
- 5.2 → 5.1 | 5.7 → 3.7
- 6.1 → 5.1 | 6.2/6.3/6.4 → 6.1 | 6.5 → 6.1 | 6.6 → 5.3

---

## 📐 Pattern Legend
| Pattern | Runs | Description |
|:---|:---:|:---|
| ATOMIC | 1 | Flash does PLAN+BUILD+UNIT+INTG in one shot (C≤5) |
| SPEC+SHIP | 2 | Sonnet: PLAN+SPEC → Flash: BUILD+UNIT+INTG (C 6–10) |
| GUIDED BUILD | 3 | Sonnet: PLAN+SPEC → Flash: BUILD+UNIT → Sonnet: INTG+verify (C 11–18) |
| FULL CYCLE | 4 | Opus: PLAN → Sonnet: SPEC+validate → Flash: BUILD+UNIT → Sonnet: INTG (C≥19) |

---

## ✅ COMPLETED

### RUN [x] 01 — Model: OPUS | Pattern: FULL CYCLE (3.4)
**Tasks:**
- **3.4 PLAN** — Stripe Integration

---
### RUN [x] 02 — Model: FLASH | Pattern: FULL CYCLE (3.4)
**Tasks:**
- **3.4 BUILD** — Stripe Integration

---
### RUN [x] 03 — Model: FLASH | Pattern: FULL CYCLE (3.4)
**Tasks:**
- **3.4 UNIT** — Stripe Integration

---
### RUN [x] 04 — Model: SONNET | Pattern: FULL CYCLE (3.4) + SPEC+SHIP (3.5)
**Tasks:**
- **3.4 INTG** — Stripe Integration
- **3.5 PLAN+SPEC** — Tier Enforcement *(Sonnet PLAN run doubles as 3.5 spec)*

---
### RUN [x] 05 — Model: FLASH | Pattern: SPEC+SHIP (3.5)
**Tasks:**
- **3.5 BUILD+UNIT+INTG** — Tier Enforcement

---
### RUN [x] 06 — Model: SONNET | Pattern: GUIDED BUILD (3.7) start
**Tasks:**
- **3.7 PLAN+SPEC** — Auth (Clerk/NextAuth)

---
### RUN [x] 07 — Model: FLASH | Pattern: ATOMIC (3.6)
**Tasks:**
- **3.6 PLAN+BUILD+UNIT+INTG** — Next.js Skeleton *(All 4 phases in 1 Flash run)*

---
### RUN [x] 08 — Model: FLASH | Pattern: GUIDED BUILD (3.7)
**Tasks:**
- **3.7 BUILD+UNIT** — Auth (Clerk/NextAuth)

---
### RUN [x] 09 — Model: SONNET | Pattern: GUIDED BUILD (3.7) + SPEC+SHIP (3.8)
**Tasks:**
- **3.7 INTG+verify** — Auth (Clerk/NextAuth) *(Sonnet owns INTG — real backend, Clerk JWT, 402/429 paths)*
- **3.8 PLAN+SPEC** — Topic Management UI *(Sonnet INTG run doubles as 3.8 spec — context overlap)*

---
### RUN [x] 10 — Model: FLASH | Pattern: SPEC+SHIP (3.8)
**Tasks:**
- **3.8 BUILD+UNIT+INTG** — Topic Management UI
> ⚠️ **Gap noted:** Browser smoke test (8 manual steps: live backend + Clerk sign-in + real 402/429) was NOT confirmed. MSW mocks passed ≠ real backend verified. Carry forward to 3.9 smoke.

---

## 🔄 IN PROGRESS / NEXT

### RUN [x] 11 — Model: SONNET | Pattern: SPEC+SHIP (3.9)
**Tasks:**
- **3.9 PLAN+SPEC** — Brief Display Page
> 🎯 **Goal:** Zero-ambiguity spec: all RSC/client split, types from API, test targets (unit count, intg scenarios). Include deferred smoke test from 3.8 in INTG checklist.

---
### RUN [x] 12 — Model: FLASH | Pattern: SPEC+SHIP (3.9)
**Tasks:**
- **3.9 BUILD+UNIT+INTG** — Brief Display Page
> ⚠️ INTG must include real backend smoke (not just MSW). Document result explicitly.

---

## 📋 PLANNED — Phase 3 (Remaining)

### RUN [ ] 13 — Model: FLASH | Pattern: ATOMIC (3.10)
**Tasks:**
- **3.10 PLAN+BUILD+UNIT+INTG** — Brief History Page
> *All 4 phases in 1 run. C=5, pure UI, Flash-only.*

---
### RUN [ ] 14 — Model: FLASH | Pattern: ATOMIC (3.11)
**Tasks:**
- **3.11 PLAN+BUILD+UNIT+INTG** — Landing Page
> *All 4 phases in 1 run. C=5, static page, Flash-only.*

---
### RUN [ ] 15 — Model: SONNET | Pattern: GUIDED BUILD (3.12)
**Tasks:**
- **3.12 PLAN+SPEC** — Onboarding Flow

---
### RUN [ ] 16 — Model: FLASH | Pattern: GUIDED BUILD (3.12)
**Tasks:**
- **3.12 BUILD+UNIT** — Onboarding Flow

---
### RUN [ ] 17 — Model: SONNET | Pattern: GUIDED BUILD (3.12) + ATOMIC (3.13)
**Tasks:**
- **3.12 INTG+verify** — Onboarding Flow
- **3.13 PLAN+BUILD+UNIT+INTG** — "Time Saved" Metric *(C=5, Sonnet queues it while in session)*
> *Sonnet INTG session — can atomically ship 3.13 in same context since it's trivial.*

---
### RUN [ ] 18 — Model: SONNET | Pattern: SPEC+SHIP (3.14)
**Tasks:**
- **3.14 PLAN+SPEC** — Public Sharing Pages

---
### RUN [ ] 19 — Model: FLASH | Pattern: SPEC+SHIP (3.14)
**Tasks:**
- **3.14 BUILD+UNIT+INTG** — Public Sharing Pages

---
### RUN [ ] 20 — Model: SONNET | Pattern: GUIDED BUILD (3.15)
**Tasks:**
- **3.15 PLAN+SPEC** — Email Digest

---
### RUN [ ] 21 — Model: FLASH | Pattern: GUIDED BUILD (3.15)
**Tasks:**
- **3.15 BUILD+UNIT** — Email Digest

---
### RUN [ ] 22 — Model: SONNET | Pattern: GUIDED BUILD (3.15) + GUIDED BUILD (3.16)
**Tasks:**
- **3.15 INTG+verify** — Email Digest
- **3.16 PLAN+SPEC** — Web Push Notifications *(context overlap: both are notification systems)*

---
### RUN [ ] 23 — Model: FLASH | Pattern: GUIDED BUILD (3.16)
**Tasks:**
- **3.16 BUILD+UNIT** — Web Push Notifications

---
### RUN [ ] 24 — Model: SONNET | Pattern: GUIDED BUILD (3.16) + SPEC+SHIP (3.17)
**Tasks:**
- **3.16 INTG+verify** — Web Push Notifications
- **3.17 PLAN+SPEC** — Mobile-Responsive *(UI context, Sonnet session)*

---
### RUN [ ] 25 — Model: FLASH | Pattern: SPEC+SHIP (3.17)
**Tasks:**
- **3.17 BUILD+UNIT+INTG** — Mobile-Responsive

---
### RUN [ ] 26 — Model: SONNET | Pattern: GUIDED BUILD (3.18)
**Tasks:**
- **3.18 PLAN+SPEC** — Rate Limiting & Abuse

---
### RUN [ ] 27 — Model: FLASH | Pattern: GUIDED BUILD (3.18)
**Tasks:**
- **3.18 BUILD+UNIT** — Rate Limiting & Abuse

---
### RUN [ ] 28 — Model: SONNET | Pattern: GUIDED BUILD (3.18) + GUIDED BUILD (3.19)
**Tasks:**
- **3.18 INTG+verify** — Rate Limiting & Abuse
- **3.19 PLAN+SPEC** — Brave Search + Exa *(backend search context overlap)*

---
### RUN [ ] 29 — Model: FLASH | Pattern: GUIDED BUILD (3.19)
**Tasks:**
- **3.19 BUILD+UNIT** — Brave Search + Exa

---
### RUN [ ] 30 — Model: SONNET | Pattern: GUIDED BUILD (3.19) + SPEC+SHIP (3.20)
**Tasks:**
- **3.19 INTG+verify** — Brave Search + Exa
- **3.20 PLAN+SPEC** — Deployment

---
### RUN [ ] 31 — Model: FLASH | Pattern: SPEC+SHIP (3.20)
**Tasks:**
- **3.20 BUILD+UNIT+INTG** — Deployment

---

## 📋 PLANNED — Phase 4

### RUN [ ] 32 — Model: SONNET | Pattern: GUIDED BUILD (4.1)
**Tasks:**
- **4.1 PLAN+SPEC** — Public API + Auth

---
### RUN [ ] 33 — Model: FLASH | Pattern: GUIDED BUILD (4.1)
**Tasks:**
- **4.1 BUILD+UNIT** — Public API + Auth

---
### RUN [ ] 34 — Model: SONNET | Pattern: GUIDED BUILD (4.1) + ATOMIC (4.2)
**Tasks:**
- **4.1 INTG+verify** — Public API + Auth
- **4.2 PLAN+BUILD+UNIT+INTG** — API Docs *(C=5, trivial, ship in same Sonnet session)*

---
### RUN [ ] 35 — Model: SONNET | Pattern: GUIDED BUILD (4.3)
**Tasks:**
- **4.3 PLAN+SPEC** — GET /delta Endpoint

---
### RUN [ ] 36 — Model: FLASH | Pattern: GUIDED BUILD (4.3)
**Tasks:**
- **4.3 BUILD+UNIT** — GET /delta Endpoint

---
### RUN [ ] 37 — Model: SONNET | Pattern: GUIDED BUILD (4.3) + GUIDED BUILD (4.4)
**Tasks:**
- **4.3 INTG+verify** — GET /delta Endpoint
- **4.4 PLAN+SPEC** — GET /nodes Endpoint *(endpoint family, same context)*

---
### RUN [ ] 38 — Model: FLASH | Pattern: GUIDED BUILD (4.4)
**Tasks:**
- **4.4 BUILD+UNIT** — GET /nodes Endpoint

---
### RUN [ ] 39 — Model: SONNET | Pattern: GUIDED BUILD (4.4) + GUIDED BUILD (4.5)
**Tasks:**
- **4.4 INTG+verify** — GET /nodes Endpoint
- **4.5 PLAN+SPEC** — POST /webhooks

---
### RUN [ ] 40 — Model: FLASH | Pattern: GUIDED BUILD (4.5)
**Tasks:**
- **4.5 BUILD+UNIT** — POST /webhooks

---
### RUN [ ] 41 — Model: SONNET | Pattern: GUIDED BUILD (4.5)
**Tasks:**
- **4.5 INTG+verify** — POST /webhooks

---
### RUN [ ] 42 — Model: OPUS | Pattern: FULL CYCLE (4.6)
**Tasks:**
- **4.6 PLAN** — Usage & Billing

---
### RUN [ ] 43 — Model: SONNET | Pattern: FULL CYCLE (4.6)
**Tasks:**
- **4.6 SPEC+validate** — Usage & Billing *(Sonnet translates OPUS plan into zero-ambiguity spec)*

---
### RUN [ ] 44 — Model: FLASH | Pattern: FULL CYCLE (4.6)
**Tasks:**
- **4.6 BUILD+UNIT** — Usage & Billing

---
### RUN [ ] 45 — Model: SONNET | Pattern: FULL CYCLE (4.6) + GUIDED BUILD (4.7)
**Tasks:**
- **4.6 INTG+verify** — Usage & Billing
- **4.7 PLAN+SPEC** — Webhook Engine *(billing+webhook context overlap)*

---
### RUN [ ] 46 — Model: FLASH | Pattern: GUIDED BUILD (4.7)
**Tasks:**
- **4.7 BUILD+UNIT** — Webhook Engine

---
### RUN [ ] 47 — Model: SONNET | Pattern: GUIDED BUILD (4.7) + GUIDED BUILD (4.8)
**Tasks:**
- **4.7 INTG+verify** — Webhook Engine
- **4.8 PLAN+SPEC** — Admin Dashboard

---
### RUN [ ] 48 — Model: FLASH | Pattern: GUIDED BUILD (4.8)
**Tasks:**
- **4.8 BUILD+UNIT+INTG** — Admin Dashboard *(INTG is Flash-safe: UI-only, no live critical paths)*

---
### RUN [ ] 49 — Model: SONNET | Pattern: GUIDED BUILD (4.9)
**Tasks:**
- **4.9 PLAN+SPEC** — B2B Rate Limits

---
### RUN [ ] 50 — Model: FLASH | Pattern: GUIDED BUILD (4.9)
**Tasks:**
- **4.9 BUILD+UNIT** — B2B Rate Limits

---
### RUN [ ] 51 — Model: SONNET | Pattern: GUIDED BUILD (4.9) + SPEC+SHIP (4.10)
**Tasks:**
- **4.9 INTG+verify** — B2B Rate Limits
- **4.10 PLAN+SPEC** — API Versioning

---
### RUN [ ] 52 — Model: FLASH | Pattern: SPEC+SHIP (4.10)
**Tasks:**
- **4.10 BUILD+UNIT+INTG** — API Versioning

---

## 📋 PLANNED — Phase 5

### RUN [ ] 53 — Model: SONNET | Pattern: GUIDED BUILD (5.1)
**Tasks:**
- **5.1 PLAN+SPEC** — Plugin Architecture

---
### RUN [ ] 54 — Model: FLASH | Pattern: GUIDED BUILD (5.1)
**Tasks:**
- **5.1 BUILD+UNIT** — Plugin Architecture

---
### RUN [ ] 55 — Model: SONNET | Pattern: GUIDED BUILD (5.1) + GUIDED BUILD (5.2)
**Tasks:**
- **5.1 INTG+verify** — Plugin Architecture
- **5.2 PLAN+SPEC** — Global AYR Network

---
### RUN [ ] 56 — Model: FLASH | Pattern: GUIDED BUILD (5.2)
**Tasks:**
- **5.2 BUILD+UNIT** — Global AYR Network

---
### RUN [ ] 57 — Model: SONNET | Pattern: GUIDED BUILD (5.2) + SPEC+SHIP (5.3)
**Tasks:**
- **5.2 INTG+verify** — Global AYR Network
- **5.3 PLAN+SPEC** — User Feedback Loop

---
### RUN [ ] 58 — Model: FLASH | Pattern: SPEC+SHIP (5.3)
**Tasks:**
- **5.3 BUILD+UNIT+INTG** — User Feedback Loop

---
### RUN [ ] 59 — Model: OPUS | Pattern: FULL CYCLE (5.4)
**Tasks:**
- **5.4 PLAN** — Contradiction Detection

---
### RUN [ ] 60 — Model: SONNET | Pattern: FULL CYCLE (5.4)
**Tasks:**
- **5.4 SPEC+validate** — Contradiction Detection

---
### RUN [ ] 61 — Model: FLASH | Pattern: FULL CYCLE (5.4)
**Tasks:**
- **5.4 BUILD+UNIT** — Contradiction Detection

---
### RUN [ ] 62 — Model: SONNET | Pattern: FULL CYCLE (5.4) + GUIDED BUILD (5.5)
**Tasks:**
- **5.4 INTG+verify** — Contradiction Detection
- **5.5 PLAN+SPEC** — Multi-Language

---
### RUN [ ] 63 — Model: FLASH | Pattern: GUIDED BUILD (5.5)
**Tasks:**
- **5.5 BUILD+UNIT** — Multi-Language

---
### RUN [ ] 64 — Model: SONNET | Pattern: GUIDED BUILD (5.5) + GUIDED BUILD (5.6)
**Tasks:**
- **5.5 INTG+verify** — Multi-Language
- **5.6 PLAN+SPEC** — Special Source Plugins

---
### RUN [ ] 65 — Model: FLASH | Pattern: GUIDED BUILD (5.6)
**Tasks:**
- **5.6 BUILD+UNIT** — Special Source Plugins

---
### RUN [ ] 66 — Model: SONNET | Pattern: GUIDED BUILD (5.6) + GUIDED BUILD (5.7)
**Tasks:**
- **5.6 INTG+verify** — Special Source Plugins
- **5.7 PLAN+SPEC** — Team / Org Accounts

---
### RUN [ ] 67 — Model: FLASH | Pattern: GUIDED BUILD (5.7)
**Tasks:**
- **5.7 BUILD+UNIT** — Team / Org Accounts

---
### RUN [ ] 68 — Model: SONNET | Pattern: GUIDED BUILD (5.7) + GUIDED BUILD (5.8)
**Tasks:**
- **5.7 INTG+verify** — Team / Org Accounts
- **5.8 PLAN+SPEC** — White-Label B2B UI

---
### RUN [ ] 69 — Model: FLASH | Pattern: GUIDED BUILD (5.8)
**Tasks:**
- **5.8 BUILD+UNIT** — White-Label B2B UI

---
### RUN [ ] 70 — Model: SONNET | Pattern: GUIDED BUILD (5.8)
**Tasks:**
- **5.8 INTG+verify** — White-Label B2B UI

---
### RUN [ ] 71 — Model: OPUS | Pattern: FULL CYCLE (5.9)
**Tasks:**
- **5.9 PLAN** — Mobile App (RN)

---
### RUN [ ] 72 — Model: SONNET | Pattern: FULL CYCLE (5.9)
**Tasks:**
- **5.9 SPEC+validate** — Mobile App (RN)

---
### RUN [ ] 73 — Model: FLASH | Pattern: FULL CYCLE (5.9)
**Tasks:**
- **5.9 BUILD+UNIT** — Mobile App (RN)

---
### RUN [ ] 74 — Model: SONNET | Pattern: FULL CYCLE (5.9)
**Tasks:**
- **5.9 INTG+verify** — Mobile App (RN)

---

## 📋 PLANNED — Phase 6

### RUN [ ] 75 — Model: OPUS | Pattern: FULL CYCLE (6.1)
**Tasks:**
- **6.1 PLAN** — Domain Router Brain

---
### RUN [ ] 76 — Model: SONNET | Pattern: FULL CYCLE (6.1)
**Tasks:**
- **6.1 SPEC+validate** — Domain Router Brain

---
### RUN [ ] 77 — Model: FLASH | Pattern: FULL CYCLE (6.1)
**Tasks:**
- **6.1 BUILD+UNIT** — Domain Router Brain

---
### RUN [ ] 78 — Model: SONNET | Pattern: FULL CYCLE (6.1) + FULL CYCLE (6.2)
**Tasks:**
- **6.1 INTG+verify** — Domain Router Brain
- **6.2 PLAN** — Finance Pipeline *(OPUS-level task; Sonnet queues handoff note only)*
> ⚠️ Sonnet does NOT plan 6.2 — it only writes the handoff note for OPUS.

---
### RUN [ ] 79 — Model: OPUS | Pattern: FULL CYCLE (6.2)
**Tasks:**
- **6.2 PLAN** — Finance Pipeline

---
### RUN [ ] 80 — Model: SONNET | Pattern: FULL CYCLE (6.2)
**Tasks:**
- **6.2 SPEC+validate** — Finance Pipeline

---
### RUN [ ] 81 — Model: FLASH | Pattern: FULL CYCLE (6.2)
**Tasks:**
- **6.2 BUILD+UNIT** — Finance Pipeline

---
### RUN [ ] 82 — Model: SONNET | Pattern: FULL CYCLE (6.2) + FULL CYCLE (6.3)
**Tasks:**
- **6.2 INTG+verify** — Finance Pipeline
- **6.3 PLAN** — Legal Pipeline *(OPUS handoff note only)*

---
### RUN [ ] 83 — Model: OPUS | Pattern: FULL CYCLE (6.3)
**Tasks:**
- **6.3 PLAN** — Legal Pipeline

---
### RUN [ ] 84 — Model: SONNET | Pattern: FULL CYCLE (6.3)
**Tasks:**
- **6.3 SPEC+validate** — Legal Pipeline

---
### RUN [ ] 85 — Model: FLASH | Pattern: FULL CYCLE (6.3)
**Tasks:**
- **6.3 BUILD+UNIT** — Legal Pipeline

---
### RUN [ ] 86 — Model: SONNET | Pattern: FULL CYCLE (6.3) + FULL CYCLE (6.4)
**Tasks:**
- **6.3 INTG+verify** — Legal Pipeline
- **6.4 PLAN** — Medical Pipeline *(OPUS handoff note only)*

---
### RUN [ ] 87 — Model: OPUS | Pattern: FULL CYCLE (6.4)
**Tasks:**
- **6.4 PLAN** — Medical Pipeline

---
### RUN [ ] 88 — Model: SONNET | Pattern: FULL CYCLE (6.4)
**Tasks:**
- **6.4 SPEC+validate** — Medical Pipeline

---
### RUN [ ] 89 — Model: FLASH | Pattern: FULL CYCLE (6.4)
**Tasks:**
- **6.4 BUILD+UNIT** — Medical Pipeline

---
### RUN [ ] 90 — Model: SONNET | Pattern: FULL CYCLE (6.4) + GUIDED BUILD (6.5)
**Tasks:**
- **6.4 INTG+verify** — Medical Pipeline
- **6.5 PLAN+SPEC** — Fine-Tuned Router

---
### RUN [ ] 91 — Model: FLASH | Pattern: GUIDED BUILD (6.5)
**Tasks:**
- **6.5 BUILD+UNIT** — Fine-Tuned Router

---
### RUN [ ] 92 — Model: SONNET | Pattern: GUIDED BUILD (6.5) + GUIDED BUILD (6.6)
**Tasks:**
- **6.5 INTG+verify** — Fine-Tuned Router
- **6.6 PLAN+SPEC** — Sys-Wide Feedback

---
### RUN [ ] 93 — Model: FLASH | Pattern: GUIDED BUILD (6.6)
**Tasks:**
- **6.6 BUILD+UNIT** — Sys-Wide Feedback

---
### RUN [ ] 94 — Model: SONNET | Pattern: GUIDED BUILD (6.6)
**Tasks:**
- **6.6 INTG+verify** — Sys-Wide Feedback

---
