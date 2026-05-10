# TrueBrief v2 - Roadmap
> **Sprint tracker.** High-level status only.  
> 📐 Status Tracking (Plan/Build/Test) happens in `docs/blueprints/phase_{N}.md`.
> ⛓️ Execution logic & Dependencies are in `docs/core/EXECUTION_PLAN.md`.

---

## Phase 0: Project Skeleton & Dev Environment
- `[x]` 0.1 - Folder structure
- `[x]` 0.2 - pyproject.toml
- `[x]` 0.3 - requirements.txt
- `[x]` 0.4 - config/settings.py
- `[x]` 0.5 - LLM abstraction layer
- `[x]` 0.6 - Data models
- `[x]` 0.7 - config/rss_feeds.yaml
- `[x]` 0.8 - .gitignore
- `[x]` 0.9 - README.md
- `[x]` 0.10 - Virtual environment
- `[x]` 0.11 - Supabase setup
- `[x]` 0.12 - Tavily setup
- `[x]` 0.13 - LLM setup
- `[x]` 0.14 - Import verification
- `[x]` 0.15 - Initial commit

---

## Phase 1: Core MVP
- `[x]` 1.0 - LLM Abstraction Layer
- `[x]` 1.1 - Collector: Query Builder
- `[x]` 1.2 - Collector: RSS Layer
- `[x]` 1.3 - Collector: Tavily Layer
- `[x]` 1.4 - Collector: Article Extractor
- `[x]` 1.5 - Harvester: Fact Extraction
- `[x]` 1.6 - Ledger: Supabase & Vector Store
- `[x]` 1.7 - Arbiter: Simple Delta Detection
- `[x]` 1.8 - Briefer: Simple Report Generation
- `[x]` 1.9 - Pipeline Runner: End-to-End
- `[x]` 1.10 - API Server: Basic Endpoints
- `[x]` 1.11 - Integration Test: Benchmark v2

---

## Phase 2: Delta Engine + Scheduling
- `[x]` 2.1 - Full Arbiter Logic
- `[x]` 2.2 - Judge LLM prompt
- `[x]` 2.3 - Temporal overlap engine
- `[x]` 2.4 - Celery + Redis
- `[x]` 2.5 - Celery Beat scheduler
- `[x]` 2.6 - Empty brief suppression
- `[x]` 2.7 - Brief history storage
- `[x]` 2.8 - Source quality logging
- `[x]` 2.9 - Google News RSS
- `[x]` 2.10 - AYR calculation
- `[x]` 2.11 - Dynamic keyword rotation
- `[x]` 2.12 - Shared topic infrastructure

---

## Phase 3: Frontend + Monetization
- `[x]` 3.1 - Story Nodes
- `[x]` 3.2 - Dual vectors
- `[x]` 3.3 - Recursive summary updates
- `[x]` 3.4 - Stripe Integration
- `[x]` 3.5 - Tier Enforcement
- `[x]` 3.6 - Next.js Frontend Skeleton
- `[x]` 3.7 - Auth (Clerk/NextAuth)
- `[/]` 3.8 - Topic Management UI
- `[x]` 3.9 - Brief Display Page
- `[ ]` 3.10 - Brief History Page
- `[ ]` 3.11 - Landing Page
- `[ ]` 3.12 - Onboarding Flow
- `[ ]` 3.13 - "Time Saved" Metric
- `[ ]` 3.14 - Public Sharing Pages
- `[ ]` 3.15 - Email Digest
- `[ ]` 3.16 - Web Push Notifications
- `[ ]` 3.17 - Mobile-Responsive Design
- `[ ]` 3.18 - Rate Limiting & Abuse
- `[ ]` 3.19 - Brave Search + Exa
- `[ ]` 3.20 - Deployment

---

## Phase 4: B2B API
- `[ ]` 4.1 - Public REST API + API Key Auth
- `[ ]` 4.2 - Polished API Docs
- `[ ]` 4.3 - GET /delta?since= Endpoint
- `[ ]` 4.4 - GET /nodes (Full Story Graph)
- `[ ]` 4.5 - POST /webhooks (Registration)
- `[ ]` 4.6 - Usage Tracking + Billing Logic
- `[ ]` 4.7 - Webhook Delivery Engine
- `[ ]` 4.8 - Admin Dashboard
- `[ ]` 4.9 - Rate Limits by Tier
- `[ ]` 4.10 - API Versioning & Headers

---

## Phase 5: Scale + Moat
- `[ ]` 5.1 - Plugin Architecture
- `[ ]` 5.2 - Global AYR Network
- `[ ]` 5.3 - User Feedback Loop
- `[ ]` 5.4 - Contradiction Detection
- `[ ]` 5.5 - Multi-Language Support
- `[ ]` 5.6 - Specialized Source Plugins
- `[ ]` 5.7 - Team / Org Accounts
- `[ ]` 5.8 - White-Label B2B UI
- `[ ]` 5.9 - Mobile App (React Native)

---

## Phase 6: Domain Intelligence Pipelines
- `[ ]` 6.1 - Domain Router Brain
- `[ ]` 6.2 - Finance Intelligence Pipeline
- `[ ]` 6.3 - Legal Intelligence Pipeline
- `[ ]` 6.4 - Medical Intelligence Pipeline
- `[ ]` 6.5 - Fine-Tuned Local Router
- `[ ]` 6.6 - System-Wide Feedback Loop
