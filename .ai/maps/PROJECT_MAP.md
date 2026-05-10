# TrueBrief — Project Map
> **Purpose:** Agent reads this instead of browsing. Updated after every BUILD session.  
> **Last updated:** 2026-05-11 | **Updated by:** Gemini Flash
> **Context:** Phase 3.9 Build Complete.

## Source Tree

### Backend (`src/truebrief/`)
```
src/truebrief/
├── arbiter/                  ← Deduplication & Novelty Logic
├── billing/                  ← Stripe integration & Tiering
├── collector/                ← Raw Content Acquisition (Tavily, RSS, GNews)
├── harvester/                ← Fact Extraction (Alphas)
├── ledger/                   ← Data Persistence (Supabase, Vector Store)
├── llm/                      ← Provider Abstraction (Gemini/OpenAI)
├── models/                   ← Domain Objects (Dataclasses)
├── pipeline/                 ← Orchestration (Runner)
└── tasks/                    ← Async Background Jobs (Celery)
```

### Frontend (`frontend/src/`)
```
frontend/src/
├── app/                      ← App Router Pages
│   ├── dashboard/            ← Topic Management Home
│   └── topics/[id]/          ← Topic Detail Shell
├── components/
│   ├── layout/               ← Navbar, Footer
│   ├── topics/               ← TopicCard, AddTopicForm, ScanStatusBadge, UpgradeBanner
│   ├── briefs/               ← BriefContent, BriefCard, CopyLinkButton
│   └── ui/                   ← Toast, ConfirmDialog
├── hooks/
│   ├── useTopics.ts          ← Topic CRUD + Scan Polling hooks
│   └── useTier.ts            ← Subscription Tier & Limits hook
├── lib/
│   ├── api.ts                ← RSC Fetcher & Shared Types
│   ├── useApi.ts             ← Client Axios w/ Clerk JWT Interceptor
│   └── query-client.ts       ← React Query Global Config
└── types/                    ← TS Interfaces
```

### Config & Infrastructure
```
config/                       ← settings.py, rss_feeds.yaml
scripts/                      ← migrations/, worker/beat starts, test scripts
tests/                        ← Backend unit & integration tests
```

## Key Config Reference
- **API Base:** `http://localhost:8000/api/v1`
- **Frontend Port:** `3000`
- **Database:** Supabase (PostgreSQL + pgvector).
- **Auth:** Clerk (Frontend) + JWT Verification (Backend).
