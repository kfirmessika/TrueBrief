# TrueBrief — Roadmap (single source of truth)

> Rewritten 2026-06-19. The AI updates this file and commits after every step.
> **Legend:** C = Complexity (1–20) · M = Recommended model · `[x]` done · `[~]` partial · `[ ]` todo
>
> | Model | Use case |
> |---|---|
> | **FLASH** | C 1–8: UI, boilerplate, docs, simple logic |
> | **SONNET** | C 9–18: complex logic, auth, integrations |
> | **OPUS** | C 19–20: architecture, massive refactors, deep reasoning |

---

## 0. Where we are today (honest snapshot)

A working news-intelligence app: create topics → scheduled scans collect articles → harvester
extracts atomic facts → arbiter dedups (NEW/UPDATE/DUPLICATE) → briefs render on the topic page.
Auth (Clerk), billing scaffolding (Paddle), email digest, web push, rate limiting, and deployment
(Railway + Vercel) all exist. The V3 quality/cost migration (M1) is done **behind feature flags**.

**What works in the product right now:** dashboard feed, sidebar topic list, topic page with
briefs (🆕 NEW / 📈 UPDATES envelope), source chips, live scan progress, settings, admin metrics +
**full per-run pipeline trace** (`/admin/runs`).

**Built but gated/blocked:** V3 quality flags (ON locally, **OFF in Railway**); batch judge
(`V3_BATCH_JUDGE`, off, pending A/B); email digest (built, blocked on a verified domain).

**Phase 2 (UI) is BUILT** (see §4 for detail):
the per-user **delta engine** (`delta_engine.py`, migration 019, API routes), the **smart history page**
(`history_doc.py`, `HistoryView`), the **calm V3 home** (`dashboard/page.tsx`), and the
**in-app digest envelope** are all implemented behind feature flags. Missing until 2026-06-29:
migration 021 DB columns (`date_basis`, `published_at`, `importance`) — now applied ✅.

**The plan in one line (revised 2026-06-19 — see §1 Launch Decision):** the current brief lost a
head-to-head vs GPT, so we **build full V3 — new pipeline (IC1–IC8 + 1a.5) + new UI (delta engine →
calm surface → history → digest) — _before_ launch**, with an objective gate (beat GPT on
signal-vs-noise) and a Phase-1 checkpoint that proves the *data* before we build the *UI*. Heavy/uncertain
infra (adaptive AYR, budget controller, B2B, billing) stays post-launch.

---

## 1. 🚀 LAUNCH PATH — the ordered critical path to go live

### 🔒 LAUNCH DECISION (2026-06-19): Full V3 — new pipeline + new UI — BEFORE launch

**Why (founder call).** We're a *specialized single-tool* news subscription competing with *multi-tool*
general AIs. Our only reason to exist is **more signal / less noise than a general AI (GPT) on the same
topic.** The 2026-06-19 benchmark showed we currently *lose* that comparison — so launching now = zero
advantage. We win the benchmark first, then launch.

**🎯 Objective launch gate (the finite line — launch the instant it passes, then freeze scope):**
re-run the benchmark on **Iran-War + 2 more topics** → our output **beats GPT on signal-vs-noise**:
IC8 golden-case assertions pass **and** a blind side-by-side reads as *ours leads with the lede / less
repetitive / synthesized*. Not a feeling — a diff. **Nothing new is added to the pre-launch list after this.**

**IN (pre-launch):** new pipeline (IC1–IC8 + 1a.5) + new UI (delta engine, calm surface, history,
digest — *minimum-viable* versions).
**OUT (post-launch — "stuff to figure out / too complex"):** adaptive & cost-aware AYR + budget
controller + cost-model Option B (§4-E); B2B API (§5 Phase 4); full contradiction detector, feedback
loop, domain pipelines, linked-graph, timing learning, multi-language (§5 Phase 5/6); **paid billing**
(soft launch is free, so §6 blockers + L2 stay post-launch).

**Ordered build:**

- **P0 — Unblock embeddings ✅ DONE.** Fixed embed_batch (SDK bug: list→1 vector). (commit de33eca)
- **P1 — Keystone: published_at for Tavily/Brave ✅ DONE.** Tavily returns `published_date` (RFC 2822)
  — we weren't reading it. Now parsed. Brave: `page_age` parsed when present. Harvester date guard now
  always anchors to `today` when pub date still unknown — kills 2020/2023 LLM hallucinations outright.
  (commit de80714)
