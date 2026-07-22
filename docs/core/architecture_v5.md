# TrueBrief V5 — Architecture (Gemini-first)

**Written:** 2026-07-22 · **Supersedes:** `architecture_v3.md` (V3/V4 era, kept for reference)
**V4 is frozen** at tag `v4-final` / branch `v4-archive` — see `docs/core/V4_ARCHIVE.md` and the
`architecture-v4-map` skill. **Never rebuild a V4 feature from scratch; port it.**

> **This document is deliberately short.** V3's architecture doc was 36KB and unreadable, which is
> part of how the project drifted. If V5 needs a 36KB spec, V5 is wrong.

---

## 1. The one-paragraph thesis

Gemini Search grounding does collection + extraction better and ~10–50x cheaper than the custom
pipeline ever did (benchmark 2026-07-21: V4 scored 24, raw Gemini 33). So **Gemini Search becomes
the pipeline**. What Gemini *cannot* do is remember what it already told you — it re-surfaces the
same story every day, forever. **That memory is the entire product.** V5 = Gemini for the facts,
our memory for the "what's actually new for *you*."

## 2. Pipeline

```
 alarm-clock trigger (per topic, user-set times)
        │
        ▼
 ┌──────────────────────────┐
 │  Gemini Search grounding │  ONE call. "Updates on <topic> from <last_run> to now."
 │  → alpha+context JSON    │  Replaces: query_builder, all search layers, scraper, harvester.
 └──────────────────────────┘
        │  list[Alpha]
        ▼
 ┌──────────────────────────┐
 │  Memory / dedup (KEPT)   │  local BAAI embeddings → pgvector cosine → arbiter fast-paths
 │  + judge (SHRUNK)        │  LLM judge only for the narrow residual case (§5)
 └──────────────────────────┘
        │  NEW / UPDATE only
        ▼
 ┌──────────────────────────┐
 │  Store + delta feed      │  known_facts → per-user "what's new since you looked"
 └──────────────────────────┘
        │
        ▼
    Topic timeline UI  (history_doc, zero LLM)
```

Every stage not named above is **cut** (§6).

## 3. The Gemini Search contract

One grounded call per run. The prompt MUST return the exact JSON shape the memory layer already
consumes — i.e. the `Alpha` dataclass in `src/truebrief/models/alpha.py`. **Port the field
semantics from V4's harvester prompt** (`llm/prompts.py` → `build_harvester_prompt`); it encodes
hard-won rules (strip editorial clauses, attribution rule, drop-if-no-date) that took months to get
right. Do not re-derive them.

```json
[{
  "alpha_text":   "One verifiable event, no editorial clause.",
  "entities":     ["Entity1", "Entity2"],
  "event_date":   "2026-07-21",
  "date_basis":   "explicit | relative | inferred",
  "is_background": false,
  "context":      "Background NOT in alpha_text — prior state, stakes, omitted figures. \"\" if none.",
  "confidence":   0.95,
  "importance":   0.9,
  "event_class":  "state_change | escalation | casualty | development | incremental | tally | routine"
}]
```

- `source_url` / `source_name` come from Gemini's `grounding_metadata.grounding_chunks[].web`,
  not from the model's text output — this preserves the per-fact evidence trail.
- **`event_date` consistency is now critical** (see §4 fix 2): the prompt must anchor every date to
  an absolute calendar date and never re-date a previously-reported event.
- `context` keeps the 2026-07-21 rule: *additive background only, never a restatement of the fact,
  empty string if there's nothing genuinely new to add.*

## 4. Memory / dedup — KEPT, with three named fixes

**Verified on real data (2026-07-22, Phase 1):** the local BAAI/bge-base embedder cleanly separates
duplicates (cosine 0.978–1.000) from different events on the same topic (0.397–0.679) — a ~0.30
margin with zero overlap. The embeddings are trustworthy. The plumbing is sound. Keep
`ledger/vector_store.py`, `llm/local_embedder.py`, `ledger/delta_engine.py`, `ledger/history_doc.py`.

**But measured redundancy is still real:** iran war 22.1% of facts in a ≥0.90 near-dup pair, trump
10.5%, isreal 9.2% — and it reaches users (one live delta feed returned three facts all restating
the same blockade announcement).

**Root cause, traced exactly:** `arbiter.py:336-338` auto-merges on the *temporally adjusted* score.
`adjusted_similarity()` decays the score when the two facts' `event_date`s disagree — so two copies
of the *identical sentence* (raw cosine **1.0**) stored 24 days apart in extracted date fall below
`AUTO_MERGE_THRESHOLD` (0.97), skip every fast-path, land in the grey zone, and the judge (which
almost never returns MERGE) admits them as UPDATE.

