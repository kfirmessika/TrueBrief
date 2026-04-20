# TrueBrief v2 — Roadmap

> **Sprint tracker.** Tasks, subtasks, statuses. This is WHERE we are right now.  
> **Last updated:** 2026-04-21 — Phase 0 skeleton complete  
> 📌 Read: [AI Rules](file:///d:/projects/Apps/TrueBrief/docs/ai_rules.md) → **this file** → [Implementation Plan](file:///d:/projects/Apps/TrueBrief/docs/implementation_plan.md) → [Architecture](file:///d:/projects/Apps/TrueBrief/docs/architecture.md)

---

## Status Legend

| Symbol | Meaning |
|--------|---------|
| `[ ]` | Not started |
| `[/]` | In progress |
| `[x]` | Done |
| `[!]` | Blocked / needs decision |
| `[-]` | Skipped / deferred |

---

## Pre-Work: Archive v1 & Start Clean

- `[x]` **0.0 — Archive v1**
  - `[x]` Commit all current v1 changes — `v1-final: archive before v2 rewrite`
  - `[x]` Create `v1-archive` branch
  - `[x]` Verify branch exists ✅
  - `[x]` Delete v1 source files from `main` (keep `.git`, `.gitignore`, `.env`, `.env.example`)
  - `[x]` Initial v2 commit — `v2: project skeleton`

---

## Phase 0: Project Skeleton & Dev Environment

- `[x]` **0.1 — Create folder structure** (src/, config/, tests/, scripts/, docs/)
- `[x]` **0.2 — pyproject.toml**
- `[x]` **0.3 — requirements.txt** (pinned deps + pydantic-settings)
- `[x]` **0.4 — config/settings.py** (env vars + LLM config)
- `[x]` **0.5 — LLM abstraction layer** (`llm/client.py`)
- `[x]` **0.6 — Data models** (`models/article.py`, `alpha.py`, `topic.py`, `brief.py`)
- `[x]` **0.7 — config/rss_feeds.yaml** (curated feed database)
- `[x]` **0.8 — .gitignore**
- `[x]` **0.9 — README.md**
- `[x]` **0.10 — Virtual environment & install deps** (`.venv/`)
- `[!]` **0.11 — Supabase connection string → .env** ← needs your Supabase URL + key
- `[!]` **0.12 — Tavily API key → .env** ← needs your Tavily key
- `[x]` **0.13 — Verify imports work** ✅ `All imports OK`
- `[ ]` **0.14 — Git commit:** `"v2: project skeleton with models and config"`

---

## Phase 1: Core MVP

> Goal: One topic → collect → extract → deduplicate → brief. No frontend. No scheduler.

- `[ ]` **1.0 — LLM Abstraction Layer**
  - `[ ]` `llm/client.py` — config-driven, supports Gemini / OpenAI
  - `[ ]` Handles rate limits and retries
  - `[ ]` Acceptance: `client.call("harvester", "...")` returns string

- `[ ]` **1.1 — Collector: Query Builder**
  - `[ ]` `collector/query_builder.py`
  - `[ ]` Topic → primary_query, alt_queries, rss_categories, date_filter
  - `[ ]` Garbage input rejection
  - `[ ]` RSS category matching from `rss_feeds.yaml`

- `[ ]` **1.2 — Collector: RSS Layer (PRIMARY)**
  - `[ ]` `collector/rss_layer.py`
  - `[ ]` Implements `SourceLayer` ABC
  - `[ ]` Returns `List[RawArticle]` with direct (non-redirect) URLs
  - `[ ]` Graceful handling of broken feeds

- `[ ]` **1.3 — Collector: Tavily Layer (SECONDARY)**
  - `[ ]` `collector/tavily_layer.py`
  - `[ ]` Returns `List[RawArticle]` with full text (no scraping needed)
  - `[ ]` Graceful skip if no API key
  - `[ ]` Credit usage logged

- `[ ]` **1.4 — Collector: Article Extractor**
  - `[ ]` `collector/extractor.py`
  - `[ ]` trafilatura for clean text from RSS article URLs
  - `[ ]` Cache by URL hash (never fetch same URL twice)
  - `[ ]` Bot-detection check

- `[ ]` **1.5 — Harvester: Fact Extraction**
  - `[ ]` `harvester/harvester.py`
  - `[ ]` Article text → `List[Alpha]` via LLM
  - `[ ]` Relative dates normalized to absolute
  - `[ ]` Confidence < 0.6 dropped

- `[ ]` **1.6 — Ledger: Supabase Schema & Vector Store**
  - `[ ]` `ledger/database.py` — Supabase connection + schema
  - `[ ]` `ledger/vector_store.py` — pgvector operations
  - `[ ]` Tables: users, topics, known_facts (vector col), briefs
  - `[ ]` Acceptance: insert fact → search near-duplicate → score > 0.85

- `[ ]` **1.7 — Arbiter: Simple Delta Detection**
  - `[ ]` `arbiter/arbiter.py`
  - `[ ]` Score > 0.90 → DUPLICATE; else → NEW
  - `[ ]` Acceptance: same fact twice → second is DUPLICATE

- `[ ]` **1.8 — Briefer: Simple Report Generation**
  - `[ ]` `briefer/briefer.py`
  - `[ ]` New Alphas → formatted brief string
  - `[ ]` NEW vs UPDATE sections separated
  - `[ ]` Source attribution included

- `[ ]` **1.9 — Pipeline Runner: End-to-End**
  - `[ ]` `pipeline/runner.py`
  - `[ ]` Wire all pillars: topic → collect → harvest → judge → brief
  - `[ ]` `python scripts/run_pipeline.py "TSMC semiconductor"` works
  - `[ ]` Completes < 60 seconds per topic

- `[ ]` **1.10 — API Server: Basic Endpoints**
  - `[ ]` `api/server.py` + `api/routes.py`
  - `[ ]` POST/GET/DELETE `/api/v1/topics`
  - `[ ]` POST `/api/v1/topics/{id}/scan`
  - `[ ]` GET `/api/v1/topics/{id}/briefs`
  - `[ ]` Auto-docs at `/docs`

- `[ ]` **1.11 — Integration Test: Master Benchmark v2**
  - `[ ]` `tests/test_pipeline.py`
  - `[ ]` Run against 21 test prompts from v1 benchmark
  - `[ ]` Compare v2 vs v1 results

---

## Phase 2: Delta Engine + Scheduling

> Goal: System runs autonomously, never repeats information.

- `[ ]` **2.1 — Full Arbiter: Fast-path logic** (> 0.97 auto-merge, zero matches auto-new)
- `[ ]` **2.2 — Judge LLM prompt** (MERGE / UPDATE / NEW for ambiguous cases)
- `[ ]` **2.3 — Temporal overlap math engine**
- `[ ]` **2.4 — Celery + Redis** (background tasks)
- `[ ]` **2.5 — Celery Beat scheduler** (per-topic polling intervals)
- `[ ]` **2.6 — Empty brief suppression** ("nothing new" → no delivery)
- `[ ]` **2.7 — Brief history storage**
- `[ ]` **2.8 — Source quality logging** (Alpha vs Duplicate per source — AYR foundation)
- `[ ]` **2.9 — Google News RSS** as 3rd source (with URL decoder)
- `[ ]` **2.10 — AYR calculation** + dynamic polling intervals
- `[ ]` **2.11 — Dynamic keyword rotation** (track best-performing search terms per topic)
- `[ ]` **2.12 — Shared topic infrastructure** (one pipeline run → fan out to all subscribers)

---

## Phase 3: Frontend + Monetization

> Goal: A product people can use and will pay for.

- `[ ]` **3.1 — Story Nodes** (group related facts into evolving stories)
- `[ ]` **3.2 — Dual vectors** (alpha_embedding + summary_embedding)
- `[ ]` **3.3 — Recursive summary updates** (on each story UPDATE)
- `[ ]` **3.4 — Stripe integration** (subscription management)
- `[ ]` **3.5 — Tier enforcement** (topic limits, speed, source access)
- `[ ]` **3.6 — Next.js frontend skeleton** (`npx create-next-app`)
- `[ ]` **3.7 — Auth** (Clerk or NextAuth.js)
- `[ ]` **3.8 — Topic management UI** (add / remove / list)
- `[ ]` **3.9 — Brief display page** (NEW / UPDATE / No changes)
- `[ ]` **3.10 — Brief history page**
- `[ ]` **3.11 — Landing page** (SEO + conversion)
- `[ ]` **3.12 — Onboarding flow**
- `[ ]` **3.13 — "Time saved" metric per user**
- `[ ]` **3.14 — Public brief sharing pages** (viral + SEO)
- `[ ]` **3.15 — Email digest** (SendGrid / Resend)
- `[ ]` **3.16 — Web push notifications** (PWA)
- `[ ]` **3.17 — Mobile-responsive design** (PWA-ready)
- `[ ]` **3.18 — Rate limiting & abuse prevention**
- `[ ]` **3.19 — Brave Search + Exa** source plugins
- `[ ]` **3.20 — Deploy** (Vercel frontend + Railway backend + Supabase)

---

## Phase 4: B2B API

> Goal: Revenue from business customers.

- `[ ]` **4.1 — Public REST API + API key auth**
- `[ ]` **4.2 — Polished API docs**
- `[ ]` **4.3 — `GET /delta?since=`** endpoint
- `[ ]` **4.4 — `GET /nodes`** (full story graph)
- `[ ]` **4.5 — `POST /webhooks`** (register delivery endpoint)
- `[ ]` **4.6 — Usage tracking + per-call billing**
- `[ ]` **4.7 — Webhook delivery**
- `[ ]` **4.8 — Admin dashboard** (B2B accounts)
- `[ ]` **4.9 — Rate limits by tier** (Business: 1K/day, Enterprise: unlimited)
- `[ ]` **4.10 — API versioning** (`/api/v1/`), deprecation headers

---

## Phase 5: Scale + Moat

> Goal: Build defensibility and compound advantages.

- `[ ]` **5.1 — Plugin architecture** (config-driven component swapping, A/B test harvesters)
- `[ ]` **5.2 — AYR shared across users** (system-level source reputation network)
- `[ ]` **5.3 — User feedback loop** (thumbs up/down → improve relevance)
- `[ ]` **5.4 — Contradiction detection** (two sources disagree → flag)
- `[ ]` **5.5 — Multi-language support** (multilingual embeddings)
- `[ ]` **5.6 — Specialized source plugins** (SEC EDGAR, PubMed, FDA, EU regulatory)
- `[ ]` **5.7 — Team / org accounts**
- `[ ]` **5.8 — White-label B2B** (custom branding, domain)
- `[ ]` **5.9 — Mobile app** (React Native — only if user demand justifies it)

---

## Phase 6: Domain Intelligence Pipelines (Year 2+)

> Goal: Specialized domain pipelines for finance, legal, medical, geopolitics.

- `[ ]` **6.1 — Domain router** (LLM classifies prompt → domain)
- `[ ]` **6.2 — Finance pipeline** (SEC filings, ticker tracking, earnings precision)
- `[ ]` **6.3 — Legal pipeline** (court dockets, citation-aware facts)
- `[ ]` **6.4 — Medical pipeline** (PubMed, clinical trials, drug approvals)
- `[ ]` **6.5 — Fine-tuned classifier** (replace LLM router, near-zero cost, < 10ms)
- `[ ]` **6.6 — Feedback loop** (user says "missed finance context" → router adjusts)
