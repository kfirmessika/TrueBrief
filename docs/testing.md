# TrueBrief — Pre-Deploy Test Plan

> The real testing regimen we run **before** flipping anything live. "Real" = against the
> actual pipeline / LLM / Supabase, not MSW mocks (CLAUDE.md hard rule #7).
> Goal: catch a bad update or a quality regression *before* users see it.

## The three layers (cheapest → most thorough)

| Layer | What it proves | Cost | Command |
|---|---|---|---|
| **1. Preflight gate** | The deploy is *wired* right (secrets, model, DB, migration 012, /health) | $0 | `python scripts/preflight.py [--base-url URL]` |
| **2. E2E smoke** | A *real scan* produces a sane brief — dates, relevance, dedup, cost all behave | real LLM | `python scripts/smoke_scan.py --limit 2` |
| **3. Accuracy harness** (A.2, next) | Scoring *quality* holds: gate recall, precision@5 ≥ 80% vs a golden set | real LLM | *(to build — `tests/golden/`)* |

Unit tests (`pytest tests/`, `npm test`) gate every commit; the three layers above gate a **deploy**.

---

## Layer 1 — Preflight gate (`scripts/preflight.py`)

Fails loudly (exit 1) if the deploy isn't safe:
- required secrets present; LLM model is not a `-preview` build (the quota=0 trap)
- Supabase reachable; **migration 012 applied** (pipeline_trace + llm_call_log payload cols)
- with `--base-url`: backend `/health` 200 + a public API endpoint responds

Run it locally *and* against the Railway URL right after deploy, before flipping flags.

---

## Layer 2 — E2E smoke (`scripts/smoke_scan.py`)

Drives the **real** `PipelineRunner` (same wrapper as the Celery task: opens a `pipeline_run`,
sets the trace context, runs, finalizes), then reads the **trace** back and asserts quality
invariants. It dogfoods the A.7 trace panel — if the harness can't read a clean trace, neither
can the admin panel.

**Modes**
- `--dry-run` — wiring/config/DB/migration + `PipelineRunner()` construct only. $0, no scan. CI-safe.
- default — runs a real scan on each selected topic (`--topic-id ID …`, `--limit N`, or `--all`).

**Quality invariants checked per run** (from `pipeline_run` + `pipeline_trace` + `llm_call_log`):
- **completed** — `exit_status` is `success` or `no_update` (not `error`).
- **brief present** — if facts were harvested and status=success, the brief is non-empty.
- **date sanity** — no fact `event_date` is in the **future** (hard fail); large back-dates flagged
  (the "new to us ≠ new to the world" red light — §8B).
- **relevance gate ran** — when `V3_RELEVANCE_GATE` is on, the gate stage is present with a kept/dropped count.
- **dedup sane** — NEW/UPDATE/DUPLICATE breakdown present; not 100% NEW on a re-scan (would mean dedup is dead).
- **cost bounded** — total run LLM cost < $0.02 target (warn), < $0.10 hard ceiling (fail).
- **collection worked** — articles collected > 0 (0 ⇒ likely a quota/source outage → warn, blocks confidence).

Exit 1 on any **quality** violation. Infra/quota problems are reported distinctly (they block
confidence but point at ops, not code).

> Note: a real scan writes facts to the ledger (that's what a scan does) — it does **not** save a
> brief row, to keep the dashboard clean. Run against the existing topics or a throwaway one.

---

## When to run what

1. **Every commit:** `pytest tests/` + `npm test` (unit).
2. **Before deploy:** `preflight.py` (local) → `smoke_scan.py --limit 2` (local, real).
3. **Right after deploy, before flipping flags:** `preflight.py --base-url <railway>` → smoke a topic → read `/admin/runs`.
4. **Before paid launch:** add Layer 3 (accuracy harness) and require precision@5 ≥ 80%.
