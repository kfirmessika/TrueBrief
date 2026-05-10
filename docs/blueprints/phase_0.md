# Phase 0: Project Skeleton & Dev Environment
> 📍 Read FIRST: [.ai/BOOT.md](file:///d:/projects/Apps/TrueBrief/.ai/BOOT.md)
> 📐 Status: `[x]` Complete

### Goal
Clean professional project structure. Everything set up to build fast.

### v2 Folder Structure

```
TrueBrief/
    .env                          # Secrets (never committed)
    .env.example                  # Template for secrets
    .gitignore
    README.md                     # Project overview
    pyproject.toml                # Modern Python packaging (replaces setup.py)
    requirements.txt              # Pinned dependencies
|
    config/
|       settings.py               # Central config (env vars, LLM config, defaults)
|       routing_rules.yaml        # Source routing config
|   L   rss_feeds.yaml            # Curated RSS feed database
|
    src/
|   L   truebrief/
|           __init__.py
|           main.py               # Entry point
|       |
|           llm/                  # LLM abstraction layer
|       |       __init__.py
|       |   L   client.py         # Multi-provider LLM client
|       |
|           models/               # Data models (dataclasses/Pydantic)
|       |       __init__.py
|       |       article.py        # RawArticle, ProcessedArticle
|       |       alpha.py          # Alpha (fact), AlphaDecision
|       |       topic.py          # Topic, TopicSchedule
|       |   L   brief.py          # Brief, BriefSection
|       |
|           collector/            # Pillar 1: Ingestion
|       |       __init__.py
|       |       base.py           # SourceLayer ABC
|       |       query_builder.py  # Topic -> search queries (LLM)
|       |       rss_layer.py      # Direct RSS feeds (PRIMARY)
|       |       tavily_layer.py   # Tavily API (SECONDARY)
|       |   L   extractor.py      # trafilatura article extraction
|       |
|           harvester/            # Pillar 2: Intelligence
|       |       __init__.py
|       |   L   harvester.py      # Article -> Alphas (LLM)
|       |
|           ledger/               # Pillar 3: Memory
|       |       __init__.py
|       |       database.py       # Supabase/PostgreSQL connection & schema
|       |   L   vector_store.py   # pgvector operations
|       |
|           arbiter/              # Pillar 4: Judge
|       |       __init__.py
|       |   L   arbiter.py        # Delta detection (fast-path + LLM)
|       |
|           briefer/              # Pillar 5: Output
|       |       __init__.py
|       |   L   briefer.py        # Generate clean reports
|       |
|           pipeline/             # Orchestration
|       |       __init__.py
|       |   L   runner.py         # Full pipeline: collect->harvest->judge->brief
|       |
|       L   api/                  # FastAPI server
|               __init__.py
|               server.py         # FastAPI app setup
|           L   routes.py         # API endpoints
|
    frontend/                     # Next.js app (Phase 3)
|   L   (created later with npx)
|
    tests/
|       __init__.py
|       test_collector.py
|       test_harvester.py
|       test_arbiter.py
|   L   test_pipeline.py
|
    scripts/
|   L   run_pipeline.py           # CLI to trigger pipeline manually
|
L   docs/
    L   architecture.md           # Living architecture doc
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
| 0.11 | Get Supabase connection string -> put in `.env` | `[ ]` |
| 0.12 | Sign up for Tavily API -> put key in `.env` | `[ ]` |
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

# LLM -- Gemini (primary for prototype)
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
> - `qdrant-client` -> Supabase + `pgvector` (cloud, zero maintenance)  
> - `crawl4ai` -> `trafilatura` (simpler, no browser needed)  
> - `spacy` -> removed (LLM replaces NLP sentence splitting)  
> - `duckduckgo_search` / `googlesearch` -> `tavily-python` + `feedparser` (reliable, no blocking)  
> - Added `google-generativeai` as primary LLM (free tier)  
> - Added `pyyaml` for config files  

---



