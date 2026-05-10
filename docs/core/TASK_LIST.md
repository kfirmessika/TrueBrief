# 📋 TrueBrief Master Task List
> **Purpose:** Raw data for the Plan Packer script.
> **Format:** | ID | Title | Complexity | Pattern | Runs | Plan-Model | Build-Model | Intg-Model |
>
> **Pattern Key** (from MODEL_ROUTER.md §Complexity-Based Execution Patterns):
> - **ATOMIC** (C≤5): FLASH does PLAN+BUILD+UNIT+INTG in 1 run
> - **SPEC+SHIP** (C 6–10): SONNET plans → FLASH builds+tests in 2 runs
> - **GUIDED BUILD** (C 11–18): SONNET plans → FLASH builds → SONNET verifies INTG in 3 runs
> - **FULL CYCLE** (C≥19): OPUS plans → SONNET validates → FLASH builds → SONNET INTG in 4 runs

| ID | Title | C | Pattern | Runs | Plan | Build | Intg |
|:---|:---|:---:|:---|:---:|:---|:---|:---|
| **Phase 3** | | | | | | | |
| 3.4 | Stripe Integration | 20 | FULL CYCLE | 4 | OPUS | FLASH | SONNET |
| 3.5 | Tier Enforcement | 10 | SPEC+SHIP | 2 | SONNET | FLASH | SONNET |
| 3.6 | Next.js Skeleton | 5 | ATOMIC | 1 | FLASH | FLASH | FLASH |
| 3.7 | Auth (Clerk/NextAuth) | 15 | GUIDED BUILD | 3 | SONNET | FLASH | SONNET |
| 3.8 | Topic Management UI | 8 | SPEC+SHIP | 2 | SONNET | FLASH | FLASH |
| 3.9 | Brief Display Page | 10 | SPEC+SHIP | 2 | SONNET | FLASH | SONNET |
| 3.10 | Brief History Page | 5 | ATOMIC | 1 | FLASH | FLASH | FLASH |
| 3.11 | Landing Page | 5 | ATOMIC | 1 | FLASH | FLASH | FLASH |
| 3.12 | Onboarding Flow | 12 | GUIDED BUILD | 3 | SONNET | FLASH | SONNET |
| 3.13 | "Time Saved" Metric | 5 | ATOMIC | 1 | FLASH | FLASH | FLASH |
| 3.14 | Public Sharing Pages | 10 | SPEC+SHIP | 2 | SONNET | FLASH | SONNET |
| 3.15 | Email Digest | 15 | GUIDED BUILD | 3 | SONNET | FLASH | SONNET |
| 3.16 | Web Push Notifications | 15 | GUIDED BUILD | 3 | SONNET | FLASH | SONNET |
| 3.17 | Mobile-Responsive | 8 | SPEC+SHIP | 2 | SONNET | FLASH | FLASH |
| 3.18 | Rate Limiting & Abuse | 18 | GUIDED BUILD | 3 | SONNET | FLASH | SONNET |
| 3.19 | Brave Search + Exa | 15 | GUIDED BUILD | 3 | SONNET | FLASH | SONNET |
| 3.20 | Deployment | 10 | SPEC+SHIP | 2 | SONNET | FLASH | SONNET |
| **Phase 4** | | | | | | | |
| 4.1 | Public API + Auth | 15 | GUIDED BUILD | 3 | SONNET | FLASH | SONNET |
| 4.2 | API Docs | 5 | ATOMIC | 1 | FLASH | FLASH | FLASH |
| 4.3 | GET /delta Endpoint | 12 | GUIDED BUILD | 3 | SONNET | FLASH | SONNET |
| 4.4 | GET /nodes Endpoint | 12 | GUIDED BUILD | 3 | SONNET | FLASH | SONNET |
| 4.5 | POST /webhooks | 15 | GUIDED BUILD | 3 | SONNET | FLASH | SONNET |
| 4.6 | Usage & Billing | 20 | FULL CYCLE | 4 | OPUS | FLASH | SONNET |
| 4.7 | Webhook Engine | 18 | GUIDED BUILD | 3 | SONNET | FLASH | SONNET |
| 4.8 | Admin Dashboard | 12 | GUIDED BUILD | 3 | SONNET | FLASH | FLASH |
| 4.9 | B2B Rate Limits | 12 | GUIDED BUILD | 3 | SONNET | FLASH | SONNET |
| 4.10 | API Versioning | 10 | SPEC+SHIP | 2 | SONNET | FLASH | SONNET |
| **Phase 5** | | | | | | | |
| 5.1 | Plugin Architecture | 18 | GUIDED BUILD | 3 | SONNET | FLASH | SONNET |
| 5.2 | Global AYR Network | 15 | GUIDED BUILD | 3 | SONNET | FLASH | SONNET |
| 5.3 | User Feedback Loop | 10 | SPEC+SHIP | 2 | FLASH | FLASH | SONNET |
| 5.4 | Contradiction Detection | 20 | FULL CYCLE | 4 | OPUS | FLASH | SONNET |
| 5.5 | Multi-Language | 12 | GUIDED BUILD | 3 | SONNET | FLASH | SONNET |
| 5.6 | Special Source Plugins | 15 | GUIDED BUILD | 3 | SONNET | FLASH | SONNET |
| 5.7 | Team / Org Accounts | 18 | GUIDED BUILD | 3 | SONNET | FLASH | SONNET |
| 5.8 | White-Label B2B UI | 15 | GUIDED BUILD | 3 | SONNET | FLASH | SONNET |
| 5.9 | Mobile App (RN) | 20 | FULL CYCLE | 4 | OPUS | FLASH | SONNET |
| **Phase 6** | | | | | | | |
| 6.1 | Domain Router Brain | 20 | FULL CYCLE | 4 | OPUS | FLASH | SONNET |
| 6.2 | Finance Pipeline | 20 | FULL CYCLE | 4 | OPUS | FLASH | SONNET |
| 6.3 | Legal Pipeline | 20 | FULL CYCLE | 4 | OPUS | FLASH | SONNET |
| 6.4 | Medical Pipeline | 20 | FULL CYCLE | 4 | OPUS | FLASH | SONNET |
| 6.5 | Fine-Tuned Router | 18 | GUIDED BUILD | 3 | OPUS | FLASH | SONNET |
| 6.6 | Sys-Wide Feedback | 15 | GUIDED BUILD | 3 | SONNET | FLASH | SONNET |
