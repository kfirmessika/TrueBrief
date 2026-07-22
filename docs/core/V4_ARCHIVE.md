# V4 ARCHIVE — what was built, where it lives, and what it's worth

**Frozen:** 2026-07-22 at commit `6f26fac`, recoverable via tag `v4-final` or branch `v4-archive`.
**Status:** V4 is the complete custom-pipeline era (10 months of work). `main` moves on to V5
(Gemini-first). **Nothing here is deleted — it is parked and reusable.**

> **Read this before rebuilding ANY feature.** The point of this file is that V5 never
> reinvents something V4 already solved. If a V5 task sounds like a feature listed below,
> open the V4 code first (`git show v4-final:<path>`) and port it rather than writing it fresh.

---

## 1. Why V4 was frozen (the evidence, not opinion)

| Measurement | Result | Source |
|---|---|---|
| Signal quality vs Gemini-Search | **TrueBrief 24 vs Gemini 33** (lost lede/completeness/synthesis/noise) | `docs/benchmarks/2026-07-21_iran-war-ceasefire-deal.md` |
| Prior benchmark | 17 vs 36 | `docs/benchmarks/2026-07-05_iran-war-ceasefire-deal.md` |
| Cost | ~$5 of search+LLM credits in <20 days on **4 topics** | founder's Tavily/Brave billing |
| Reliability | works sometimes; breaks in a new place each run (dead quotas, 403 scraping, silent fallbacks) | live runs this session |
| Users | 0 in 10 months | no signup metric exists anywhere in `src/` |

**Conclusion:** the custom collect→harvest→arbitrate chain — ~90% of the effort and the intended
differentiator — is *slower, lower-quality, and 10–50x more expensive* than simply calling Gemini
Search. It is not a bug problem; the architecture lost on its own terms. V5 makes Gemini Search the
main pipeline and keeps only what independently earns its place.

---

## 2. How to recover anything from V4

```bash
git show v4-final:src/truebrief/harvester/harvester.py     # read one file as it was
git checkout v4-final -- src/truebrief/harvester/          # restore a whole dir onto main
git diff main v4-final -- src/truebrief/ledger/            # see what V5 changed
git switch v4-archive                                       # browse the whole V4 tree
```
`v4-final` (tag) and `v4-archive` (branch) both point at `6f26fac`. Neither ever moves.

---

## 3. Component map — what it does, where it is, what it's worth

Verdicts: **KEEP** (carry into V5) · **EVALUATE** (Phase 1 decides on real data) · **CUT** (not in
V5 now; reintroduce post-production only if proven) · **FIX** (keep but repair first).

### Collection layer — CUT
| Piece | Path | Note |
|---|---|---|
| Query builder (LLM → 3-4 domains × 2 queries) | `collector/query_builder.py` | Replaced by a single Gemini Search call |
| Tavily / Brave / Exa / RSS / Google-News layers | `collector/{tavily,brave,exa,rss,google_news}_layer.py` | Common interface in `collector/base.py` |
| Article extractor + SSRF guard | `collector/extractor.py`, `collector/url_guard.py` | Trafilatura-based; hit widespread 403/bot-blocking |
| Near-dup article filter | `collector/dedup.py` | Article-level (not fact-level) |
| Query rotation (5 active variants, regen on exhaustion) | `ledger/query_rotator.py` | Bounded; not the cost leak |

**Why cut:** free tiers dead (Tavily "exceeds plan", Brave 402), major outlets 403-block the scraper
(NYT/Axios/ISW), and the per-scan fan-out fires ~4-5 paid searches with no budget ceiling. Gemini
Search does collection+extraction in one grounded call.
**Reusable if needed later:** the Tavily/Brave layers are clean, small, and work when funded — the
V5 "hybrid" experiment (agent finds links → hand to Gemini) would port these.

### Harvester — CUT (but the prompt is valuable IP)
`harvester/harvester.py` — turns article text into atomic facts: `alpha_text`, `context`,
`entities`, `event_date`, `date_basis`, `is_background`, `confidence`, `importance`, `event_class`.
- **The extraction prompt is the single most valuable artifact here** (`llm/prompts.py`,
  `build_harvester_prompt`). It encodes hard-won rules: strip editorial clauses, attribution rule,
  the 7 `event_class` values, drop-if-no-date. **V5's Gemini Search prompt must reproduce this same
  JSON contract** so the memory layer keeps working unchanged.
- Known bug (documented, unfixed): `_LAG_DROP_DAYS=45` staleness gate compares `event_date` to the
  *article's* publish date, not wall-clock today — so resurfaced old articles pass through.
- `V3_LAG_GATE` / `V3_DATE_GUARD` both default `False` in `config/settings.py`.

### Memory / dedup — **EVALUATE (leading stronghold, verify before trusting)**
| Piece | Path |
|---|---|
| pgvector store, `add_fact`, `find_similar`, `match_facts` RPC | `ledger/vector_store.py` |
| Per-user delta feed ("what's new since you looked") | `ledger/delta_engine.py` |
| Local embeddings (BAAI/bge-base-en-v1.5, no API cost) | `llm/local_embedder.py` |
| Topic timeline for the topic page (zero LLM) | `ledger/history_doc.py` |

This is the claimed differentiator — nobody else does per-user, cross-session, fact-level dedup.
**Not yet proven on real accumulated data.** Phase 1 must verify it before V5 depends on it.
Key constants: `delta_engine.PER_TOPIC_CAP=40`, `RELEVANCE_FLOOR=0.50`, `_salience()` =
significance × recency × relevance with a 0.6 floor; `history_doc._MAX_FACTS=600`.