| # | Fix | Where |
|---|---|---|
| 1 | **Auto-merge on RAW cosine ≥ 0.97 regardless of temporal adjustment.** Near-identical text is stronger evidence than a shakily-extracted date. Keep the adjusted-score path for everything below that. | `arbiter/arbiter.py` |
| 2 | **Make `event_date` stable at the source** — the Gemini prompt (§3) must not re-date a re-reported event. This is the upstream bug; fix 1 is the safety net. | `llm/prompts.py` |
| 3 | **Backstop reconciliation pass** per topic — a periodic sweep catching cross-run duplicates that slipped past per-insert checks (per-insert only compares against a top-N fetch). | new, small |

## 5. Judge — KEPT but SHRUNK

**Verified on 18 real ambiguous pairs (Phase 1):** the judge returned UPDATE on 16/18 — it behaves
less like a 3-way classifier and more like "always find a delta." ~78% of its calls were defensible;
a plain cosine-threshold rule matched its practical outcome on 12/18 (67%). Its real, non-replicable
win is one narrow pattern: **lexically similar but categorically different events** (e.g. "Trump
spoke at the Pennsylvania Defense Summit" vs "Trump attended a NATO summit" — cosine 0.76, a
threshold wrongly forces UPDATE, the judge correctly says NEW).

Its number-change wins (a hidden injury count, a corrected date) are already catchable **without an
LLM** by the existing `_digit_runs()` check in `arbiter.py` — that check is currently gated to
same-day pairs only.

**V5 design:**
1. Widen the non-LLM fast paths — extend the digit-run / entity-overlap checks beyond the same-day
   restriction (±3 days) so cheap math absorbs most of the judge's current volume.
2. Call the LLM judge **only** for the residual: moderate/high entity overlap where the facts may
   describe categorically different events.
3. Known risk to guard: the judge invents confident, specific deltas over unreliable dates. With
   fix §4.2 stabilising dates, this shrinks — but never let a judge delta introduce a number or date
   absent from both input facts.

## 6. Cut in V5 (reintroduce post-production only if proven)

| Cut | Why | Port back from |
|---|---|---|
| query_builder, Tavily/Brave/Exa/RSS layers, extractor/scraper | Gemini Search replaces all of it; free tiers dead, majors 403-block the scraper | `collector/` |
| Harvester (code) | Gemini does extraction. **The prompt survives** as the §3 contract | `harvester/` |
| Signal scorer | Gemini's own selection may make it redundant — prove before re-adding | `pipeline/signal_scorer.py` |
| AYR adaptive scheduler | Replaced by manual alarm-clock (§7) | `ledger/ayr_engine.py` |
| Story stitching / story mode | Hallucinated causation, corrupted a number | prompts + migration 023 |
| State of Play | Deliberately off since V4 — **do not re-enable** | `briefer/state_of_play.py` |

**Reintroduction rule:** nothing comes back without a test showing it beats V5-without-it. Port from
`v4-final`, never rewrite.

## 7. Scheduling — manual "alarm clocks"

Replaces AYR auto-scan. Each topic gets **1 run/day by default**; the user adds specific run times
(e.g. 12:00 and 20:00), as many as they want. Explicit, predictable, and it makes cost a function of
user intent rather than an adaptive loop nobody can see. Adaptive cadence returns post-production
only if users ask for it.

Also fix here: `api/routes.py` hardcodes pro=21600s while `models/tier.py` and the `tier_intervals`
table say 3600s. **`models/tier.py` is the single source of truth** — delete the hardcoded dict.

## 8. Cost telemetry — foundational, built in Phase 3 before anything else ships

V4 flew blind for months: the `llm_call_log` / `pipeline_run` tables and the 3 cost RPCs exist only
in `ledger/schema.sql` and were never added to the numbered migration chain, `pricing.py` has no
entry for `llama-3.3-70b-versatile` (silently bills $0), search-API cost is tracked nowhere, and
`/admin/cost-summary` swallows errors so "broken" and "free" look identical.

V5 requirements: a real migration creating the tables + RPCs · a price entry for every configured
model **plus a test that fails if any configured model lacks one** · per-call cost logging for the
Gemini Search call · the admin endpoint surfaces a telemetry-health status instead of silently
returning zeros.

## 9. Success gates

| Gate | Bar |
|---|---|
| Quality | `scripts/quality_benchmark.py` — V5 **beats** V4's 24 and closes on Gemini's 33 on the same topics |
| Noise | measured near-dup rate per topic **< 5%** (from 22.1% / 10.5% / 9.2%) |
| Cost | tracked, non-zero, and a small fraction of a cent per topic-day |
| Reliability | a week of scheduled runs with no silent failure |
| Founder read | the daily output is something you'd actually read — the gate that matters most |

## 10. Post-production roadmap (not now)

In rough order, each gated on evidence: adaptive cadence (from AYR) → signal scorer if noise
persists → the Tavily/Brave link-finding hybrid (agent finds links → hands them to Gemini) → story
mode only if narrative genuinely tests better than the timeline → the media/social flywheel
(auto-publish daily topic findings) as go-to-market.
