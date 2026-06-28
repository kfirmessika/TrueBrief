---
name: truebrief-backend
description: Conventions for editing the TrueBrief Python backend (src/truebrief/**, config/, scripts/, tests/) — FastAPI routes, Celery tasks, the LLMClient, billing, auth, and adding pipeline stages or source layers. Use when writing or changing backend code, or running backend tests. Enforces "never hardcode models", "no circular imports", and "run pytest before done".
---

# TrueBrief Backend — FastAPI · Celery · Pipeline

**Scope:** `src/truebrief/`, `config/settings.py`, `scripts/`, `tests/`. Do NOT touch `frontend/` (see [[truebrief-frontend]]) or run DB schema migrations directly (see [[truebrief-database]]).

## Dev commands (from project root)
```bash
.venv/Scripts/python.exe -m pytest tests/        # run tests — REQUIRED before reporting done
.venv/Scripts/python.exe -m pytest tests/ -k <pattern>   # targeted (save tokens)
python scripts/run_pipeline.py "your topic"      # manual synchronous run, prints brief
python scripts/run_pipeline.py "topic" --debug   # verbose
python scripts/audit_topic.py "keyword"          # dump stored data → reports/
```
**Rule: never report a task done without running `pytest tests/` and reporting PASS/FAIL.** See [[run-truebrief-locally]] for the full local stack (Redis + Celery + FastAPI).

## Layout (`src/truebrief/`)
`api/` (server.py, routes.py, rate_limit.py, push_routes, digest_routes, billing_routes) · `pipeline/runner.py` · `collector/` (base, query_builder, extractor, rss/google_news/tavily/brave/exa layers) · `harvester/` · `arbiter/` (arbiter, judge, temporal) · `briefer/` · `ledger/` (vector_store, story_manager, story_summarizer, ayr_engine, query_rotator, source_logger, database, telemetry) · `llm/` (client, pricing) · `models/` (alpha, article, brief, story, topic, tier) · `auth/` (dependencies, clerk, user_repo) · `billing/` (tiers, paddle_service, stripe_service) · `tasks/` (celery_app, pipeline_task, digest_task, push_task, scheduler) · `push/` · `digest/`.

## Hard rules
1. **All LLM calls go through `LLMClient`** (`llm/client.py`). Never call an LLM SDK directly. Never hardcode a model name — read `settings.LLM_MODEL_FLASH | LLM_MODEL_SONNET | LLM_MODEL_OPUS | EMBEDDING_MODEL`.
2. **All DB access goes through `ledger/`.** `get_supabase()` (`ledger/database.py`) is the singleton client.
3. **No circular imports** — share types via `models/`. Never import a downstream pipeline stage from an upstream one.
4. **No placeholder code** — no `TODO`/`pass`/`...` left behind. If a value is unknown, ask.
5. **Config** via `config/settings.py` (pydantic Settings, single source of truth), env from `.env`.

## LLMClient
```python
from truebrief.llm.client import LLMClient
llm = LLMClient()
text = llm.call(step_name="my_step", prompt="...", system_prompt="...", json_mode=False)
vec  = llm.embed("text")              # list[float]
vecs = llm.embed_batch(["a", "b"])    # list[list[float]]
```
`step_name` is used for per-step cost tracking (`llm/pricing.py`).

## API endpoints (all under `/api/v1`, auth via `get_current_user`)
Topics CRUD + `/topics/{id}/scan` + `/scan-status/{task_id}`; `/billing/status` + `/billing/webhook`; `/push/subscribe`; `/digest/*`; admin (founder-only) `/admin/topics`, `/admin/topics/{id}/run`, `/admin/runs`; `/users/me`, `/users/me/stats`.
```python
@router.get("/your-path")
async def endpoint(user: User = Depends(get_current_user), db = Depends(get_supabase)):
    ...
# register: app.include_router(your_router, prefix="/api/v1") in api/server.py
```
Founder guard: `from truebrief.api.routes import _require_founder; _require_founder(user)`.

## Billing / tiers
`from truebrief.billing.tiers import enforce_topic_limit, enforce_speed_limit` — call in POST /topics and POST scan. Limits: free (3 topics / 24h), pro (10 / 1h), power (∞ / 15min). Paddle is current; Stripe is legacy.

## Celery
`run_pipeline_for_topic.delay(topic_id)` (tasks/pipeline_task.py) runs the pipeline, saves the brief, updates `last_run_at`/`next_run_at`. Beat checks every topic's `next_run_at` every 60s. **Requires Redis** — set `REDIS_URL=redis://localhost:6379/0` in `.env`, else Celery falls back to an in-memory broker (beat won't work).

## Models cheat-sheet
`Alpha {alpha_text, entities[], source_url, source_name, event_date?, context?, confidence, id, topic_id?, embedding?}` · `AlphaDecision {alpha, decision: NEW|UPDATE|DUPLICATE, similarity_score, matched_alpha_id?, reasoning?, delta?}` · `StoryNode {id, topic_id, title, summary, status, fact_count, created_at, updated_at}`.

For pipeline stage logic + thresholds see [[truebrief-pipeline]]. For accuracy testing after changes see [[accuracy-eval]].
