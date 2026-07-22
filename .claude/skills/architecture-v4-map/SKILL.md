---
name: architecture-v4-map
description: Map of the frozen V4 codebase (tag `v4-final` / branch `v4-archive`) — what was built, where it lives, and its keep/cut/replace verdict. ALWAYS use this before writing any V5 feature that sounds like something V4 already had (fact extraction, dedup/memory, judging, scheduling, scoring, briefs, story stitching, cost tracking). Port from V4 instead of reinventing it. Also covers the V4→V5 recovery commands and the hard-won lessons V5 must not relearn.
---

# V4 Archive — navigation map

**Hard rule: never rebuild a V4 feature from scratch.** V4 is 10 months of work, frozen at commit
`6f26fac` (tag `v4-final`, branch `v4-archive`). If a V5 task resembles anything below, read the V4
implementation first and port it. Full detail lives in `docs/core/V4_ARCHIVE.md` — read that when
you need the *why*; this file is the fast index.

## Recover any V4 code

```bash
git show v4-final:<path>                  # read a file as it was
git checkout v4-final -- <path>           # restore it onto main
git diff main v4-final -- <path>          # see what V5 changed
git switch v4-archive                     # browse the whole V4 tree
```

## Where things are, and whether to reuse them

| Feature you're about to build | V4 lives at | Verdict |
|---|---|---|
| Fact extraction (alpha_text + context + event_class JSON) | `harvester/harvester.py`, prompt in `llm/prompts.py` | **CUT the code, KEEP the prompt** — V5's Gemini Search call must reproduce the same JSON contract |
| Web search / article fetching | `collector/{tavily,brave,exa,rss,google_news}_layer.py`, `collector/extractor.py` | CUT — Gemini Search replaces it; port the layers only for the V5 hybrid experiment |
| Search query generation | `collector/query_builder.py`, `ledger/query_rotator.py` | CUT |
| Per-user dedup / "what's new" memory | `ledger/vector_store.py`, `ledger/delta_engine.py`, `llm/local_embedder.py` | **EVALUATE — leading stronghold**, verify on real data before V5 depends on it |
| Topic timeline (zero-LLM) | `ledger/history_doc.py` | KEEP |
| MERGE/UPDATE/NEW judging | `arbiter/arbiter.py`, `arbiter/judge.py`, `arbiter/contradiction.py` | EVALUATE — "keep only if needed" |
| Noise/relevance gating | `pipeline/signal_scorer.py` | EVALUATE — **must run on 70b-class**, 8b is incoherent |
| Adaptive scan cadence | `ledger/ayr_engine.py`, `tasks/scheduler.py`, `tasks/celery_app.py` | CUT for now — V5 uses manual alarm-clock scheduling; reintroduce post-production |
| Narrative bridges between facts | story-stitch prompts in `llm/prompts.py`, `fact_stitches` (migration 023) | CUT — hallucinated causation and corrupted a number |
| Brief / state-of-play generation | `briefer/briefer.py`, `briefer/state_of_play.py` | EVALUATE; **`V3_STATE_OF_PLAY` stays OFF — deliberate, do not re-enable** |
| All LLM prompts | `llm/prompts.py` | **KEEP — highest-value artifact**, all 9 stages, grouped, with a runnable `__main__` sanity block |
| LLM provider calls / fallbacks | `llm/client.py` | KEEP |
| Cost & token tracking | `llm/pricing.py`, `ledger/telemetry.py` | **KEEP + FIX** — broken, see below |
| API keys / B2B | `apikeys/` (migration 026 **never applied to prod**) | KEEP dormant |
| Billing | `billing/paddle_service.py` (**never activated**) | KEEP dormant |
| Auth, digests, push | `auth/`, `digest/`, `push/` | KEEP |
| Frontend | `frontend/src/app/` — `(marketing)`, `dashboard`, `topics/[id]`, `settings`, `admin`, `developers` | KEEP, minus story mode |

## Known-broken in V4 (fix in V5, don't reproduce)

1. **Cost tracking is dead.** `llm_call_log`/`pipeline_run` + the 3 cost RPCs exist only in
   `ledger/schema.sql`, never in the numbered migration chain → likely absent from the live DB.
   `pricing.py` has no entry for `llama-3.3-70b-versatile` (silently bills $0). Search-API cost is
   tracked nowhere. `/admin/cost-summary` swallows errors and returns zeros, so "broken" and
   "free" look identical.
2. **No supersession.** `models/story.py`'s `StoryStatus.STALE` is never set by any code; the
   arbiter tags the new contradicting fact but never demotes the old one. Root cause of the stuck
   `noise_level` benchmark score.
3. **Staleness gate is anchored wrong.** `harvester.py` compares `event_date` to the *article's*
   publish date, not today — resurfaced old articles pass straight through.
4. **Briefer is date-blind.** Its payload omits `event_date`/`first_seen_at`.
5. **Two tier-floor sources of truth.** `api/routes.py` hardcodes pro=21600s; `models/tier.py` and
   the `tier_intervals` table say pro=3600s.

## Lessons V5 must not relearn

- "Tests pass" ≠ good output — 283 green tests coexisted with losing the benchmark (24 vs 33).
- One-scan benchmarks lie; validate the **accumulated** view over many scans.
- Free API tiers cannot run this product — they die mid-day and fail silently.
- Start the backend with the venv (`scripts/start-local.ps1`); system python silently kills LLM calls.
- Never let cost be invisible.
- **Building for 10 months with no user in the loop is the root cause of all of it.**

## Validation tools that stay valid

`scripts/quality_benchmark.py` (the Gemini-vs-us judge — **V5's success gate**) ·
`scripts/audit_topic.py` (dump all stored data for a topic — the real-data evidence tool) ·
`scripts/validate_pipeline.py` · `tests/test_golden_iran_war.py` (encoded quality rules).