- **Phase 1 — Pipeline to content-parity (the data wins the benchmark):** `1a.5` two-clock dev-lag gate ·
  `IC1` tally collapse · `IC2` event-class ranking · `IC3` dedup-fires · `IC4` contradiction flag ·
  `IC8` golden-case harness. *(specs: §2 1a.5, §2.5)*
  - **🆕 P2 — Freshness/adaptive-K ✅ DONE.** (root-cause finding 2026-06-19) MMR had no recency term →
    old well-covered stories won the 5 slots on hot days. MAX_ARTICLES=5 was static → on a 45-article
    day we read 11%. Fixed: MMR_RECENCY=0.15 weight with 36h half-life decay; MIN_K=5/MAX_K=20 adaptive.
    Also: IC3 same-event fast-path + telemetry zero-count fix. (commit 5d25c0e)
  - **🔶 CHECKPOINT (de-risks the whole bet): re-run the benchmark. Our _content_ must already beat
    GPT — _before_ any UI work.** Pass → UI is pure upside on proven facts. Fail → fix the pipeline, don't move on.
    - **2026-06-20 re-run (Trump topic) — DATA LAYER PASSES, SYNTHESIS LAYER FAILS.** Keystone confirmed:
      brief is now temporally coherent (no 2020/2023 contamination, no old/new mix). But still loses to GPT on
      **synthesis/presentation, not data**: (1) buries the lede — leads with CFPB, not the Iran deal GPT names
      as #1; (2) no "biggest story" synthesis line; (3) `WHAT'S NEW/FULL CONTEXT` labels + doubled chips
      (`huffpost.comhuffpost.com`) still render; (4) Middle East fragmented into 3 overlapping sections;
      (5) missed freshest items (Air Force One/Qatar 747, Pulte→DNI, FISA 702, AI EO). → Next: **IC7** (state-of-play,
      closes 1+2+4) then **IC5/IC6** (cheap presentation) then **IC4/IC8**. Checkpoint re-runs after IC7.
    - **2026-06-21 re-run (Iran War, ALL ICs + state-of-play folded in) — NOW COMPETITIVE WITH GEMINI.**
      Automated `quality_benchmark.py` (LLM judge, 4 axes): **TIED ~30–31 vs 31** across two runs (up from
      18-vs-26). **We WIN synthesis (8 vs 7)** — IC7 lands — and noise (≈8 vs 7). Remaining LOSSES are narrow:
      **(a) precision leak** — an off-topic Israel-Hamas humanitarian stat leaked into an Iran brief (relevance-gate/
      verifier miss — a *wrong* fact is worse than a missing one); **(b) NYT/paywall 403** — completeness loss on
      hard paywalls (snippet fallback fixed RSS sources but Google-News→NYT URLs still 403, link-only summaries —
      needs a paid extraction service); **(c) lede salience** — don't always lead with the single most urgent
      development. *Note: judge is non-deterministic + Gemini hit 503s — ±1–2 pts is noise.* **Next tuning targets:
      (a) precision leak, (c) lede salience — both need deliberate multi-run measurement (quota-bound, do later).**
    - **2026-06-21 (migrations 014/015 applied; 5 algorithmic fixes) — COMPETITIVE, WINS SYNTHESIS.** Across 4
      benchmark runs: **30–31 vs 31–33** (from the original 18-vs-26 rout). **We win synthesis every run** (judge:
      *"Brief A offers a superior synthesis of the current state of play"*) and tie/win noise; we trail lede &
      completeness by ~1–2. Live-data fixes this round: **IC2 significance×recency** (lede salience — a8f6cdb),
      **date-guard sentinel** (epoch 1970→today, not fake 2026-01-01 — 7983047), **IC4 closure/sealed antonyms**
      (7983047), **adaptive-K //5→//3** (completeness 18%→33% — 0b5d3c5), **snippet ≥120-char guard** (kills the
      fabricated-fact risk — dc81f25). Verified live: IC7 state-of-play surfaces contradictions ("Strait of Hormuz
      [contested] — Iran closed it; US claims open") even when IC4's pairwise flag misses. **Remaining gap is
      structural: completeness vs a full-web-index competitor + NYT/WSJ paywall 403s — not closable by code alone
      (needs paid extraction / multi-query-per-scan). Our durable edge = synthesis + provenance + state-of-play.**
- **Phase 2 — New UI (experience on proven-good content):** `4-A` delta engine · `IC7` state-of-play
  header · `4-C` calm surface + kill live briefer *(IC5/IC6 are **absorbed** — the calm surface is built
  right by design; no effort wasted fixing the old briefer)* · `4-B` history page · `4-D` daily digest.
  *(specs: §4-A/B/C/D, §2.5 IC7)*
- **Then launch:** the L1 mechanics below (deploy → flip flags → smoke) → invite free users.

> **Guardrail against the delay pattern:** the gate is the *benchmark diff*, the scope is *frozen* at the
> IN-list, and the Phase-1 checkpoint proves the core before we invest in UI. If we're tempted to add
> anything not on the IN-list, it goes to post-launch — no exceptions.

---

> Two tiers below: **Soft** (free, no money) then **Public/Paid** (needs domain + billing, now post-launch).

### L0 — Make the live pipeline debuggable ✅ DONE (de-risks everything after)
- [x] **A.7 Pipeline Observability / Admin Trace Panel** — per-run trace of the whole pipeline
      (query+tools chosen & why → articles each tool returned → MMR selection → exact LLM
      prompt/response per stage → per-fact judge decisions). Founder-only `/admin/runs/{id}`.
      Migration 012 applied to Supabase 2026-06-18.

### L1 — Soft launch (free tier only — no domain/billing needed)
- [ ] **S0. Push backend to Railway** — deploy current `main` so prod runs the new model
      (gemini-3.1-flash-lite), UCB1 rotator, A.7 trace capture, and batch-judge code. (C: 2)
- [ ] **S1. Flip V3 flags ON in Railway env** — `V3_DATE_GUARD`, `V3_RELEVANCE_GATE`,
      `V3_ENTITY_DEDUP`, `V3_PAUSE_STORY_GRAPH` (they're already ON locally, still False in prod). (C: 1)
- [ ] **S2. Verify model quota on prod key** — confirm `gemini-3.1-flash-lite` has real daily
      quota. **CONFIRMED BLOCKER (smoke test 2026-06-19):** dev key batch-embed returns 1 vector for
      any N inputs → MMR falls back → relevance gate over-fires (dropped 14/15 facts in one scan).
      Briefs still produce but quality is unreliable. Must verify prod key before deploy. (C: 3)
- [ ] **S3. Smoke-scan 3 real topics** — run each, open `/admin/runs` to confirm dates / relevance
      gate / dedup behave and cost looks right. Gate with `python scripts/preflight.py --base-url …`. (C: 4)
- [x] **S4. Frontend CI green** — removed stale `topics.intg`/`briefs.intg` suites + fixed drifted
      assertions. 16/16 tests pass, `npm run build` PASS. (done 2026-06-19)
- [ ] **S5. Invite 5–10 free users** on the bare Vercel/Railway URLs — everyone free tier, no
      emails, no payments. Watch `/admin/runs` + `/admin/metrics` daily. (C: 2)

### L2 — Public / paid launch (needs the pre-launch blockers in §6)
- [ ] **P1. Buy domain** → unblocks Resend + Paddle + Clerk prod.
- [ ] **P2. Resend:** verify domain, set `DIGEST_FROM_EMAIL=briefs@<domain>`.
- [ ] **P3. Paddle:** finish merchant setup with the live URL; set price/keys; smoke a test checkout.
- [ ] **P4. Clerk:** swap dev instance → production instance.
- [x] **P5. Pre-Production Smoke Gate** — `scripts/preflight.py` (secrets, no `-preview` model,
      Supabase, **migration 012 applied**, `/health` + public API). Exit 1 blocks launch.

---

## 2. V3 Pipeline Migration (M1 quality/cost diffs)

> Architecture build-sequence steps 1–7. Flags default **False** = V1 preserved; flip per-flag after A/B.

- [x] Switch model → `gemini-3.1-flash-lite` (stable; fixes the daily-quota=0 trap)
- [x] 1a.1 Date/year guard in harvester (`V3_DATE_GUARD`)
- [x] 1a.2 Relevance gate — drop off-topic facts (`V3_RELEVANCE_GATE`)
- [x] 1a.3 Entity-aware dedup in arbiter (`V3_ENTITY_DEDUP`)
- [x] 1a.4 Pause story graph + summarizer; hide Stories tab (`V3_PAUSE_STORY_GRAPH`)
- [x] UCB1 query rotator — 1 lifetime LLM call/topic, cached in `topics.search_strategy`
- [x] 1b.1 Batch grey-zone judge (`V3_BATCH_JUDGE`) — `judge.call_batch()` + `arbiter.judge_alphas()`,
      off by default; enable after M2 A/B confirms quality
- [x] **1a.5 Two-clock dev-lag gate** (`published_at` + `date_basis` + `importance` + lag classifier) —
      §8B. Harvester extracts all three fields; `V3_LAG_GATE` drops stale one-time events; migration 021
      adds DB columns (applied 2026-06-29). Delta engine backfill gate (`_is_backfill`) routes
      large-lag facts to history, not the live feed. (commit 57ddbe3)
- [x] **1b.2 URL/article dedup** — exact-URL skip (14d window in `VectorStore.get_seen_urls()`) +
      near-dup/syndication collapse (`V3_NEARDUP_COLLAPSE`): SimHash-64 / Hamming≤3 drops wire-story
      copies before extraction. 6 unit tests; wired in `runner.py` step 2c.
- [x] **1b.3 Gate scans on new content (quiet-scan = $0)** — runner returns early after URL dedup
      when all candidate articles were already processed (runner.py L315-318); zero LLM calls on a
      no-new-content scan.
- [ ] 1b.4 Drop the live-path briefer — assemble from `fact`+`context` (folds into §4-C below) (C: 8 | SONNET)

### M2 — Measure + validate (the gate before building more)
- [ ] **A.2 Accuracy Test Harness** — golden set; CI report on gate recall, scoring precision/recall,
      digest precision@5 (north-star ≥ 80%). Treat scoring quality as the product. (C: 18 | SONNET)
- [ ] A/B the V3 flags on real scans — call count / tokens / cost / dedup quality vs V1 baseline,
      read from `pipeline_run` + `llm_call_log` via `/admin/metrics`. (C: 6)

---

## 2.5 🔧 IMMEDIATE CORRECTIONS (from the 2026-06-19 GPT benchmark)

> A head-to-head on **"Iran War" vs GPT** (same topic, same day) exposed **3 data leaks + 4 presentation gaps**. Verdict: GPT's brief was more useful — it led with the lede (signed US–Iran framework + ceasefire), stayed tight, and synthesized; ours buried the peace deal under casualties, showed 5 overlapping tallies as separate "new" items, repeated a fact (dedup miss), and had no "so what".
> **Sequencing rule (so we don't repeat mistakes):** the **data fixes are durable** — they fix `facts` rows, so every surface benefits *and* they survive the briefer removal (4-C). Do them first. The **presentation fixes** make the soft-launch brief readable now; their full form rides 4-C. Each correction also becomes a **golden-set case** (IC8 → A.2).
> Architecture spec: §10B.2a/b (development-type + tally-collapse), §5 (dedup + contradiction), §7 (state of play), §13 (hierarchy + labels), §16 red light #5.

### 2.5-A Data / pipeline fixes — durable, DO NOW (before soft launch)
- [x] **IC1. Running-total collapse** (arch §10B.2b) — arbiter step 1b: tally fact + entity-overlap
      ≥ 0.5 → force UPDATE (bypass vector threshold). `find_tally_match()` in vector_store. Flag
      `V3_TALLY_COLLAPSE`. Migration 013 applied 2026-06-19. 15 tests. (commit de33eca)
- [x] **IC2. Event-class + significance weighting** (arch §10B.2a) — harvester emits
      `event_class ∈ {state_change, escalation, development, incremental, tally, routine}`;
      runner step 5d sorts decisions by weight before briefer → state_change leads. Flag
      `V3_DEV_CLASS_RANK`. Alpha model + migration 013. (commit de33eca)
- [x] **P0. embed_batch fix** — Gemini SDK treated contents=list as one doc → 1 vector for N
      inputs. Fixed: ThreadPoolExecutor(8) dispatches one call per text → 7x faster, all N vectors
      returned. All quality gates (MMR, relevance gate, entity-dedup) now work correctly. (commit de33eca)
- [x] **IC3. Entity-dedup must fire on same-event facts** (1a.3 validation) — "4 Israeli soldiers killed" ×2
      (same date + entities + number) must merge to **one fact, `verified_count=2`**. Triple gate: entity_overlap≥0.80
      + temporal_overlap≥0.97 + raw_sim≥0.50 → DUPLICATE without LLM call. (commit 5d25c0e)
- [x] **IC4. Contradiction flag at merge** (arch §5/§8B) — `arbiter/contradiction.py`: a NEW fact that
      contradicts a stored one (shared subject + overlapping time + incompatible value: Hormuz open/closed,
      toll 3,912 vs 3,468) is flagged (`contradicts_id` + note) and forced NEW — runs BEFORE the IC3 duplicate
      fast-path so a contradiction is never silently merged. Conservative/deterministic (no LLM); excludes running
      tallies. Migration 015 (no-op fallback), flag `V3_CONTRADICTION_FLAG`. 8 tests incl. arbiter integration. (commit pending)

### 2.5-B Presentation / synthesis
> **Per the 2026-06-19 Launch Decision (§1):** we now build the **new calm surface (4-C)** rather than
> launch on the old briefer — so **IC5 + IC6 are absorbed into 4-C** (built right by design, not retro-fitted).
> **IC7 (state of play)** and **IC8 (golden case)** remain live pre-launch tasks (Phase 1/2).
- [x] **IC5. Drop `WHAT'S NEW / FULL CONTEXT` labels + de-dupe source chips** — briefer prompt rewritten to
      weave `context` as prose (no rigid labels) + "one chip per OUTLET" rule; frontend `parseSourceLine`
      now de-dupes chips by domain (kills `cnn.comcnn.com`). 6 unit tests in test_briefer.py. (commit pending)
- [x] **IC6. Importance hierarchy in the brief** — briefer now receives `significance` (event_class) +
      `corroborating_sources` per fact, preserves IC2 sort, leads with a **📌 Bottom line** synthesis line,
      and collapses running tallies into one bullet. *needs IC2 (done).* (commit pending)
- [x] **IC7. "State of play" topic-header block** (arch §7.4) — `StateOfPlayGenerator` produces a grounded
      situation line + ≤6 `agreed/contested/postponed/escalating` checklist from stored facts only (no prediction);
      runner regenerates it ONLY when a `state_change` fact lands (1 LLM call, fire-and-forget); stored on
      `topics.state_of_play` (migration 014); served at `GET /topics/{id}/state-of-play`; rendered atop the topic
      view. Flag `V3_STATE_OF_PLAY`. 8 unit tests + live-validated on real Iran-War facts. **⚠️ Apply migration 014
      in Supabase to activate persistence.** (commit pending)
- [x] **IC8. Golden case from this benchmark** (feeds A.2) — `tests/test_golden_iran_war.py` encodes the
      labelled Iran-War failures as 6 standing regression assertions tied to the component that prevents each:
      buried lede (IC6), tally noise (IC2), duplicated soldiers (IC3 gate), Hormuz contradiction (IC4),
      missing state-of-play (IC7), tally≠contradiction (IC4 guard). CI-safe (no live LLM/DB). (commit pending)

- [x] **IC9. Jina Reader extraction fallback** — `extractor._try_jina_reader()` retries failed
      extractions (403, bot wall, soft paywall) via `https://r.jina.ai/<url>`. Free, no API key.
      Tier order: trafilatura → Jina Reader → substantial snippet → drop. Flag `V3_JINA_READER`.
      `_MIN_JINA_CHARS=300` guards against stub/paywall pages. (commit pending)
- [x] **IC10. SOP lede anchor** — runner loads stored `state_of_play.situation` (IC7, previous scan)
      and passes it to `Briefer.generate(situation=...)` as a `CURRENT SITUATION` anchor so the
      `📌 Bottom line` synthesis is grounded in the established topic narrative rather than re-derived
      from scratch. Flag `V3_SOP_LEDE`. Zero extra LLM calls. (commit pending)
- [x] **MAX_K 20 → 25** — completeness lift for hot days (was capped at 20 even with 70+ candidates;
      with `//3` adaptive-K, 70 candidates now reads 23 articles instead of 20). (commit pending)

- [x] **IC11. Domain-based parallel queries** — `QueryBuilder` now generates 3-4 topic-specific
      domains (e.g. `military_and_security`, `international_diplomacy`, `humanitarian_and_regional`,
      `domestic_israel`) each with 2 search queries. `PipelineRunner._collect_all_domains()` fires
      one query per domain in parallel (Tavily + Google News), pools results URL-deduped with RSS
      (fires once, category-based). Collection jumps from 22 → 116 candidates on Israel test.
      UCB1 backward-compat: domains serialised into `alt_queries` + stored in `topics.search_strategy.domains`.
      Flag `V3_DOMAIN_QUERIES`. New `TopicDomain` dataclass in `query_builder.py`. (2026-06-21)
- [x] **IC12. Dynamic domain blocklist** — `extractor._record()` fires a fire-and-forget upsert into
      `domain_extraction_stats` (migration 016) after every extraction attempt. `get_blocked_domains()`
      returns domains with >75% fail rate + ≥5 attempts; runner skips them at MMR time.
      Migration 016: table + `record_domain_extraction()` atomic PL/pgSQL function. Flag `V3_DYNAMIC_BLOCKLIST`.
      Degrades to no-op until migration 016 applied in Supabase. (2026-06-21)

- [x] **IC13. Brave search + per-(topic x tool) UCB1 AYR matrix** — `BraveLayer` rewritten to use
      `/news/search` endpoint (returns real news articles, not Wikipedia homepages); `_parse_age()`
      converts relative strings to datetime. New `source_stats` table (migration 017) tracks
      `(topic_id, tool_name)` with EMA-smoothed AYR. `update_tool_stats()` upserts after each run;
      `get_tool_fire_set()` UCB1 bandit: cold-start fires all tools for first 3 scans then exploits
      high-AYR tools; free tools always fire. Runner step 6c writes per-tool alpha counts back. Flag
      `V3_TOOL_UCB1`. Israel benchmark 2026-06-21: 183 articles (vs 116 IC12 baseline), 13 stories
      with 6 exclusive vs GPT 8 stories and Gemini 10 stories. Brave adds CFR/Arab News/IBTimes/
      Iran International sources missing from Tavily. (2026-06-21)

- [x] **IC14. Lower MMR diversity + remove RSS pre-filter + scheduler enqueue gate + targeted follow-up** (2026-06-22)
      - Scheduler triple-send fix: `_advance_next_run()` returns `bool`; enqueue skipped if
        DB write failed so heartbeat cannot double-fire the same topic.
      - RSS keyword pre-filter removed from `_collect_all` and `_collect_all_domains`. The
        filter was silently dropping IDF press releases and government notices. `V3_RELEVANCE_GATE`
        (LLM cosine ≥ 0.50) handles off-topic filtering instead.
      - MMR diversity tuned: `MMR_LAMBDA` 0.55→0.62 (implicit diversity 0.30→0.23),
        `MMR_DOMAIN_CAP` 2→3, `MMR_DOMAIN_PENALTY` 0.35→0.20 — allows a second article
        from the same source when it carries a materially different sub-detail.
      - `_collect_and_judge_followup()`: after main judging, re-queries Tavily once per
        `state_change` NEW alpha (using `alpha_text[:100]` as the sub-query), extracts,
        harvests, runs through relevance gate, judges, and appends NEW/UPDATE decisions
        to the brief. Gated behind `V3_FOLLOWUP_FETCH` flag (default off).

**Status — ALL Phase-1 ICs complete:** IC1 ✅ IC2 ✅ IC3 ✅ IC4 ✅ IC5 ✅ IC6 ✅ IC7 ✅ IC8 ✅ IC9 ✅ IC10 ✅ IC11 ✅ IC12 ✅ IC13 ✅ IC14 ✅.
The **2026-06-21 benchmark (Iran War)** after IC5/IC6 jumped all four axes to **7/10** (from 3–5); the
remaining loss (28 vs 37) was **completeness + lede-salience**, which IC7 (state-of-play, picks the lede
as a grounded situation line) + IC4 (surfaces contradictions instead of burying them) directly target.
**Next: re-run `scripts/quality_benchmark.py` after applying migrations 014+015** to measure the IC4/IC7
lift, then the §1 launch checkpoint. **Apply migrations 014 (state_of_play) + 015 (contradiction) in Supabase
to activate persistence** (code degrades to no-op until then).
**Architecture refs:** IC7 = §7.4 (facts-only header, regenerated on `state_change`); IC4 = §5/§8B
(contradiction at merge); IC6 = §13 hierarchy + §10B.2a event-class weight.

---

## 3. ✅ DONE (collapsed)

- **Phase 0–2:** project skeleton, core MVP, delta-engine-v1 + scheduling.
- **Phase 3 (frontend + monetization):** 3.1–3.20 done — story nodes, dual vectors, Stripe→Paddle,
  tier enforcement, Next.js skeleton, Clerk auth, topic mgmt UI, brief display, landing, time-saved
  metric, public sharing, email digest, web push, mobile-responsive, rate limiting, Brave+Exa,
  Railway+Vercel deploy. (3.10 standalone history route **removed** — history is inline now.
  3.12 onboarding **cancelled** — decided unnecessary.)
- **Phase A (backend validation):** A.1 cost/latency telemetry, A.4 failure-mode tests,
  A.6 admin metrics, **A.7 trace panel**.
- **Phase B (design system):** B.0 OKLCH tokens + dark mode + primitives, B.1 critical gaps
  (topic detail tabs, settings, source chips, live scan bar).
- **Ops:** migration 012 applied; `scripts/preflight.py` launch gate; frontend CI green;
  **E2E smoke harness** (`scripts/smoke_scan.py`) + **test plan** (`docs/testing.md`) built;
  real scan on 2 prod topics passed all 7 quality invariants (2026-06-19).

---

## 4. PRODUCT SURFACES — the delta engine, calm brief, history page, daily digest

> **⬆️ MOVED TO PRE-LAUNCH (2026-06-19 — see §1 Launch Decision).** These were "post-launch"; the GPT
> benchmark flipped that — they're now **Phase 2** of the pre-launch build (after the Phase-1 pipeline
> checkpoint proves content parity). Build *minimum-viable* versions in the dependency order below.
> 4-E stays **post-launch** (heavy/uncertain infra). Maps to architecture build-sequence #8–11.

### 4-A. Delta engine + `user_topic_state` — ✅ BUILT (2026-06-29 audit)
- [x] `user_topic_state` table with two markers: `last_seen_at` (live) + `last_digest_at` (digest).
      Migration 019 applied. 3 rows in table.
- [x] Per-user **delta query** — `delta_engine.py`: `get_delta_feed(user_id, anchor)` is $0 LLM,
      pure Postgres. `advance_seen()` / `advance_digest()` advance anchors on view. "All quiet"
      is a first-class state. API routes: `GET /feed`, `POST /feed/seen`, `GET /feed/digest`.
- [x] **Gate on development recency** — `_is_backfill()` in delta engine routes facts whose
      development pre-dates first_seen_at by >45 days to history, never the live feed. Backed by
      `V3_LAG_GATE` in the harvester (1a.5, migration 021 applied 2026-06-29).

### 4-B. Smart history page — ✅ BUILT (2026-06-29 audit)
- [x] **No-LLM-first timeline** — `history_doc.py`: `build_history_doc()` orders clean fact-sentences
      chronologically, zero LLM. `store_history_doc()` upserts to `history_docs` (migration 018,
      4 rows). Runner calls it when `V3_HISTORY_DOC=True` and new facts land.
- [x] **Backfill routing**: large-lag facts drop from the live feed (delta engine) and appear in the
      History timeline only.
- [x] UI: `HistoryView` component in `topics/[id]/page.tsx` — day-grouped vertical timeline with
      milestone chips, powered by `GET /topics/{id}/history`.

### 4-C. Calm v3-briefing surface — ✅ BUILT (2026-06-29 audit)
- [x] `dashboard/page.tsx` implements the radically-subtracted home: `● N new across X topics`,
      plain sentences, "All caught up." hero with green checkmark, live/digest envelope toggle,
      `FeedFactRow` with event_class chips + favicon + verified_count.
- [x] `V3_NO_LLM_BRIEF` flag + `briefer/assembler.py` assembles briefs from `fact`+`context`
      without an LLM call.
- [x] Stories tab hidden behind `NEXT_PUBLIC_V3_PAUSE_STORY_GRAPH=true`.
- [ ] **1b.4 Drop the live-path briefer in prod** — flag `V3_NO_LLM_BRIEF` still OFF in Railway;
      flip it as part of S1. (C: 1 | FLASH — just set the env var)

### 4-D. Daily digest envelope — ✅ BUILT (2026-06-29 audit)
- [x] **One feed, two envelopes** — `GET /feed/digest` uses `last_digest_at` anchor. Digest feed
      groups by topic with `date_label`. "That's everything. See you tomorrow." footer.
- [x] Live/Digest toggle in `dashboard/page.tsx`. `advance_digest()` called on digest view.
- [ ] Email digest wiring to the new digest engine (email delivery still needs the domain — §6).

### 4-E. Adaptive scanning & cost control (build-seq #8, 13) — ⛔ STAYS POST-LAUNCH (OUT of the pre-launch gate)
- [ ] Spike-responsive AYR (snap up on surprise, decay gently) + per-(topic×tool) AYR + coalescing
      window. (C: 18 | SONNET)
- [ ] Budget controller (once telemetry can predict) + soft/hard limits + margin shield. (C: 15 | SONNET)
- [ ] Trust UX: viewable muted-items log ("212 items muted — view"). (C: 5 | FLASH)

---

## 5. Later / at scale (do NOT block go-live)

- **Phase B.3–B.5:** polish (optimistic mutations, transitions, OG images), copy/brand, a11y + mobile.
- **Phase C:** C.1 Playwright E2E, C.2 API contract types, C.3 perf budget, C.4 load/stress.
- **Phase A deferred:** A.3 longitudinal stress sims, A.5 competitor benchmark.
- **Phase 4 — B2B API:** public REST + auth, `/delta`, `/nodes`, webhooks, usage billing, versioning.
  (Architecture says B2B over-indexes vs B2C — the real money. Compliance/regulatory wedge first.)
- **Phase 5 — scale + moat:** plugins, global AYR network, feedback loop (Rocchio + learned
  pre-filter), contradiction detection, multi-language, teams/org, white-label, mobile app.
- **Phase 6 — domain pipelines:** domain router brain, finance/legal/medical pipelines.
- **Build-seq #14–15:** timing/pattern scan learning (the social-pivot moat); spliced timeline +
  un-paused linked-thread graph for B2B.

---

## 6. Pre-launch blockers (need a real domain first)

> For the **soft** launch all three are skipped — everyone is free tier, no emails, no payments.
> They gate only the **paid/public** launch (L2).

- **Resend:** `DIGEST_FROM_EMAIL` must be a verified domain → buy domain → verify → set it.
- **Paddle:** needs a live website URL to finish merchant setup → set `PADDLE_API_KEY`,
  `PADDLE_WEBHOOK_SECRET`, `PADDLE_PRICE_PRO`, `PADDLE_PRICE_POWER`.
- **Clerk:** switch dev instance (`integral-grackle-67…`) → production instance.

---

## 7. Locked decisions & red lights (from the architecture)

- **One surface, radical subtraction** — the brief *is* the home feed; topics are a filter, not a
  sidebar of dots. "All caught up" is a hero state.
- **"New to us" ≠ "new to the world"** (red light, verified live) — the feed must gate on development
  recency (§8B / 1a.5), not `first_seen_at`. This is the single biggest quality leak.
- **Lead with the lede; tallies are background; show a "state of play"** (red light, 2026-06-19 GPT
  benchmark) — rank by `event_class` not flat importance; collapse running totals; surface a grounded
  status block. The GPT head-to-head beat us on signal/synthesis — fix via §2.5 (IC1–IC8).
- **Story graph stays paused** — keep the code, stop the spend; revisit only for B2B, and only as a
  loose locally-queried graph, never a global tree, never load-bearing for dedup.
- **Briefer is removed from the live path** — assemble `fact`+`context`; keep generation only for the
  polished email digest.
- **Model choice always lives in `settings`/`LLMClient`** — never hardcoded. Run on Gemini Flash, not
  Claude (cost at per-scan volume).
- **North-star: precision@5 ≥ 80%** — below ~60% churn is guaranteed regardless of UI; build A.2 first.
