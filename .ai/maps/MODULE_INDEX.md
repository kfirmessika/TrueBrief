# Module Index
> **Purpose:** Detailed reference for each module. Read only when you need to understand specific module logic or dependencies.  
> **Last updated:** 2026-05-05 | **Updated by:** Gemini Flash

---

## llm
- **Purpose:** Provider-agnostic LLM interface.
- **Entry Point:** `llm/client.py` (`LLMClient`)
- **Key Logic:** Config-driven switching between Gemini (modern GenAI SDK) and OpenAI. Supports `call`, `embed`, and `embed_batch`.
- **Dependencies:** `config/settings.py`
- **Gotchas:** `json_mode` enforces JSON schema via LLM parameters.

## collector
- **Purpose:** Fetches content from the web and extracts clean text.
- **Key Files:** `extractor.py` (text cleaning), `query_builder.py` (search optimization).
- **Providers:** Tavily (AI Search), Google News, RSS feeds.
- **Dependencies:** `trafilatura` (for extraction), `tavily-python`.
- **Logic:** Uses `MMR` (Maximal Marginal Relevance) in the pipeline to select the top-5 diverse articles from candidate lists.

## harvester
- **Purpose:** Transforms long-form text into atomic facts (Alphas).
- **Key File:** `harvester.py`.
- **Logic:** Sends clean article text to an LLM with a strict prompt to extract verifiable, self-contained facts.
- **Validation:** Filters facts by confidence score (`CONFIDENCE_MIN = 0.60`).

## arbiter
- **Purpose:** The "Brain" of the system. Decides if a fact is New, a Duplicate, or an Update.
- **Key Files:** `arbiter.py` (orchestration), `judge.py` (LLM reasoning).
- **Logic:** 
    1. **Fast Path:** Vector similarity check in Supabase.
    2. **Auto-Merge:** Above 0.97 similarity = automatic duplicate.
    3. **Judge Path:** 0.75 - 0.97 similarity = LLM decides if it adds "Delta" (new info).
- **Dependencies:** `ledger/vector_store.py`, `llm/client.py`.

## ledger
- **Purpose:** Permanent storage and specialized data management.
- **Key Files:** 
    - `database.py`: Supabase client factory.
    - `vector_store.py`: Vector search and fact insertion.
    - `story_manager.py`: Groups Alphas into `StoryNodes` (Phase 3).
    - `story_summarizer.py`: Recursive LLM updates for story narratives.
    - `query_rotator.py`: Optimizes search keywords based on historical yield.
- **Logic:** Uses `pgvector` for semantic matching at both Fact and Story levels.

## pipeline
- **Purpose:** End-to-end orchestration.
- **Key File:** `runner.py`.
- **Flow:** Query Building → Collection → MMR Selection → Extraction → Harvesting → Judging → Story Assignment → Summarization → Briefing.

## tasks
- **Purpose:** Production-scale execution.
- **Key Files:** `celery_app.py`, `scheduler.py`.
- **Logic:** Periodically triggers the `PipelineRunner` for all active topics.

## models
- **Purpose:** Shared data structures.
- **Key Files:** `alpha.py`, `story.py`, `article.py`.
- **Standard:** Every module uses these dataclasses for type safety.

---
## [NOT BUILT YET]
- **api:** FastAPI routes for the mobile/web frontend (Phase 4).
- **billing:** Stripe integration, webhooks, and tier management (Phase 3.4).
