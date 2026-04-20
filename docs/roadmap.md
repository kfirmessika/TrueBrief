# TrueBrief v2 — Complete Development Roadmap

> **Living document.** Status updates happen here as we build. This is the single source of truth.  
> **Last updated:** 2026-04-18 — ADR-1 (LLM), ADR-2 (Database), ADR-3 (Sources) applied.
>
> 📄 **Definitive Plan (updated copy):** [truebrief_definitive_plan_v2.md](file:///C:/Users/user/.gemini/antigravity/brain/fcdcef8e-4468-4487-83f0-1dcf93b114aa/truebrief_definitive_plan_v2.md)

---

## How We Work Together (The Antigravity Workflow)

You're a solo developer. I'm your AI pair-programmer. Together we work like a professional team. Here's the system:

### The Loop (for every feature)

```
1. PLAN   → We discuss what to build. I create/update this roadmap.
2. SPEC   → I write the exact file changes before touching code.
3. BUILD  → I write the code. You review.
4. TEST   → We run it. Fix what breaks.
5. COMMIT → You commit to git with a clean message.
6. NEXT   → Move to the next item on the roadmap.
```

### Rules We Follow

| Rule | Why |
|------|-----|
| **Never code from zero when v1 has working logic** | v1 has battle-tested code. We read it first, extract the good parts, then build clean on top. |
| **One feature per conversation** | Keep conversations focused. Each session = one roadmap item. |
| **Test before moving on** | No skipping. Run the code. Verify it works. Then continue. |
| **Git commit after every working feature** | Small, clean commits. Not a giant "add everything" bomb. |
| **Ask me questions — don't guess** | If you don't understand something (architecture, business logic, a Python pattern), ask. That's how you learn. |

### How to Start a Session

When you open Antigravity to work on TrueBrief, say something like:

> *"Let's work on Phase 1, Step 1.2 — the RSS Layer collector plugin."*

I'll read this roadmap, find where we are, check the v1 reuse map, and we go.

### How to Use Planning Mode

- For **big features** (new pillar, new system): Use `/planning` mode → I research → create a plan → you approve → we build.
- For **small tasks** (fix a bug, tweak a prompt, add a field): Just ask directly → I code it → you test.

---

## Architecture Decision Records (ADR)

> These are the final decisions after research. Each decision includes what you said, what I found, and what's correct.

---

### ADR-1: LLM Strategy — Multi-LLM with Gemini as Primary

#### What you said
> "We can use different LLMs for each step. Use Gemini for prototype because free daily limit. Maybe private LLM on server later."

#### What I found (verified)
- **Gemini Flash free tier:** ~1,000-1,500 requests/day, 15 RPM. No credit card needed. ✅ Real.
- **OpenAI:** No free tier for API. Pay-per-use only. ❌ Not usable for zero-cost prototype.
- **Claude/Anthropic:** No free API tier. ❌ Same problem.
- **Grok/xAI:** No free tier suitable for automation. ❌

#### My Decision: ✅ You're correct — Gemini is the right choice for prototype

The pipeline has **5 LLM call points**. Here's exactly which LLM handles which call, and why:

| Pipeline Step | LLM Call | Model (Phase 1) | Model (Production) | Why |
|--------------|----------|-----------------|-------------------|-----|
| **Query Builder** | Topic → search queries | `gemini-2.5-flash` | `gemini-2.5-flash` | Simple task. Flash is fast and free. Never needs upgrade. |
| **Harvester** | Article → extract facts | `gemini-2.5-flash` | `gemini-2.5-pro` or `gpt-4o` | This is the most important call. Flash is fine for prototype; production needs higher accuracy for numbers/dates. |
| **Arbiter (Judge)** | Is this fact NEW/DUPLICATE/UPDATE? | `gemini-2.5-flash` | `gemini-2.5-flash` | Structured decision with clear rules. Flash handles this well. |
| **Briefer** | Facts → clean report | `gemini-2.5-flash` | `gemini-2.5-flash` | Text formatting. Doesn't need expensive model. |
| **Garbage Filter** | Reject bad input | `gemini-2.5-flash` | `gemini-2.5-flash` | Trivial classification. Flash forever. |

**Implementation: LLM abstraction layer**

```python
# config/settings.py
LLM_CONFIG = {
    "query_builder": {"provider": "gemini", "model": "gemini-2.5-flash"},
    "harvester":     {"provider": "gemini", "model": "gemini-2.5-flash"},
    "arbiter":       {"provider": "gemini", "model": "gemini-2.5-flash"},
    "briefer":       {"provider": "gemini", "model": "gemini-2.5-flash"},
    "garbage_filter": {"provider": "gemini", "model": "gemini-2.5-flash"},
}
```

We build a thin `LLMClient` wrapper that reads this config. To switch any step to OpenAI/Claude/local, you change ONE line in config. Zero code changes.

**About private/local LLMs:** Your instinct is right for the future, but wrong for now. Local LLMs (Llama, Mistral, etc.) need: GPU hardware (~$1K+), setup time, worse accuracy on structured JSON extraction. The free Gemini tier gives you 1,500 calls/day = enough to run 50+ full pipeline executions daily. That's more than enough through Phase 1-2. Revisit local LLMs when Gemini costs become real (Phase 3+, production traffic).

---

### ADR-2: Database — Supabase Cloud ✅ (Keep What You Set Up)

#### What you said
> "I opened Supabase, created project, enabled pgvector. Is local better?"

#### What I found (verified)
| Factor | Supabase Cloud (Free) | Local PostgreSQL |
|--------|----------------------|-----------------|
| Setup time | ✅ Done (you already did it) | ❌ Need to install PostgreSQL + pgvector extension on Windows (painful) |
| pgvector | ✅ Already enabled | ❌ Manual compilation on Windows |
| Cost | ✅ Free (500MB, enough for 100K+ facts) | ✅ Free |
| Maintenance | ✅ Zero (Supabase handles it) | ❌ You're the DBA |
| Access from anywhere | ✅ Yes (cloud) | ❌ Only from your machine |
| Production migration | ✅ Already cloud-ready | ❌ Need to migrate later |
| Downside | ⚠️ Pauses after 7 days inactive | None |

#### My Decision: ✅ Keep Supabase. You're already set up.

The "pauses after 7 days" problem is irrelevant during active development — you'll be using it daily. When we hit production, we either upgrade to Supabase Pro ($25/mo) or migrate to Railway/Render PostgreSQL (both simple SQL exports).

**Action:** When we start Phase 0, I'll tell you exactly when to grab the connection string and where to put it.

---

### ADR-3: News Source APIs — The Collector Strategy

This is the most complex decision. Let me address everything you said point by point.

#### What you said (fact-checked)

| Your claim | Verdict | Details |
|-----------|---------|---------|
| "Google News RSS gives redirected links, hard to get originals" | ✅ **CORRECT** | Google News RSS returns encoded redirect URLs (e.g., `news.google.com/rss/articles/CBMi...`). Decoding them requires calling a Google internal endpoint. Libraries exist (`googlenewsdecoder`) but they break frequently as Google changes the format. |
| "If we keep using same keywords, Google knows" | ⚠️ **Partially correct** | Google doesn't "learn" your queries, but they do rate-limit/block repeated automated access. No official rate limits = they can block you anytime. The dynamic keyword rotation idea is good but is a Phase 2+ optimization. |
| "NewsAPI free tier is limited to 100/day" | ✅ **CORRECT** | And worse than you think — the free tier has a **24-hour delay** AND **cannot be used in production** (their terms explicitly forbid it). Using it in a deployed product = license revocation. |
| "Direct RSS + Tavily for MVP to keep cost at $0" | ✅ **EXCELLENT RECOMMENDATION** | Direct RSS = truly free, no rate limits, publishers WANT you to read their feeds. Tavily = 1,000 free credits/month (500-1,000 searches). Combined = zero cost for MVP. |

#### The Full Source Comparison (researched)

| Source | Free Tier | Rate Limit | Quality | Real-Time? | Reliability | URL Issues |
|--------|-----------|------------|---------|------------|-------------|------------|
| **Direct RSS Feeds** | ✅ Unlimited | None | 🟢 High (publisher-direct) | 🟢 Yes (5-15 min delay) | 🟢 Very stable (RSS is a standard) | ✅ Direct original URLs |
| **Google News RSS** | ✅ Unlimited (unofficial) | ⚠️ Undefined (can block) | 🟢 High coverage | 🟢 Yes | 🔴 Fragile (unofficial, links break) | ❌ Redirect URLs need decoding |
| **Tavily API** | ✅ 1,000 credits/month | Defined & clear | 🟢 High (returns clean text!) | 🟢 Yes | 🟢 Stable (official API) | ✅ Direct URLs + full text |
| **NewsAPI.org** | 100 req/day | 100/day | 🟢 Good (150K sources) | 🔴 No (24h delay on free) | 🟢 Stable | ✅ Direct URLs |
| **Brave Search API** | ~1,000 req/month ($5 credit) | Defined | 🟡 Medium | 🟢 Yes | 🟢 Stable | ✅ Direct URLs |
| **Exa API** | $10 initial credit | Defined | 🟢 High (semantic search) | 🟢 Yes | 🟢 Stable | ✅ Direct URLs |

#### My Decision: Phase 1 Sources

```
Phase 1 (MVP — $0 cost):
  ├── Direct RSS Feeds ← PRIMARY (unlimited, free, real-time, original URLs)
  └── Tavily API       ← SECONDARY (1,000 free searches/month, returns CLEAN TEXT)

Phase 2 (scaling — still ~$0):
  ├── Direct RSS Feeds
  ├── Tavily API
  └── Google News RSS  ← ADD with googlenewsdecoder library (more coverage, accept fragility)

Phase 3+ (growth — pay for quality):
  ├── Direct RSS Feeds (always free)
  ├── Tavily API (pay-per-use beyond 1,000)
  ├── Brave Search API ($5/month for 1,000 req)
  └── Exa API (semantic deep search, $7/1,000 req)

NOT using:
  ├── NewsAPI.org — 24h delay on free tier + cannot use in production = useless for us
  └── Apify — too expensive for news scraping, better for social media (Phase 5+)
```

#### Why Direct RSS is the foundation (not Google News RSS)

| Reason | Detail |
|--------|--------|
| **Zero cost forever** | Publishers provide RSS for free. It's how they want you to consume their content. |
| **Original URLs** | No redirect decoding headaches. The URL in the RSS feed IS the article URL. |
| **Real-time** | Most major publishers update RSS within 5-15 minutes of publishing. |
| **Reliable** | RSS is a 20-year-old standard. It won't change or break. |
| **Legal** | Publishers choose to have RSS feeds. You're reading published content, not scraping. |

#### BUT — Direct RSS alone isn't enough

Direct RSS requires you to **know which feeds to subscribe to** for a given topic. This is where the **Query Builder + Tavily** combo fills the gap:

```
User enters: "TSMC semiconductor manufacturing"

1. Query Builder (LLM) → generates search queries
2. Tavily API → searches the web for those queries → returns article URLs + clean text
3. ALSO: match topic to known RSS feeds from our curated feed database

Result: Tavily catches breaking news Tavily finds. RSS catches everything from known publishers.
```

#### The Curated Feed Database (built into config)

```yaml
# config/rss_feeds.yaml
general:
  - url: https://feeds.reuters.com/reuters/topNews
    name: Reuters Top News
  - url: https://feeds.bbci.co.uk/news/rss.xml
    name: BBC News
  - url: https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml
    name: NYT Homepage

technology:
  - url: https://feeds.arstechnica.com/arstechnica/index
    name: Ars Technica
  - url: https://www.theverge.com/rss/index.xml
    name: The Verge
  - url: https://techcrunch.com/feed/
    name: TechCrunch

finance:
  - url: https://feeds.reuters.com/reuters/businessNews
    name: Reuters Business
  - url: https://www.cnbc.com/id/100003114/device/rss/rss.html
    name: CNBC Top News

geopolitics:
  - url: https://feeds.reuters.com/Reuters/worldNews
    name: Reuters World
  - url: https://feeds.bbci.co.uk/news/world/rss.xml
    name: BBC World
  - url: https://rss.nytimes.com/services/xml/rss/nyt/World.xml
    name: NYT World
```

The Query Builder decides which RSS categories to scan based on the topic. This is config-driven, not hardcoded.

#### Your AYR Keyword Rotation Idea — ✅ Good but Phase 2+

You said: *"create different keywords from the prompt and rate them based on alphas they produce"*

This is exactly what the AYR (Alpha Yield Rate) system does in the definitive plan. But it's Phase 2+ because:
1. You need data first (run the pipeline 100+ times to have meaningful AYR scores)
2. The core pipeline must work before you optimize it
3. We track source quality from Day 1 (logging) but don't act on it until Phase 2

---

## Pre-Work: Archive v1 & Start Clean

> [!IMPORTANT]
> The current `d:\projects\Apps\TrueBrief` contains v1 code. We archive it into a branch, then reset `main` to a clean state. **No code is lost.**

### Status: `[ ]` Not Started

### Steps

| # | Task | Status | Command/Action |
|---|------|--------|----------------|
| 0.1 | Commit all current v1 changes | `[ ]` | `git add -A && git commit -m "v1-final: archive before v2 rewrite"` |
| 0.2 | Create archive branch | `[ ]` | `git branch v1-archive` |
| 0.3 | Verify archive branch exists | `[ ]` | `git branch -a` (should show `v1-archive`) |
| 0.4 | Clean the working tree for v2 | `[ ]` | Delete all source files **except** `.git/`, `.gitignore`, `.env`, `.env.example` |
| 0.5 | Create v2 project skeleton (see Phase 0) | `[ ]` | I generate the folder structure |
| 0.6 | Initial v2 commit | `[ ]` | `git add -A && git commit -m "v2: project skeleton"` |

### How to Get v1 Code Later

```bash
git show v1-archive:src/truebrief/memory.py      # View any v1 file
git diff v1-archive -- src/truebrief/verifier.py  # Compare v1 vs v2
```

**V1 lives in the `v1-archive` branch forever.**

---

## Phase 0: Project Skeleton & Dev Environment

### Status: `[ ]` Not Started

### Goal
Clean professional project structure. Everything set up to build fast.

### v2 Folder Structure

```
TrueBrief/
├── .env                          # Secrets (never committed)
├── .env.example                  # Template for secrets
├── .gitignore
├── README.md                     # Project overview
├── pyproject.toml                # Modern Python packaging (replaces setup.py)
├── requirements.txt              # Pinned dependencies
│
├── config/
│   ├── settings.py               # Central config (env vars, LLM config, defaults)
│   ├── routing_rules.yaml        # Source routing config
│   └── rss_feeds.yaml            # Curated RSS feed database
│
├── src/
│   └── truebrief/
│       ├── __init__.py
│       ├── main.py               # Entry point
│       │
│       ├── llm/                  # LLM abstraction layer
│       │   ├── __init__.py
│       │   └── client.py         # Multi-provider LLM client
│       │
│       ├── models/               # Data models (dataclasses/Pydantic)
│       │   ├── __init__.py
│       │   ├── article.py        # RawArticle, ProcessedArticle
│       │   ├── alpha.py          # Alpha (fact), AlphaDecision
│       │   ├── topic.py          # Topic, TopicSchedule
│       │   └── brief.py          # Brief, BriefSection
│       │
│       ├── collector/            # Pillar 1: Ingestion
│       │   ├── __init__.py
│       │   ├── base.py           # SourceLayer ABC
│       │   ├── query_builder.py  # Topic → search queries (LLM)
│       │   ├── rss_layer.py      # Direct RSS feeds (PRIMARY)
│       │   ├── tavily_layer.py   # Tavily API (SECONDARY)
│       │   └── extractor.py      # trafilatura article extraction
│       │
│       ├── harvester/            # Pillar 2: Intelligence
│       │   ├── __init__.py
│       │   └── harvester.py      # Article → Alphas (LLM)
│       │
│       ├── ledger/               # Pillar 3: Memory
│       │   ├── __init__.py
│       │   ├── database.py       # Supabase/PostgreSQL connection & schema
│       │   └── vector_store.py   # pgvector operations
│       │
│       ├── arbiter/              # Pillar 4: Judge
│       │   ├── __init__.py
│       │   └── arbiter.py        # Delta detection (fast-path + LLM)
│       │
│       ├── briefer/              # Pillar 5: Output
│       │   ├── __init__.py
│       │   └── briefer.py        # Generate clean reports
│       │
│       ├── pipeline/             # Orchestration
│       │   ├── __init__.py
│       │   └── runner.py         # Full pipeline: collect→harvest→judge→brief
│       │
│       └── api/                  # FastAPI server
│           ├── __init__.py
│           ├── server.py         # FastAPI app setup
│           └── routes.py         # API endpoints
│
├── frontend/                     # Next.js app (Phase 3)
│   └── (created later with npx)
│
├── tests/
│   ├── __init__.py
│   ├── test_collector.py
│   ├── test_harvester.py
│   ├── test_arbiter.py
│   └── test_pipeline.py
│
├── scripts/
│   └── run_pipeline.py           # CLI to trigger pipeline manually
│
└── docs/
    └── architecture.md           # Living architecture doc
```

### Tasks

| # | Task | Status |
|---|------|--------|
| 0.1 | Create folder structure above | `[ ]` |
| 0.2 | Write `pyproject.toml` with metadata | `[ ]` |
| 0.3 | Write `requirements.txt` with pinned deps | `[ ]` |
| 0.4 | Write `config/settings.py` (env-based config + LLM config) | `[ ]` |
| 0.5 | Write LLM abstraction layer (`llm/client.py`) | `[ ]` |
| 0.6 | Write data models in `models/` | `[ ]` |
| 0.7 | Write `config/rss_feeds.yaml` (curated feed database) | `[ ]` |
| 0.8 | Write `.gitignore` (Python, env, __pycache__, data/) | `[ ]` |
| 0.9 | Write `README.md` | `[ ]` |
| 0.10 | Set up virtual environment & install deps | `[ ]` |
| 0.11 | Get Supabase connection string → put in `.env` | `[ ]` |
| 0.12 | Sign up for Tavily API → put key in `.env` | `[ ]` |
| 0.13 | Verify: `python -c "from truebrief.models.alpha import Alpha"` works | `[ ]` |
| 0.14 | Git commit: `"v2: project skeleton with models and config"` | `[ ]` |

### v2 Dependencies (requirements.txt)

```
# Core
fastapi>=0.115.0
uvicorn>=0.34.0
pydantic>=2.10.0
python-dotenv>=1.0.0
pyyaml>=6.0.0

# LLM — Gemini (primary for prototype)
google-generativeai>=0.8.0

# Collector
trafilatura>=2.0.0
feedparser>=6.0.0
httpx>=0.28.0
tavily-python>=0.5.0

# Ledger (Supabase/PostgreSQL)
supabase>=2.0.0
pgvector>=0.3.0

# Scheduler (Phase 2)
# celery>=5.4.0
# redis>=5.2.0

# Testing
pytest>=8.0.0
pytest-asyncio>=0.25.0
```

> [!NOTE]
> **Key changes from v1:**  
> - `qdrant-client` → Supabase + `pgvector` (cloud, zero maintenance)  
> - `crawl4ai` → `trafilatura` (simpler, no browser needed)  
> - `spacy` → removed (LLM replaces NLP sentence splitting)  
> - `duckduckgo_search` / `googlesearch` → `tavily-python` + `feedparser` (reliable, no blocking)  
> - Added `google-generativeai` as primary LLM (free tier)  
> - Added `pyyaml` for config files  

---

## Phase 1: Core MVP (Collector + Harvester + Memory + Basic Delta)

### Status: `[ ]` Not Started

### Goal
One topic → collect articles → extract facts → detect duplicates → show results.  
**No frontend, no scheduling, no payments.** Just the brain working end-to-end.

---

### Step 1.0: LLM Abstraction Layer

| Detail | Value |
|--------|-------|
| **What** | Thin wrapper that lets any pipeline step call any LLM provider via config |
| **File** | `src/truebrief/llm/client.py` |
| **Status** | `[ ]` |

#### Design
```python
class LLMClient:
    """Call any LLM via config. Switch providers by changing settings.py."""
    
    def call(self, step_name: str, prompt: str, json_mode: bool = False) -> str:
        """step_name maps to LLM_CONFIG entry (e.g., 'harvester', 'arbiter')"""
        config = LLM_CONFIG[step_name]
        if config["provider"] == "gemini":
            return self._call_gemini(config["model"], prompt)
        elif config["provider"] == "openai":
            return self._call_openai(config["model"], prompt)
        # Add more providers here
```

#### Acceptance Criteria
- `client.call("harvester", "Extract facts from...")` → returns LLM response string
- Config-driven: change `settings.py` → different model, zero code changes
- Handles rate limits, retries, and failures gracefully

---

### Step 1.1: Collector — Query Builder

| Detail | Value |
|--------|-------|
| **What** | LLM takes a user topic → produces search queries + RSS category matching |
| **File** | `src/truebrief/collector/query_builder.py` |
| **Status** | `[ ]` |

#### 📦 V1 REUSE MAP
| What to reuse | v1 file | What's valuable |
|--------------|---------|-----------------|
| Intent analysis prompt | [librarian.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/librarian.py#L22-L65) | The `_analyze_intent()` prompt structure. Adapt JSON output to match definitive plan. |
| Garbage input rejection | [librarian.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/librarian.py#L36-L56) | The "REJECT gibberish" pattern. |

#### Acceptance Criteria
- `query_builder.build("TSMC semiconductor")` → returns `SearchQuery` with primary_query, alt_queries, rss_categories, date_filter
- Garbage input like `"test123"` returns a rejection
- Matches topic to RSS categories from `rss_feeds.yaml`

---

### Step 1.2: Collector — Direct RSS Plugin (PRIMARY)

| Detail | Value |
|--------|-------|
| **What** | Scan curated RSS feeds matching the topic's category, return new articles |
| **File** | `src/truebrief/collector/rss_layer.py` |
| **Status** | `[ ]` |

#### 📦 V1 REUSE MAP
| What to reuse | v1 file | What's valuable |
|--------------|---------|-----------------|
| RSS parsing loop | [radar.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/radar.py#L13-L58) | The `feedparser` scan pattern, seen_urls dedup. Adapt to return `RawArticle`. |

#### Acceptance Criteria
- `RSSLayer().search(query)` → returns `List[RawArticle]` from matched RSS feeds
- Implements `SourceLayer` ABC
- URLs are direct article links (no redirects to decode)
- Handles broken/empty feeds gracefully

---

### Step 1.3: Collector — Tavily Plugin (SECONDARY)

| Detail | Value |
|--------|-------|
| **What** | Search Tavily API for topic-specific articles (fills gaps RSS doesn't cover) |
| **File** | `src/truebrief/collector/tavily_layer.py` |
| **Status** | `[ ]` |

#### Key Facts About Tavily
- 1,000 free credits/month (basic search = 1 credit, advanced = 2 credits)
- **Returns clean extracted text** — no need for separate article scraping for Tavily results
- Direct original URLs
- Reliable API with clear documentation

#### Acceptance Criteria
- `TavilyLayer().search(query)` → returns `List[RawArticle]` with full article text
- Handles missing API key gracefully (skip, don't crash)
- Tracks credit usage in logs

---

### Step 1.4: Collector — Article Extractor

| Detail | Value |
|--------|-------|
| **What** | For RSS articles (which only give URLs), fetch and extract clean text |
| **File** | `src/truebrief/collector/extractor.py` |
| **Status** | `[ ]` |

#### 📦 V1 REUSE MAP
| What to reuse | v1 file | What's valuable |
|--------------|---------|-----------------|
| Date extraction from HTML | [sniper.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/sniper.py#L68-L87) | The `<meta>` tag and `<time>` tag date extraction. trafilatura does this automatically but good fallback. |
| Bot-detection check | [sniper.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/sniper.py#L48-L50) | The "attention required" / "cloudflare" check. Keep as quality filter. |

#### Note: Tavily results skip the extractor
Tavily already returns clean text. Only RSS results need extraction via trafilatura. This saves processing and is why the two-source combo is efficient.

#### Acceptance Criteria
- `extract("https://reuters.com/some-article")` → returns `RawArticle` with full clean text
- Caches by URL hash — never fetches same URL twice
- Handles timeouts and failures gracefully
- Detects bot-blocked pages and marks as failed

---

### Step 1.5: Harvester — Fact Extraction

| Detail | Value |
|--------|-------|
| **What** | LLM reads article text → extracts atomic facts (Alphas) |
| **File** | `src/truebrief/harvester/harvester.py` |
| **Status** | `[ ]` |

#### 📦 V1 REUSE MAP
| What to reuse | v1 file | What's valuable |
|--------------|---------|-----------------|
| Batch extraction prompt | [verifier.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/verifier.py#L62-L140) | The `extract_alphas_batch()` prompt — metric preservation, noise filter, conflict detection. **Adapt output to JSON format.** |
| Cross-examination logic | [verifier.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/verifier.py#L142-L200) | Conflict detection concept. Simplify implementation. |
| Temporal normalization | [context_verifier.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/context_verifier.py#L1-L100) | Temporal bounding box prompt. Incorporate into Harvester date extraction. |

#### Acceptance Criteria
- `harvester.extract(article_text, published_date)` → returns `List[Alpha]`
- Output includes: alpha_text, entities, event_date, context, confidence
- Relative dates normalized to absolute dates
- Confidence < 0.6 facts dropped

---

### Step 1.6: Ledger — Supabase Schema & Vector Store

| Detail | Value |
|--------|-------|
| **What** | Supabase PostgreSQL + pgvector for users, topics, facts, briefs |
| **Files** | `src/truebrief/ledger/database.py`, `src/truebrief/ledger/vector_store.py` |
| **Status** | `[ ]` |

#### 📦 V1 REUSE MAP
| What to reuse | v1 file | What's valuable |
|--------------|---------|-----------------|
| Vector operations | [memory.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/memory.py#L14-L96) | `add_fact()`, `is_novel()`, `get_all_facts()` interface. Same logic, Supabase backend. |
| Topic CRUD | [topics.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/topics.py#L5-L60) | CRUD pattern. Replace JSON file with PostgreSQL. |
| Similarity threshold | [memory.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/memory.py#L12) | `SIMILARITY_THRESHOLD = 0.85` — validated in v1 benchmarks. |

#### Acceptance Criteria
- Supabase tables created: users, topics, known_facts (with vector column), briefs
- Can insert a fact with embedding and search by cosine similarity
- Test: insert fact → search near-duplicate → get match with score > 0.85

---

### Step 1.7: Arbiter — Simple Delta Detection

| Detail | Value |
|--------|-------|
| **What** | For each new Alpha: NEW or DUPLICATE? (simple version) |
| **File** | `src/truebrief/arbiter/arbiter.py` |
| **Status** | `[ ]` |

#### 📦 V1 REUSE MAP
| What to reuse | v1 file | What's valuable |
|--------------|---------|-----------------|
| Novelty checking | [engine.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/engine.py#L82-L114) | `NoveltyFilter.analyze()` pattern |
| Temporal overlap math | [engine.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/engine.py#L134-L166) | Overlap ratio calculation — Phase 2 |
| Time Detective | [context_verifier.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/context_verifier.py#L33-L67) | Temporal analysis prompt — Phase 2 |

#### Phase 1 Scope (Simple)
- Score > 0.90 → DUPLICATE (auto-merge)
- No matches → NEW (auto-add)
- Everything else → NEW (err on side of including too much)

#### Acceptance Criteria
- `arbiter.judge(alpha, topic_id)` → returns `AlphaDecision(NEW | DUPLICATE)`
- Same fact twice → second is DUPLICATE
- New fact → NEW

---

### Step 1.8: Briefer — Simple Report Generation

| Detail | Value |
|--------|-------|
| **What** | Take new Alphas → format clean brief |
| **File** | `src/truebrief/briefer/briefer.py` |
| **Status** | `[ ]` |

#### 📦 V1 REUSE MAP
None directly — v1 displayed raw alphas. Brief format spec is in [definitive plan](file:///C:/Users/user/.gemini/antigravity/brain/fcdcef8e-4468-4487-83f0-1dcf93b114aa/truebrief_definitive_plan_v2.md) (Brief Format section).

#### Acceptance Criteria
- `briefer.generate(new_alphas, topic)` → formatted brief string
- Separates NEW vs UPDATE sections
- Includes source attribution

---

### Step 1.9: Pipeline Runner — End-to-End

| Detail | Value |
|--------|-------|
| **What** | Wire all pillars: Topic → Collect → Harvest → Judge → Brief |
| **File** | `src/truebrief/pipeline/runner.py` |
| **Status** | `[ ]` |

#### 📦 V1 REUSE MAP
| What to reuse | v1 file | What's valuable |
|--------------|---------|-----------------|
| Pipeline orchestration | [manager.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/manager.py#L40-L103) | `scan_topic()` flow |
| Scan endpoint logic | [router.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/router.py#L41-L152) | Pipeline in API form |

#### Acceptance Criteria
- `python scripts/run_pipeline.py "TSMC semiconductor"` → prints brief with real facts
- End-to-end: real API calls, real LLM, real database
- Pipeline completes in < 60 seconds for single topic

---

### Step 1.10: API Server — Basic Endpoints

| Detail | Value |
|--------|-------|
| **What** | FastAPI with topic CRUD and scan triggers |
| **Files** | `src/truebrief/api/server.py`, `src/truebrief/api/routes.py` |
| **Status** | `[ ]` |

#### 📦 V1 REUSE MAP
| What to reuse | v1 file | What's valuable |
|--------------|---------|-----------------|
| FastAPI setup | [router.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/router.py#L1-L20) | App setup, CORS config |
| API endpoints | [router.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/router.py#L24-L211) | `/alphas`, `/topics`, `/scan` concepts |

#### Phase 1 Endpoints
| Method | Path | What |
|--------|------|------|
| `POST` | `/api/v1/topics` | Create topic |
| `GET` | `/api/v1/topics` | List topics |
| `GET` | `/api/v1/topics/{id}` | Get topic details |
| `DELETE` | `/api/v1/topics/{id}` | Delete topic |
| `POST` | `/api/v1/topics/{id}/scan` | Trigger scan |
| `GET` | `/api/v1/topics/{id}/briefs` | Get briefs |
| `GET` | `/api/v1/briefs/{id}` | Get specific brief |

#### Acceptance Criteria
- Server starts with `uvicorn`
- All endpoints return proper JSON
- Auto-docs at `/docs`

---

### Step 1.11: Integration Test — Master Benchmark v2

| Detail | Value |
|--------|-------|
| **What** | Run pipeline against diverse topics, validate quality |
| **File** | `tests/test_pipeline.py` |
| **Status** | `[ ]` |

#### 📦 V1 REUSE MAP
| What to reuse | v1 file | What's valuable |
|--------------|---------|-----------------|
| Test prompts | [master_benchmark.py](file:///d:/projects/Apps/TrueBrief/tests/master_benchmark.py#L18-L61) | 21 diverse prompts across 7 categories — **GOLD** |
| Benchmark runner | [master_benchmark.py](file:///d:/projects/Apps/TrueBrief/tests/master_benchmark.py#L63-L133) | Run loop, timing, error classification |
| Previous results | [master_benchmark_results.json](file:///d:/projects/Apps/TrueBrief/tests/master_benchmark_results.json) | Compare v2 vs v1 |

---

## Phase 2: Delta Engine + Scheduling (after Phase 1 complete)

### Status: `[ ]` Not Started

| # | Task | Status | Key v1 Reference |
|---|------|--------|-------------------|
| 2.1 | Full Arbiter: Fast-path (>0.97 auto-merge, zero matches auto-new) | `[ ]` | [engine.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/engine.py#L82-L114) |
| 2.2 | Judge LLM prompt (MERGE/UPDATE/NEW) | `[ ]` | [context_verifier.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/context_verifier.py#L33-L67) |
| 2.3 | Temporal overlap math engine | `[ ]` | [engine.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/engine.py#L134-L166) |
| 2.4 | Celery + Redis for background tasks | `[ ]` | New |
| 2.5 | Celery Beat scheduler | `[ ]` | [scheduler.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/scheduler.py) |
| 2.6 | Empty brief suppression | `[ ]` | New |
| 2.7 | Brief history storage | `[ ]` | New |
| 2.8 | Source quality logging (foundation for AYR) | `[ ]` | New |
| 2.9 | Google News RSS as 3rd source (with decoder) | `[ ]` | New |
| 2.10 | Dynamic keyword rotation for sources | `[ ]` | Your idea — track which keywords produce best alphas |
| 2.11 | Shared topic infrastructure | `[ ]` | New |

---

## Phase 3: Frontend + Monetization (after Phase 2)

### Status: `[ ]` Not Started

### Goal
A product people can use and will pay for.

| # | Task | Status | Notes |
|---|------|--------|-------|
| 3.1 | Story Nodes: group related facts into evolving stories | `[ ]` | Adds parent-child structure to facts |
| 3.2 | Dual vectors: alpha_embedding + summary_embedding (still pgvector) | `[ ]` | Enables story-level vs fact-level matching |
| 3.3 | Recursive summary updates when stories evolve | `[ ]` | Rewrite story node summary on each UPDATE |
| 3.4 | Stripe integration: subscription management | `[ ]` | Free / Pro / Power tier |
| 3.5 | Tier enforcement: topic limits, speed, source access | `[ ]` | Based on Stripe plan |
| 3.6 | Next.js frontend skeleton (`npx create-next-app`) | `[ ]` | Phase 3 is when we build the UI |
| 3.7 | Auth via Clerk or NextAuth.js | `[ ]` | Never build auth yourself |
| 3.8 | Topic management UI (add/remove/list) | `[ ]` | Core product interaction |
| 3.9 | Brief display page (the core product) | `[ ]` | NEW / UPDATE / No changes sections |
| 3.10 | Brief history page | `[ ]` | See all past briefs per topic |
| 3.11 | Landing page with value proposition | `[ ]` | SEO + conversion |
| 3.12 | Onboarding flow (explain product, suggest topics) | `[ ]` | Reduces drop-off |
| 3.13 | "Time saved" metric per user | `[ ]` | Engagement + conversion lever |
| 3.14 | Public brief sharing pages | `[ ]` | Viral growth + SEO |
| 3.15 | Email digest delivery (daily/weekly, user config) | `[ ]` | SendGrid or Resend |
| 3.16 | Web push notifications (PWA) | `[ ]` | Browser push |
| 3.17 | Mobile-responsive design (PWA-ready) | `[ ]` | No native app yet |
| 3.18 | Rate limiting and abuse prevention | `[ ]` | Protect API from hammering |
| 3.19 | Brave Search + Exa as Phase 3+ source plugins | `[ ]` | Adds broader web coverage |
| 3.20 | Deploy frontend to Vercel, connect to Railway backend | `[ ]` | Full production stack |

---

## Phase 4: B2B API (after Phase 3)

### Status: `[ ]` Not Started

### Goal
Revenue from business customers.

| # | Task | Status |
|---|------|--------|
| 4.1 | Public REST API with API key auth | `[ ]` |
| 4.2 | API docs (auto-generated from FastAPI + polished) | `[ ]` |
| 4.3 | `GET /api/v1/topics/{id}/delta?since={timestamp}` | `[ ]` |
| 4.4 | `GET /api/v1/topics/{id}/nodes` (full story graph) | `[ ]` |
| 4.5 | `POST /api/v1/webhooks` (register delivery endpoint) | `[ ]` |
| 4.6 | Usage tracking and per-call billing | `[ ]` |
| 4.7 | Webhook delivery (push briefs to client systems) | `[ ]` |
| 4.8 | Admin dashboard for B2B accounts | `[ ]` |
| 4.9 | Rate limits by tier (Business: 1K/day, Enterprise: unlimited) | `[ ]` |
| 4.10 | API versioning (`/api/v1/`), deprecation headers | `[ ]` |

---

## Phase 5: Scale + Moat (Month 6-12)

### Status: `[ ]` Not Started

| # | Task | Status |
|---|------|--------|
| 5.1 | Plugin architecture: config-driven component swapping (A/B test harvesters) | `[ ]` |
| 5.2 | AYR shared across users = system-level source reputation network | `[ ]` |
| 5.3 | User feedback loop: thumbs up/down → improve relevance scoring | `[ ]` |
| 5.4 | Contradiction detection: two sources disagree → flag for user | `[ ]` |
| 5.5 | Multi-language support (multilingual embeddings) | `[ ]` |
| 5.6 | Specialized source plugins: SEC EDGAR, PubMed, FDA, EU regulatory | `[ ]` |
| 5.7 | Team/organization accounts | `[ ]` |
| 5.8 | White-label options for B2B (custom branding, domain) | `[ ]` |
| 5.9 | Mobile app (React Native) — only if user demand justifies it | `[ ]` |

---

## Phase 6: Domain Intelligence Pipelines (Year 2+)

### Status: `[ ]` Not Started

| # | Task | Status |
|---|------|--------|
| 6.1 | Domain router: LLM classifies prompt → domain (finance / legal / medical / geopolitics) | `[ ]` |
| 6.2 | Finance pipeline: SEC filings, ticker tracking, earnings precision | `[ ]` |
| 6.3 | Legal pipeline: court dockets, citation-aware facts | `[ ]` |
| 6.4 | Medical pipeline: PubMed, clinical trials, drug approvals | `[ ]` |
| 6.5 | Fine-tuned small classifier to replace LLM router (near-zero cost, <10ms) | `[ ]` |
| 6.6 | Feedback loop: user says "missed finance context" → router adjusts | `[ ]` |

---

## V1 → V2 Complete Reuse Reference

| v2 Component | v1 File | What's Valuable | What Changes |
|-------------|---------|-----------------|-------------|
| LLM Client | New | — | New abstraction layer |
| Query Builder | `librarian.py` | Intent prompt, garbage rejection | Gemini via LLM client, match RSS categories |
| RSS Layer | `radar.py` | feedparser scan loop | Returns `RawArticle`, curated feed database |
| Tavily Layer | New | — | New (replaces DuckDuckGo/Google scraping) |
| Article Extractor | `sniper.py` | Date extraction, bot detection | trafilatura replaces Crawl4AI |
| Harvester | `verifier.py` | Batch extraction prompt, metric preservation | JSON output, temporal normalization built-in |
| Vector Store | `memory.py` | add_fact, is_novel, similarity threshold | Supabase replaces Qdrant |
| Arbiter | `engine.py` + `context_verifier.py` | NoveltyFilter, temporal math, Time Detective | Cleaner, proper enum decisions |
| Pipeline | `manager.py` + `router.py` | scan_topic flow | Async, Celery later |
| Topics CRUD | `topics.py` | CRUD pattern | PostgreSQL replaces JSON file |
| API | `router.py` | FastAPI setup, endpoints | Versioned `/api/v1/` |
| Benchmarks | `tests/master_benchmark.py` | 21 test prompts, runner pattern | pytest, automated comparison |

---

## Professional Practices

### Git Workflow
```bash
# Feature branches for big changes
git checkout -b feat/collector-rss-layer
# ... work ...
git commit -m "feat(collector): add RSS layer with curated feed database"
git checkout main && git merge feat/collector-rss-layer

# Direct commits for small fixes
git commit -m "fix(arbiter): correct similarity threshold to 0.90"
```

### Commit Message Format
```
type(scope): short description
Types: feat, fix, refactor, test, docs, chore
Scope: collector, harvester, ledger, arbiter, briefer, api, pipeline, llm
```

---

## API Keys Needed

| Key | Where to get it | When needed | Cost |
|-----|----------------|-------------|------|
| `GOOGLE_API_KEY` | [Google AI Studio](https://aistudio.google.com/) | Phase 0 | Free (1,500 req/day) |
| `TAVILY_API_KEY` | [tavily.com](https://tavily.com) | Phase 0 | Free (1,000 credits/month) |
| `SUPABASE_URL` + `SUPABASE_KEY` | Your Supabase dashboard | Phase 0 | Free (500MB) |
| News API keys (Brave, Exa) | Later | Phase 3+ | Pay-per-use |
