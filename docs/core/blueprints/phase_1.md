# Phase 1: Core MVP
> 📍 Read FIRST: [.ai/BOOT.md](file:///d:/projects/Apps/TrueBrief/.ai/BOOT.md)
> 📐 Status: `[x]` Complete

### Goal
One topic -> collect articles -> extract facts -> detect duplicates -> show results.  
**No frontend, no scheduling, no payments.** Just the brain working end-to-end.

---

### Step Summary
| # | Task | Status | PLAN | BUILD | UNIT | INTG |
|---|------|--------|---|---|---|---|
| 1.0 | LLM Abstraction Layer | [x] | [x] | [x] | [x] | [x] |
| 1.1 | Collector -- Query Builder | [x] | [x] | [x] | [x] | [x] |
| 1.2 | Collector -- Direct RSS Plugin | [x] | [x] | [x] | [x] | [x] |
| 1.3 | Collector -- Tavily Plugin | [x] | [x] | [x] | [x] | [x] |
| 1.4 | Collector -- Article Extractor | [x] | [x] | [x] | [x] | [x] |
| 1.5 | Harvester -- Fact Extraction | [x] | [x] | [x] | [x] | [x] |
| 1.6 | Ledger -- Supabase & Vector Store | [x] | [x] | [x] | [x] | [x] |
| 1.7 | Arbiter -- Simple Delta Detection | [x] | [x] | [x] | [x] | [x] |
| 1.8 | Briefer -- Simple Report Gen | [x] | [x] | [x] | [x] | [x] |
| 1.9 | Pipeline Runner -- End-to-End | [x] | [x] | [x] | [x] | [x] |
| 1.10 | API Server -- Basic Endpoints | [x] | [x] | [x] | [x] | [x] |
| 1.11 | Integration Test -- Benchmark v2 | [x] | [x] | [x] | [x] | [x] |

---

### Step 1.0: LLM Abstraction Layer

| Detail | Value |
|--------|-------|
| **What** | Thin wrapper that lets any pipeline step call any LLM provider via config |
| **File** | `src/truebrief/llm/client.py` |
| **Status** | `[x]` |

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
- `client.call("harvester", "Extract facts from...")` -> returns LLM response string
- Config-driven: change `settings.py` -> different model, zero code changes
- Handles rate limits, retries, and failures gracefully

---

### Step 1.1: Collector -- Query Builder

| Detail | Value |
|--------|-------|
| **What** | LLM takes a user topic -> produces search queries + RSS category matching |
| **File** | `src/truebrief/collector/query_builder.py` |
| **Status** | `[ ]` |

#### 🔍 V1 REUSE MAP
| What to reuse | v1 file | What's valuable |
|--------------|---------|-----------------|
| Intent analysis prompt | [librarian.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/librarian.py#L22-L65) | The `_analyze_intent()` prompt structure. Adapt JSON output to match definitive plan. |
| Garbage input rejection | [librarian.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/librarian.py#L36-L56) | The "REJECT gibberish" pattern. |

#### Acceptance Criteria
- `query_builder.build("TSMC semiconductor")` -> returns `SearchQuery` with primary_query, alt_queries, rss_categories, date_filter
- Garbage input like `"test123"` returns a rejection
- Matches topic to RSS categories from `rss_feeds.yaml`

---

### Step 1.2: Collector -- Direct RSS Plugin (PRIMARY)

| Detail | Value |
|--------|-------|
| **What** | Scan curated RSS feeds matching the topic's category, return new articles |
| **File** | `src/truebrief/collector/rss_layer.py` |
| **Status** | `[ ]` |

#### 🔍 V1 REUSE MAP
| What to reuse | v1 file | What's valuable |
|--------------|---------|-----------------|
| RSS parsing loop | [radar.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/radar.py#L13-L58) | The `feedparser` scan pattern, seen_urls dedup. Adapt to return `RawArticle`. |

#### Acceptance Criteria
- `RSSLayer().search(query)` -> returns `List[RawArticle]` from matched RSS feeds
- Implements `SourceLayer` ABC
- URLs are direct article links (no redirects to decode)
- Handles broken/empty feeds gracefully

---

### Step 1.3: Collector -- Tavily Plugin (SECONDARY)

| Detail | Value |
|--------|-------|
| **What** | Search Tavily API for topic-specific articles (fills gaps RSS doesn't cover) |
| **File** | `src/truebrief/collector/tavily_layer.py` |
| **Status** | `[ ]` |

#### Key Facts About Tavily
- 1,000 free credits/month (basic search = 1 credit, advanced = 2 credits)
- **Returns clean extracted text** -- no need for separate article scraping for Tavily results
- Direct original URLs
- Reliable API with clear documentation

#### Acceptance Criteria
- `TavilyLayer().search(query)` -> returns `List[RawArticle]` with full article text
- Handles missing API key gracefully (skip, don't crash)
- Tracks credit usage in logs

---

### Step 1.4: Collector -- Article Extractor

| Detail | Value |
|--------|-------|
| **What** | For RSS articles (which only give URLs), fetch and extract clean text |
| **File** | `src/truebrief/collector/extractor.py` |
| **Status** | `[ ]` |

#### 🔍 V1 REUSE MAP
| What to reuse | v1 file | What's valuable |
|--------------|---------|-----------------|
| Date extraction from HTML | [sniper.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/sniper.py#L68-L87) | The `<meta>` tag and `<time>` tag date extraction. trafilatura does this automatically but good fallback. |
| Bot-detection check | [sniper.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/sniper.py#L48-L50) | The "attention required" / "cloudflare" check. Keep as quality filter. |

#### Note: Tavily results skip the extractor
Tavily already returns clean text. Only RSS results need extraction via trafilatura. This saves processing and is why the two-source combo is efficient.

#### Acceptance Criteria
- `extract("https://reuters.com/some-article")` -> returns `RawArticle` with full clean text
- Caches by URL hash -- never fetches same URL twice
- Handles timeouts and failures gracefully
- Detects bot-blocked pages and marks as failed

---

### Step 1.5: Harvester -- Fact Extraction

| Detail | Value |
|--------|-------|
| **What** | LLM reads article text -> extracts atomic facts (Alphas) |
| **File** | `src/truebrief/harvester/harvester.py` |
| **Status** | `[ ]` |

#### 🔍 V1 REUSE MAP
| What to reuse | v1 file | What's valuable |
|--------------|---------|-----------------|
| Batch extraction prompt | [verifier.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/verifier.py#L62-L140) | The `extract_alphas_batch()` prompt -- metric preservation, noise filter, conflict detection. **Adapt output to JSON format.** |
| Cross-examination logic | [verifier.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/verifier.py#L142-L200) | Conflict detection concept. Simplify implementation. |
| Temporal normalization | [context_verifier.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/context_verifier.py#L1-L100) | Temporal bounding box prompt. Incorporate into Harvester date extraction. |

#### Acceptance Criteria
- `harvester.extract(article_text, published_date)` -> returns `List[Alpha]`
- Output includes: alpha_text, entities, event_date, context, confidence
- Relative dates normalized to absolute dates
- Confidence < 0.6 facts dropped

---

### Step 1.6: Ledger -- Supabase Schema & Vector Store

| Detail | Value |
|--------|-------|
| **What** | Supabase PostgreSQL + pgvector for users, topics, facts, briefs |
| **Files** | `src/truebrief/ledger/database.py`, `src/truebrief/ledger/vector_store.py` |
| **Status** | `[ ]` |

#### 🔍 V1 REUSE MAP
| What to reuse | v1 file | What's valuable |
|--------------|---------|-----------------|
| Vector operations | [memory.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/memory.py#L14-L96) | `add_fact()`, `is_novel()`, `get_all_facts()` interface. Same logic, Supabase backend. |
| Topic CRUD | [topics.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/topics.py#L5-L60) | CRUD pattern. Replace JSON file with PostgreSQL. |
| Similarity threshold | [memory.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/memory.py#L12) | `SIMILARITY_THRESHOLD = 0.85` -- validated in v1 benchmarks. |

#### Acceptance Criteria
- Supabase tables created: users, topics, known_facts (with vector column), briefs
- Can insert a fact with embedding and search by cosine similarity
- Test: insert fact -> search near-duplicate -> get match with score > 0.85

---

### Step 1.7: Arbiter -- Simple Delta Detection

| Detail | Value |
|--------|-------|
| **What** | For each new Alpha: NEW or DUPLICATE? (simple version) |
| **File** | `src/truebrief/arbiter/arbiter.py` |
| **Status** | `[ ]` |

#### 🔍 V1 REUSE MAP
| What to reuse | v1 file | What's valuable |
|--------------|---------|-----------------|
| Novelty checking | [engine.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/engine.py#L82-L114) | `NoveltyFilter.analyze()` pattern |
| Temporal overlap math | [engine.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/engine.py#L134-L166) | Overlap ratio calculation -- Phase 2 |
| Time Detective | [context_verifier.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/context_verifier.py#L33-L67) | Temporal analysis prompt -- Phase 2 |

#### Phase 1 Scope (Simple)
- Score > 0.90 -> DUPLICATE (auto-merge)
- No matches -> NEW (auto-add)
- Everything else -> NEW (err on side of including too much)

#### Acceptance Criteria
- `arbiter.judge(alpha, topic_id)` -> returns `AlphaDecision(NEW | DUPLICATE)`
- Same fact twice -> second is DUPLICATE
- New fact -> NEW

---

### Step 1.8: Briefer -- Simple Report Generation

| Detail | Value |
|--------|-------|
| **What** | Take new Alphas -> format clean brief |
| **File** | `src/truebrief/briefer/briefer.py` |
| **Status** | `[ ]` |

#### 🔍 V1 REUSE MAP
None directly -- v1 displayed raw alphas. Brief format spec is in [definitive plan](file:///C:/Users/user/.gemini/antigravity/brain/fcdcef8e-4468-4487-83f0-1dcf93b114aa/truebrief_definitive_plan_v2.md) (Brief Format section).

#### Acceptance Criteria
- `briefer.generate(new_alphas, topic)` -> formatted brief string
- Separates NEW vs UPDATE sections
- Includes source attribution

---

### Step 1.9: Pipeline Runner -- End-to-End

| Detail | Value |
|--------|-------|
| **What** | Wire all pillars: Topic -> Collect -> Harvest -> Judge -> Brief |
| **File** | `src/truebrief/pipeline/runner.py` |
| **Status** | `[ ]` |

#### 🔍 V1 REUSE MAP
| What to reuse | v1 file | What's valuable |
|--------------|---------|-----------------|
| Pipeline orchestration | [manager.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/manager.py#L40-L103) | `scan_topic()` flow |
| Scan endpoint logic | [router.py](file:///d:/projects/Apps/TrueBrief/src/truebrief/router.py#L41-L152) | Pipeline in API form |

#### Acceptance Criteria
- `python scripts/run_pipeline.py "TSMC semiconductor"` -> prints brief with real facts
- End-to-end: real API calls, real LLM, real database
- Pipeline completes in < 60 seconds for single topic

---

### Step 1.10: API Server -- Basic Endpoints

| Detail | Value |
|--------|-------|
| **What** | FastAPI with topic CRUD and scan triggers |
| **Files** | `src/truebrief/api/server.py`, `src/truebrief/api/routes.py` |
| **Status** | `[ ]` |

#### 🔍 V1 REUSE MAP
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

### Step 1.11: Integration Test -- Master Benchmark v2

| Detail | Value |
|--------|-------|
| **What** | Run pipeline against diverse topics, validate quality |
| **File** | `tests/test_pipeline.py` |
| **Status** | `[ ]` |

#### 🔍 V1 REUSE MAP
| What to reuse | v1 file | What's valuable |
|--------------|---------|-----------------|
| Test prompts | [master_benchmark.py](file:///d:/projects/Apps/TrueBrief/tests/master_benchmark.py#L18-L61) | 21 diverse prompts across 7 categories -- **GOLD** |
| Benchmark runner | [master_benchmark.py](file:///d:/projects/Apps/TrueBrief/tests/master_benchmark.py#L63-L133) | Run loop, timing, error classification |
| Previous results | [master_benchmark_results.json](file:///d:/projects/Apps/TrueBrief/tests/master_benchmark_results.json) | Compare v2 vs v1 |

---



