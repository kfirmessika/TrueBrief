---
name: truebrief-pipeline
description: Reference for TrueBrief's news pipeline — the collect → harvest → arbitrate → story → brief flow. Use when working on or reasoning about src/truebrief/pipeline, collector, harvester, arbiter, briefer, or ledger; the stage order; similarity thresholds; model tiers; known quality issues; or the brief output format.
---

# TrueBrief Pipeline — The Engine

The pipeline turns a raw topic string into a noise-free markdown brief of only NEW + UPDATED facts.
Orchestrated by `PipelineRunner.run()` in `src/truebrief/pipeline/runner.py`.

## Stages (in order)

1. **QueryBuilder.build(raw_topic)** (`collector/query_builder.py`) — LLM → `SearchQuery {topic_name, primary_query, alt_queries[], scope}`.
2. **QueryRotator.select_variant** (`ledger/query_rotator.py`) — picks the best-performing query variant from DB history.
3. **_collect_all(query)** — runs all `SourceLayer` plugins in parallel, dedups by URL. RSS/GoogleNews keyword pre-filter; Tavily/Brave/Exa trusted (no filter).
4. **_mmr_select(query, articles, limit=5)** — Maximal Marginal Relevance, λ=0.65 (relevance vs diversity). Embeds query + titles, greedy selection. `MAX_ARTICLES = 5`.
5. **ArticleExtractor.extract + Harvester.extract** (`collector/extractor.py`, `harvester/harvester.py`) — fetch full text (`trafilatura`); LLM extracts atomic `Alpha[]`. Facts with `confidence < 0.60` (`CONFIDENCE_MIN`) are dropped.
6. **Arbiter.judge(alpha, topic_id)** (`arbiter/arbiter.py`) — embed alpha, fetch top-3 similar from VectorStore, temporal-adjust, then:
   - score ≥ `AUTO_MERGE_THRESHOLD` (0.97) → **AUTO-DUPLICATE** (no LLM)
   - score < `GREY_ZONE_MIN` (0.75) → **AUTO-NEW** (no LLM)
   - 0.75–0.97 → **JudgeLLM** (`arbiter/judge.py`, structured output: MERGE/UPDATE/NEW + delta)
7. **StoryManager.assign_to_story** (`ledger/story_manager.py`) — UPDATE joins matched fact's StoryNode; NEW → `match_stories` RPC (≥ `STORY_ASSIGNMENT_THRESHOLD` 0.70) or creates a new StoryNode.
8. **VectorStore.add_fact** (`ledger/vector_store.py`) — embed alpha_text, insert into `known_facts` with `story_node_id`.
9. **StorySummarizer.refresh_summary** (`ledger/story_summarizer.py`) — only on UPDATE; LLM re-summarizes + re-embeds the story.
10. **AYR engine.record_run** (`ledger/ayr_engine.py`) — sets next `poll_interval_seconds` from the yield rate.
11. **Briefer.generate(decisions, topic_name)** (`briefer/briefer.py`) — NEW + UPDATE only → markdown brief. Saved to `briefs` by `tasks/pipeline_task.py` after the runner returns.

## Tuning thresholds (where to turn the dials)

| Constant | File | Value | Effect |
|---|---|---|---|
| `AUTO_MERGE_THRESHOLD` | arbiter.py | 0.97 | ↑ if too many dupes hit the LLM (slow/$) |
| `GREY_ZONE_MIN` | arbiter.py | 0.75 | ↑ (0.80–0.85) if paraphrases slip through as NEW |
| `LEDGER_FETCH_THRESHOLD` | arbiter.py | 0.50 | min score to retrieve a match at all |
| `STORY_ASSIGNMENT_THRESHOLD` | story_manager.py | 0.70 | ↓ if NEW facts keep spawning new stories |
| `CONFIDENCE_MIN` | harvester.py | 0.60 | facts below are dropped |
| `MAX_ARTICLES` | runner.py | 5 | articles per run; ↑ if signal is thin |
| MMR `λ` | runner.py | 0.65 | relevance vs diversity balance |

## Model tiers (never hardcode — read from `config/settings.py`)
- `settings.LLM_MODEL_FLASH` — harvester, query builder (fast/cheap)
- `settings.LLM_MODEL_SONNET` — arbiter judge, briefer, summarizer (capable)
- `settings.LLM_MODEL_OPUS` — reserved for complex reasoning
- `settings.EMBEDDING_MODEL` — text-embedding-004 (768 dims)

All LLM calls go through `LLMClient` (`llm/client.py`): `.call(step_name, prompt, system_prompt=, json_mode=)`, `.embed(text)`, `.embed_batch([...])`.

## Known quality issues (live)
1. **`event_date` ~87% empty** — LLM rarely populates it; extractor prompt needs explicit temporal-extraction instruction.
2. **Arbiter sees paraphrases as NEW** — same fact, different wording slips past GREY_ZONE_MIN 0.75; raising to 0.80–0.85 + more JudgeLLM helps.
3. **Collector re-scrapes same articles** — no per-URL dedup vs `known_facts.source_url` before MMR.
4. **`briefs.facts_json` always NULL** — dead column; don't rely on it.
5. **`usatoday.com` injects wrong event_dates (2020)** — no sanity-check vs topic time range; a date >2y old should be rejected/flagged (see `tests/test_date_guard_sentinel.py`).
6. **AYR vs tier-interval conflict** — after a run AYR sets `poll_interval_seconds`; a subscription change overwrites it. Last writer wins.

## Brief format (Briefer output)
```
📋 TrueBrief | {Topic} | {Date}
🆕 NEW STORIES ({N})
━━━━━━━━━━━━
**Story Title**
• Fact sentence. → Sources: [Name](url)
📈 UPDATES ({N})
━━━━━━━━━━━━
**Story Title**
• WHAT'S NEW: the delta. → Sources: [Name](url)
• FULL CONTEXT: why it matters. → Sources: [Name](url)
```
Rules enforced in the briefer prompt: every bullet ends with `→ Sources: [Name](url)`; never hallucinate (facts only from the JSON payload); omit a 0-item section; group related facts under one `**heading**`.

## Adding a stage / source
- **Stage:** create `src/truebrief/<stage>/<stage>.py`, accept `LLMClient`/`VectorStore` in `__init__` (never instantiate internally), wire into `PipelineRunner.__init__` + `run()` in order. Never import a downstream stage (circular imports are fatal — share types via `models/`).
- **Source:** subclass `SourceLayer` (`collector/base.py`), set `name`, implement `search(query) -> list[RawArticle]`, register in `PipelineRunner.__init__`.

Related: [[truebrief-backend]] (code conventions), [[accuracy-eval]] (per-stage quality tests), [[architecture-v3-map]] (§5 pipeline, §10B scoring).
