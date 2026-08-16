# V5 Pipeline — Verified Execution Reference

**Purpose:** every claim in this document was confirmed by tracing actual call sites in the
code (grep + read), not by trusting comments, docstrings, or `docs/core/architecture_v5.md`'s
design description. Written 2026-08-12 after two prior explanations in chat turned out to be
wrong (sourced from a stale comment and an unverified assumption). If you (agent, future
session) are asked about pipeline execution, cost sources, or what's live vs dead — read this
file first. If code has changed since, re-verify the specific claim before relying on it; don't
assume this file is still accurate forever.

---

## 1. What triggers a run

Each topic has "alarm clock" times — explicit UTC `(hour, minute)` slots stored in
`topic_schedule_times` (`src/truebrief/ledger/alarm_schedule.py:67-77`). Default is one run/day
at 09:00 UTC if none are configured (`alarm_schedule.py:16-18`). `compute_next_run`
(`:23-40`) computes the next slot and writes it to `topics.next_run_at` as a full ISO
datetime (`:96`, `.isoformat()` — **full timestamp precision is stored here**, see §8.2).

Higher tiers can schedule more than once/day: `min_spacing_hours_ok` (`:43-61`) enforces a
per-tier minimum gap between times (`TIER_LIMITS.min_interval_hours`) — free tier's 24h floor
allows one time/day; pro tier's 1h floor allows up to 24 scans/day.

A Celery Beat heartbeat, `check_and_schedule_topics` (`src/truebrief/tasks/scheduler.py:36`,
registered `celery_app.py:82-86`, fires every 60s), finds topics whose `next_run_at` has
passed and calls `run_pipeline_task.delay(...)` (`scheduler.py:98`). A user can also trigger
an immediate scan via an API route, landing on the same task.

**Confirmed: exactly one path can trigger a topic scan.** Grepped all of `src/truebrief/` for
`@celery_app.task|@shared_task|@app.task` — 4 registered tasks total (`pipeline_task.py`,
`scheduler.py`, `digest_task.py`, `push_task.py`), and `celery_app.py:58-63`'s `include=[...]`
list only imports those 4 modules, so nothing else can register a task at import time. No V4
pipeline task is registered anywhere — V4's `PipelineRunner` (`pipeline/runner.py`) is only
ever imported by 4 offline scripts (`scripts/quality_benchmark.py`, `scripts/run_pipeline.py`,
`scripts/smoke_scan.py`, `scripts/phase2_master_test.py`), never by a route or Celery task.

---

## 2. The live LLM call chain, in order, for one topic run

```
gemini_search  →  gemini_extract  →  embed × N alphas  →  arbiter × (grey-zone facts only)  →  briefer
```

Traced end-to-end: `pipeline_task.py:167` → `pipeline/v5_runner.py`'s `GeminiSearchRunner.run`
(`:40-87`). This is the **entire** live LLM sequence for a scheduled or user-triggered scan.
Nothing else fires unless a flag is changed (see §8.1).

| step_name | File:line | Model (config/settings.py) | Fires |
|---|---|---|---|
| `gemini_search` | `collector/gemini_search_collector.py:110-114` | `gemini-2.5-flash-lite` | Once/run |
| `gemini_extract` | `collector/gemini_search_collector.py:124-129` | `gemini-3.1-flash-lite` | Once/run |
| *(embed, no step_name)* | `arbiter/arbiter.py:429` (`self.ledger.llm.embed`) | Provider = `EMBED_PROVIDER` (see §8.2) | Once per new alpha |
| `arbiter` | `arbiter/judge.py:101` (single) or `:151-157` (`V3_BATCH_JUDGE`, off by default) | `gemini-3.1-flash-lite` | Only for facts in the cosine "grey zone" — most resolve for free |
| `briefer` | `briefer/briefer.py:51-56` | `gemini-3.5-flash-lite` (pricier tier than the others) | Once/run, only if ≥1 NEW/UPDATE fact |

---

## 3. Step by step — what each stage actually does