### Arbiter / judge — EVALUATE ("keep only if needed")
`arbiter/arbiter.py` (orchestration) · `arbiter/judge.py` (LLM MERGE/UPDATE/NEW) ·
`arbiter/contradiction.py` (IC4 flag) · `arbiter/temporal.py`.
Contradiction detection requires ≥0.7 temporal overlap by design, so it cannot catch
"June deal quietly superseded by July collapse." **No supersession mechanism exists anywhere** —
`models/story.py`'s `StoryStatus.STALE` is defined but never set by any code. This is the root of
the stuck `noise_level` score.

### Signal scorer — EVALUATE / likely CUT
`pipeline/signal_scorer.py` — Groq llama-3.3-70b, scores 0-10 + `on_topic`. Validated 2026-07-07 as
a strong noise gate (trump 34→13, iran 30→11). **Must run on 70b-class — 8b was incoherent.**
Gemini Search may make this redundant; prove it either way.

### Adaptive scheduling (AYR) — CUT for V5, reintroduce post-production
`ledger/ayr_engine.py` (EMA of alpha-yield-rate → poll interval, 900s–86400s, needs 5 samples) ·
`tasks/scheduler.py` · `tasks/celery_app.py` (60s beat heartbeat) · `tasks/pipeline_task.py`.
Works as designed, but V5 replaces it with **manual alarm-clock scheduling** (default 1 run/day,
user-added run times). Known bug: `api/routes.py` hardcodes pro=21600s while `models/tier.py` and
the `tier_intervals` table say pro=3600s — two sources of truth.

### Story stitching — CUT
`llm/prompts.py` (`build_story_stitch_pair_prompt` / `_batch_`) · `fact_stitches` table
(migration 023) · story mode in `frontend/src/app/(app)/topics/[id]/page.tsx`.
Generated LLM "bridges" between adjacent facts. **Was caught inventing causal links between
unrelated facts and corrupting a number (16 killed → "six").** Partially hardened on 2026-07-21
(`619aea7`) but still hedges causation on genuinely unrelated pairs. Not worth the risk in V5.

### Briefer / State of Play — EVALUATE / stays OFF
`briefer/briefer.py` (markdown brief) · `briefer/assembler.py` · `briefer/state_of_play.py`.
**`V3_STATE_OF_PLAY` must stay off** — deliberate V4 decision, do not re-enable.
Briefer payload bug: it omits `event_date`/`first_seen_at`, so the LLM cannot tell a 5-week-old
fact from today's.

### Prompts — **KEEP (highest-value artifact)**
`llm/prompts.py` — every LLM prompt across all 9 pipeline stages, consolidated 2026-07-21, grouped
by stage with model-tier banners, plus a runnable `__main__` sanity block. Includes the
2026-07-21 fix making harvester `context` additive background instead of fact-restatement.

### LLM client & cost — KEEP + **FIX (foundational for V5)**
`llm/client.py` (multi-provider gemini/openai/groq with fallback chains) · `llm/pricing.py` ·
`ledger/telemetry.py`.
**Broken and must be fixed in V5 Phase 3:**
1. `llm_call_log` / `pipeline_run` tables and the 3 cost RPCs (`llm_cost_by_stage`,
   `llm_cost_by_day`, `pipeline_run_summary`) exist **only** in `ledger/schema.sql` — they were
   never added to the numbered migration chain, so they may not exist in the live DB at all.
2. `pricing.py` has **no entry** for `llama-3.3-70b-versatile` → silently bills **$0**.
3. **Search API cost is tracked nowhere** — no table, no counter.
4. `/admin/cost-summary` and `/admin/metrics` swallow all errors and return zeros, so a missing
   table looks identical to "nothing costs money." This is why spend was invisible for months.

### Frontend — KEEP (minus story mode)
Next.js 16 App Router, `frontend/src/app/`: `(marketing)` landing, `(app)/dashboard`,
`(app)/topics/[id]` (timeline + story mode), `settings`, `admin`, `developers`, `terms`/`privacy`.
Plus PWA (manifest, SW, offline shell) and Capacitor Android/iOS shells (`docs/MOBILE_APP.md`).

### API / B2B / billing / auth — KEEP (dormant)
`apikeys/` (service + routes; **migration 026 never applied to prod** → 503s) ·
`billing/paddle_service.py` (**never activated** — no live price IDs) · `auth/` (Clerk) ·
`api/rate_limit.py` · `digest/` (email digests) · `push/` (web push, VAPID).

---

## 4. Reference docs & tooling that stay valid
- `docs/core/architecture_v3.md` (36KB — **never read in full**; use the `architecture-v3-map` skill)
- `docs/roadmap.md`, `docs/PRODUCT_PLAN.md`, `docs/BUSINESS_PLAN.md`, `docs/OPERATIONS.md`
- `scripts/quality_benchmark.py` — the Gemini-vs-us judge harness (**V5's success gate**)
- `scripts/audit_topic.py` — dumps everything stored for a topic (real-data evidence tool)
- `scripts/validate_pipeline.py`, `scripts/cleanup_facts.py`, `scripts/preflight.py`
- 283 backend tests in `tests/`; golden rules in `tests/test_golden_iran_war.py`

## 5. Hard-won lessons V5 must not relearn
1. **"Tests pass" ≠ "output is good."** 283 green tests coexisted with losing the benchmark.
   Validate on accumulated real output, never on unit tests alone.
2. **One-scan benchmarks lie.** The product accumulates over 50+ scans; test the accumulated view.
3. **Free tiers cannot run this product.** They die mid-day and cause silent, confusing failures.
4. **Always start the backend with the venv** (`scripts/start-local.ps1`) — a system-python uvicorn
   silently crashed every LLM call for two days.
5. **Never let cost be invisible.** Months of spend went untracked because errors were swallowed.
6. **The signal scorer must run on a 70b-class model.**
7. **Building 10 months without a user in the loop is the root cause** of everything above.