### 3.1 Search (`gemini_search`) — collector call 1 of 2
`GeminiSearchCollector.collect()` (`gemini_search_collector.py:93-131`). Builds a prompt via
`build_gemini_search_prompt` (`llm/prompts.py:709-729`):
> "Search the web for developments on '{topic}' from {last_run_date} to {today}. List every
> distinct development... with an explicit date. Be specific... Do not include analysis,
> predictions, or significance judgments."

Uses `LLMClient.call_gemini_with_grounding` — real Google Search grounding tool enabled
(`tools=[GoogleSearch()]`). Output is deliberately **plain prose, not JSON** — forcing JSON on
a grounded call was found to suppress `grounding_metadata` and make the model fabricate source
URLs (verified live 2026-07-22, per the module's own docstring). Returns prose text +
`grounding_supports`/`grounding_chunks` (the real, Google-verified source list).

**Only date-range context is sent — no memory, no prior facts.** `build_gemini_search_prompt`'s
signature is `(topic_name, last_run_date, today)` — three strings, nothing else. Confirmed by
reading the full function body (`prompts.py:718-729`) and its one production call site
(`gemini_search_collector.py:109`).

### 3.2 Extraction (`gemini_extract`) — collector call 2 of 2
Same function, second half. `_insert_citation_markers` (`:44-65`) stitches `[i]`/`[i,j]`
citation markers into the prose at each grounding segment's exact character offset.
`_build_source_legend` (`:68-84`) builds a numbered `[0] domain.com` list from the **real**
`grounding_chunks` — URLs/names here never come from model text, only from Google's own
grounding data. `build_gemini_extract_prompt` (`prompts.py:738-762`) then asks a second,
non-grounded, JSON-mode call to turn the cited prose + legend into structured facts, citing
sources ONLY by legend index (never writing a URL itself). `_parse_facts`
(`gemini_search_collector.py:133-225`) parses that JSON into `Alpha` objects — this is where
"alphas" (atomic, dated, sourced facts) are actually created. Facts below `_MIN_CONFIDENCE=0.6`
or missing a parseable `event_date` are dropped here.

### 3.3 Embed
Each surviving alpha gets an embedding vector before dedup comparison
(`arbiter/arbiter.py:429`, `self.ledger.llm.embed(...)`). **No `step_name` gate** — these calls
are never logged to `llm_call_log` at all, so they never appear in the cost dashboard
regardless of provider or price. See §8.2 for which provider actually serves this in
production.

### 3.4 Dedup / Judge (`arbiter`)
`Arbiter.judge_alphas()` (`arbiter.py:114`), per alpha:
1. Several **free, non-LLM** fast paths run first (`arbiter.py:173-396`): tally collapse,
   contradiction flag, raw-cosine near-duplicate check, entity-overlap check, same-day
   duplicate check. Most facts get classified here — MERGE, UPDATE, or pass-through — without
   ever reaching an LLM.
2. `VectorStore.find_similar()` (`vector_store.py:308-354`, pgvector cosine similarity via the
   `match_facts` RPC, scoped to the topic, `limit=3`, `threshold=0.50` —
   `arbiter.py:49,53,435-448`) pulls the closest prior facts.
3. Only for the genuinely ambiguous "grey zone" pairs the cheap math can't resolve: the matches
   get formatted into a text block (`ARBITER_CASE_BLOCK`, `prompts.py:303-310`) —
   ```
   CLOSEST KNOWN FACTS (from memory, ranked by similarity):
   [MERGE 0.91] "fact text..." — entities, event date
   ```
   — and fed to the `arbiter` LLM call (`judge.py:101-106`), which returns MERGE / UPDATE / NEW.

**This is the proven "inject memory into a prompt" pattern in this codebase** — see §7.

### 3.5 Store
NEW/UPDATE facts get written via `VectorStore.add_fact()` (`v5_runner.py:71` →
`vector_store.py:66-185`) into `known_facts`, including the embedding, entities, event_date,
context, confidence, source_url, source_domain, verified_count, verifier_flags, event_class,
relevance-vs-topic-centroid, and more (full field list in §7.1). This also conditionally
spawns a background thread for `story_stitch` — see §8.1, currently off.

### 3.6 Brief writing (`briefer`)
`Briefer.generate()` (`briefer/briefer.py:29-60`), called as
`self.briefer.generate(decisions, topic_input)` (`v5_runner.py:85` — **no third `situation`
arg is ever passed on the live path**, so `situation_hint` is always empty). Filters to only
NEW/UPDATE decisions (`:41`); returns `""` if none. Builds a JSON payload of
`{"NEW_STORIES": [...], "UPDATES": [...]}` — facts arrive pre-sorted by significance
(`state_change > escalation > development > incremental > tally > routine`) and that order is
preserved. `build_briefer_prompt` (`prompts.py:364-404`) enforces an exact output format:

```
📋 TrueBrief | [Topic] | [Date]
**📌 Bottom line:** [one sentence, the single most important CURRENT development]
🆕 NEW STORIES (N)
**Story Title**
• fact + context as flowing prose. → Sources: [domain.com](url)
📈 UPDATES (N)
**Story Title**
• what changed, prior situation woven in as prose. → Sources: [domain.com](url)
```

This markdown is saved to the `briefs` table. **It is the primary content of the topic page**
(`frontend/src/app/(app)/topics/[id]/page.tsx:230`, `BriefPanel` → `GET /topics/{id}/briefs` →
`parseBrief` → rendered as the entire content area, comment at `:698-701`: "the synthesized
brief only... the raw fact-by-fact timeline was removed 2026-07-30"). It is NOT admin-only —
an earlier chat answer that claimed this was wrong, sourced from a stale `frontend/CLAUDE.md`
note.

---

## 4. Dashboard and topic page — no extra LLM calls on visit

- **Dashboard flip card** (`frontend/src/app/(app)/dashboard/page.tsx`, `TopicFlipCard`):
  fetches the same `GET /topics/{id}/briefs`, renders `parseBrief(latest.content)`'s lede +
  first 4 bullets. As of the 2026-08-12 UI change, it's a static card (flip/toggle removed,
  always shows this summary — see the "Session Summary" from that change).
- **Topic page** (`topics/[id]/page.tsx`, `BriefPanel`): same endpoint, renders the full brief
  via `<BriefBody>`.
- `GET /topics/{id}/briefs` (`routes.py:698-715`) is a **pure DB read** — `db.table("briefs")
  .select("*")...` — zero LLM calls in the route itself.
- **`dashboard_summary`** (`POST /topics/{id}/summary`, `routes.py:1346-1399`) is a *separate*,
  real endpoint that DOES call an LLM (`step_name="dashboard_summary"`,
  `build_dashboard_summary_prompt`) — but **no frontend code calls it**. Grepped all of
  `frontend/src` for `api.post`/`api.get` against `/summary` — zero matches outside a cost-
  label string in the admin page. **This endpoint is fully dead** despite being real,
  functional code.

---

## 5. Admin cost dashboard — label-to-reality mapping

`frontend/src/app/(app)/admin/page.tsx`'s "LLM Cost by Stage" widget reads
`GET /admin/metrics` (`routes.py:1628-1755`), which aggregates `llm_call_log` via the
`llm_cost_by_stage` Postgres RPC (`scripts/migrations/027_llm_cost_rpcs.sql`), filtered to
`V5_STAGES` (`routes.py:1691-1694`): `gemini_search, gemini_extract, arbiter, briefer,
dashboard_summary, state_of_play`. Window is all-time (`days_back=3650`).

| Label | step_name | Actually live? |
|---|---|---|
| Search (Gemini) | `gemini_search` | **Live** — §3.1 |
| Extraction | `gemini_extract` | **Live** — §3.2 |
| Dedup / Judge | `arbiter` | **Live** — §3.4 |
| Brief writing | `briefer` | **Live** — §3.6 |
| Dashboard summary | `dashboard_summary` | **Dead** — §4, no frontend caller, ever |
| State of play | `state_of_play` | **Dead** — §6, generator never called on live path, flag off, route has no frontend caller |

Any historical $0/small-$ amounts under the dead labels are leftover spend from before these
paths were orphaned — not current activity. Action taken 2026-08-12: removed the two dead
stages from both `V5_STAGES` (backend) and the frontend label map, so the widget only shows
the 4 stages that are actually live. See git log for the exact commit.

---

## 6. Dead / orphaned code inventory (V4 → V5 leftovers)

Confirmed via import-tracing — none of these are reachable from a route, a Celery task, or any
live frontend call:

- **Entire old collector/search stack**: `collector/tavily_layer.py`, `brave_layer.py`,
  `exa_layer.py`, `google_news_layer.py`, `rss_layer.py`, `extractor.py`, `dedup.py`,
  `url_guard.py`, `base.py`, `query_builder.py`, `harvester/harvester.py`,
  `ledger/query_rotator.py`, `ledger/story_summarizer.py`. Only importer of any of them:
  `pipeline/runner.py` (the V4 runner), which is itself only imported by 4 offline scripts.
- **`briefer/state_of_play.py`** (`StateOfPlayGenerator`) — only imported by `pipeline/runner.py`.
  `V3_STATE_OF_PLAY=false` in `.env`. `Briefer.generate()`'s `situation` param is never passed
  on the live path. Dead at every layer, not just flag-gated.
- **Story mode**: `POST /topics/{id}/story` (`routes.py:1402`) — no frontend caller.
  `story_stitch` prompts referenced only by this dead route and by `vector_store.py`'s
  background-thread stitcher, which is flag-gated off (`V4_STORY_STITCHING`, defaults `False`,
  unset in `.env` — see §8.1, this one is NOT fully dead, just currently off).
- **AYR engine**: `GET /topics/{id}/ayr` (`routes.py:877`) — no frontend caller. Explicitly
  superseded by alarm-clock scheduling; topic page has a comment confirming this.
- **Also orphaned, no frontend caller**: `GET /topics/{id}/query-variants` (`routes.py:926`),
  `GET /topics/{id}/stories` / `/stories/{id}/facts` (`routes.py:968,992`).
- **`dashboard_summary` endpoint** (`POST /topics/{id}/summary`) — see §4/§5.
- **`garbage_filter`** — an `LLM_CONFIG` entry in `config/settings.py:214` with **zero call
  sites anywhere** in the codebase. Configured, never used.
- **Three overlapping admin-check functions** in `routes.py`: `_require_founder` (`:67-77`,
  checks `FOUNDER_EMAIL`, used once at `:1034`), `_require_admin` (`:80-85`, checks
  `is_admin()`/`ADMIN_EMAILS`, used at `:287,375`), `_is_admin` (`:1603-1620`, checks
  `ADMIN_USER_IDS` OR `ADMIN_EMAILS`, used at `:827,1635,1785,1839`). Worth consolidating —
  not urgent, no known bug from the overlap, just churn residue.
- **Prompt builders in `llm/prompts.py`** only reachable from the above dead/V4-only code:
  `build_query_builder_prompt`, `build_harvester_prompt`, `build_state_of_play_prompt`,
  `build_story_summarizer_prompt`, `build_query_rotator_prompt`,
  `build_dashboard_summary_prompt`, `build_story_stitch_pair_prompt`,
  `build_story_stitch_batch_prompt`. Only 3 prompt builders are actually live:
  `build_gemini_search_prompt`, `build_gemini_extract_prompt`, `build_briefer_prompt`.

None of this is costing money or causing bugs today — it's inert weight, not an active
problem. Full V4 design context lives in `docs/core/V4_ARCHIVE.md` (via the
`architecture-v4-map` skill) — this section is just "what's still sitting in the current tree
from that era."

---

## 7. Memory / embedding system — what's actually queryable

### 7.1 `VectorStore` (`ledger/vector_store.py`)
`add_fact()` (`:66-185`) stores per fact in `known_facts`: `topic_id`, `alpha_text`,
`alpha_embedding`, `entities`, `event_date`, `context`, `confidence`, `source_url`,
`source_domain`, `verified_count`, `verifier_flags`, `event_class`, plus conditionally
`story_node_id`, `date_basis`, `published_at`, `importance`, `relevance` (cosine vs. the
topic's own embedding), `signal_score`/`signal_class`, `contradicts_id`/`contradiction_note`.

Query methods that exist:
- `find_similar(embedding, topic_id, limit, threshold)` (`:308-354`) — pgvector cosine
  similarity, topic-scoped, top-K. **This is the only "search memory" primitive used on the
  live path.**
- `find_tally_match(alpha, min_entity_overlap)` (`:356-403`) — entity-overlap only, for
  `event_class='tally'`.
- `get_seen_urls(topic_id, days)` (`:285-306`) — time-filtered, URLs only, no fact content.
- No "all facts for topic Y from the last N days" method exists on `VectorStore` itself. A
  plain chronological query exists in `ledger/history_doc.py:86-116` but only feeds
  `GET /topics/{id}/history`, which only the internal `admin/compare` page calls — not part of
  any live prompt.

### 7.2 The existing "inject memory into a prompt" pattern
Live today, in the Arbiter only (§3.4): embed → `VectorStore.find_similar()` (topic-scoped,
top-3, cosine ≥0.50) → format via `ARBITER_CASE_BLOCK` → inject into the `arbiter` LLM call.
**Not currently wired into the search call** — `build_gemini_search_prompt` only receives
`topic_name, last_run_date, today` (§3.1). If memory-aware search is ever built, this is the
pattern to reuse — call `find_similar` before building the search prompt instead of only
after extraction.

---

## 8. Open items flagged during this audit (not yet fixed, not yet asked for)

### 8.1 `story_stitch` — live in the call chain but flag-gated off
`VectorStore.add_fact()`'s background thread can call `story_stitch` (`vector_store.py:253-
257`), gated by `settings.V4_STORY_STITCHING` (default `False`, `config/settings.py:139`, not
set in `.env` or `.env.example`). Currently 0 live occurrences. If this flag is ever flipped
on, it starts firing on every stored fact from the scheduled pipeline itself — not just the
already-dead `/story` route. Worth remembering it's there before anyone flips that flag.

### 8.2 `EMBED_PROVIDER` in production — checked live via Railway MCP, 2026-08-12
`config/settings.py:158` defaults `EMBED_PROVIDER` to `"gemini"`. Local `.env` overrides it to
`"local"` (free, CPU-only `BAAI/bge-base-en-v1.5`, no network call — `llm/local_embedder.py`).
**Checked the actual Railway "Worker" service (the one that runs the Celery task and therefore
the Arbiter's embed calls) — `EMBED_PROVIDER` is NOT set as an environment variable there.**
That means production is running on the code default, `"gemini"` — i.e., production embed
calls are real network calls to `models/gemini-embedding-2` (`llm/client.py:307-323`), not the
local CPU model the architecture doc implies is the live design. They're priced at $0.0/token
in `pricing.py:36` ("free tier at this scale") and, separately, are never logged to
`llm_call_log` at all (`embed()`/`embed_batch()` don't call `_log_call()`), so they don't show
up in the cost dashboard even as a $0 row. If Google ever starts charging for this at volume,
that spend would show up nowhere in the current cost dashboard until pricing.py and the
`_log_call` wiring are updated. Worth deciding deliberately whether production should be on
`gemini` (current, higher quality, unlogged $0 today) or `local` (CPU-only, definitely $0
forever, matches what the architecture doc describes as the intended design) — this looks like
an unintentional default, not a considered choice, since nothing in `.env.example` or Railway
sets it explicitly.

### 8.3 Search window is day-granularity only — same-day rescans send an identical window
`GeminiSearchCollector.collect()` (`gemini_search_collector.py:105-109`) formats
`last_run_date` via `.strftime("%Y-%m-%d")` — **date only, no time-of-day** — before building
the search prompt ("from {last_run_date} to {today}"). But `topics.next_run_at` is stored with
full datetime precision (`alarm_schedule.py:96`, `.isoformat()`), and pro-tier topics can be
scheduled to scan as often as once/hour (`min_spacing_hours_ok`, §1). **This means: if a topic
scans twice in the same UTC day, both scans send Gemini the exact same date-range instruction**
("from 2026-08-12 to 2026-08-12" for both a 09:00 run and a 15:00 run) — there is currently no
way for the prompt to express "since 6 hours ago" vs "since yesterday." This is a structural,
code-confirmed source of redundant search + extraction spend and downstream judge workload for
any topic scanning more than once/day: Gemini has no way to know a narrower window was intended,
so it may well re-surface facts already reported hours earlier, which then just get filtered
out as duplicates by the Arbiter (spending `gemini_search` + `gemini_extract` cost, plus
whatever grey-zone `arbiter` calls the redundant facts trigger, for zero net signal). This
wasn't measured live in this audit (see the companion investigation task for actual duplicate-
rate numbers) — this section documents the structural cause, confirmed directly in code,
independent of that measurement. A fix would mean passing full ISO timestamps (not just dates)
into `build_gemini_search_prompt` and rephrasing the window instruction accordingly — not
implemented here, flagging for a deliberate decision + benchmark validation before changing
production behavior, per this project's "nothing kept/changed without evidence" rule.

**Measured live, 2026-08-12** (real `GeminiSearchCollector.collect()` calls against active
topics, `raw_query='iran war'`, `raw_query='trump'`, using the primary `GOOGLE_API_KEY` — no
quota errors):

- **Window adherence (3-day window, single scan):** 26/26 returned alphas across both topics
  had `event_date` inside the requested window. Gemini Search grounding does not bleed in
  stale/old items at day granularity — that part of the design works as intended.
- **Same-day rescan overlap (the actual hypothesis):** two `collect()` calls 5 seconds apart,
  both windowed to "since 6 hours ago" (same calendar day) on `'iran war'` — **86% of run-1
  facts (6/7) substantively reappear in run 2**, reworded/re-aggregated by Gemini each time
  (confirmed via the real production embedder + the live Arbiter's actual thresholds,
  `GREY_ZONE_MIN=0.75` / `AUTO_MERGE_THRESHOLD=0.97`). Of those: **5/7 (71%) land in the grey
  zone**, meaning every same-day rescan currently spends a wasted `JudgeLLM` call per
  re-surfaced fact, on top of the `gemini_search`+`gemini_extract` spend that produced them.
  **1/7 scored 0.714 — just under `GREY_ZONE_MIN` — and would auto-insert as a brand-new fact**
  despite being the same underlying event, i.e. a real duplicate currently leaks past the
  Arbiter on rescans, not just a cost-waste problem.
- **"Last 6 hours" prompt wording test:** manually asking for time-of-day-aware results didn't
  help — Google Search's underlying news index itself only returns day-granularity dates, so
  the returned facts and their apparent freshness were unchanged. **Sharper prompt wording
  alone would not fix this** — there's nothing finer-grained for the model to draw from.
- **Root-cause read:** this is the pipeline's known paraphrase-leak issue (`truebrief-pipeline`
  skill, known issue #2 — the same real event gets reworded differently each Gemini call)
  compounding the day-granularity problem, not two separate bugs. The date-truncation fix
  alone would not close this gap.
- **Cheaper fix candidate than "truncate less":** before calling `gemini_search` on a same-
  calendar-day rescan, pull the topic's last N stored facts and inject "already known, don't
  re-report" context into the search prompt (reusing the Arbiter's existing `find_similar` →
  format → inject pattern, §7.2) — this would cut the wasted `gemini_search`/`gemini_extract`
  spend at the source, rather than relying on the Arbiter to catch it after the fact (which it
  only partially does, per the 0.714 leak above). Not implemented — flagging for a deliberate
  decision + benchmark validation, same rule as above.

### 8.4 Stale Clerk env vars still present in Railway's "Worker" service
Listed via Railway MCP 2026-08-12: `CLERK_AUDIENCE`, `CLERK_ISSUER`, `CLERK_JWKS_URL`,
`CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY` are all still configured on the production Worker
service, despite the frontend having fully migrated to Supabase Auth (confirmed separately —
`frontend/src/components/auth/AuthCard.tsx` is a custom Supabase-based card, no Clerk
component anywhere). These are inert unless something still reads them, but they're real
credentials sitting in production config for an auth provider that's no longer wired to
anything found in this or the prior audit. Worth a deliberate decision on whether to revoke/
remove them.
