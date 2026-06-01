# TrueBrief — Pre-Deployment Plan

> **Status:** Approved with scope changes — see Decision Log below.
> **Author:** Drafted by Claude (Opus) on 2026-05-19. Updated 2026-05-21.
> **Scope:** Step 3.20 (Deployment) now runs FIRST. Phases A/B/C run post-deploy against live Railway + Vercel URLs.
> **Estimated total complexity:** 90+ points (roughly 4–6 weeks of focused work depending on which optional items survive review).

---

## Decision Log

### 2026-05-21 — Deploy First, Test Live

**Problem:** Running A/B/C validation on localhost is not viable. Celery workers and Redis stop whenever the PC sleeps or restarts. The A.3 longitudinal stress tests require 30 days of continuous uptime — impossible on a local machine.

**Decision:** Step 3.20 (Railway + Vercel deployment) is promoted to run **before** Phase A/B/C. All validation tests will target the live Railway backend URL. This is the only way longitudinal tests (A.3) and competitor benchmarks (A.5) can actually complete.

**Impact:** No change to what gets tested. Only when and where it runs.

---

### 2026-05-21 — UI/UX: Design Reference Required Before Implementation

**Problem:** Previous approach of implementing design improvements directly from text descriptions (B.0, B.1) produced results the founder found unprofessional. The root cause: no validated visual reference existed before coding began.

**Decision:** Phase B now requires a **B.REF step** before any further UI work. The founder must:
1. Use **Google AI Studio** (aistudio.google.com) or **Claude.ai Projects** (claude.ai) to generate HTML/screenshot mockups
2. Upload current UI screenshots and prompt for a redesign in the style of Linear or Vercel dashboard — clean, dark-first, information-dense
3. Iterate prompts until the result looks right in a browser
4. Bring the approved reference to Claude Code for 1:1 implementation

**Rule:** No B.2, B.3, B.4, or B.5 work begins without B.REF approved. Claude Code does not attempt freehand design improvements.

---

## 0 · Executive Summary

The current state of the system, after Steps 3.1–3.19:

| Surface | What's solid | What's not |
|---|---|---|
| **Pipeline core** | 5 source layers (Tavily, RSS, Google News, Brave, Exa) wired in; arbiter with 0.97 auto-merge + 0.75 grey-zone + LLM judge; story nodes with recursive summary; AYR auto-tunes scan interval; query rotator A/B-tests variants | No test for: hallucinated facts, summary rot over 20+ updates, false-duplicate at AUTO_MERGE, story-merge creep, embedding-batch mismatch recovery |
| **Cost telemetry** | None. We can guess ~8–13 LLM calls + 10–25 embeddings per scan, but we don't record actual token counts | No per-scan cost row, no per-tier P&L, no breakdown by pipeline stage |
| **Competitor data** | Zero. We have no objective evidence that TrueBrief beats Perplexity / ChatGPT Tasks / Feedly AI on delta, density, or cost | — |
| **Frontend** | Landing, onboarding, navbar, toast/confirm dialog, dashboard shell, share page — all genuinely polished | Topic Detail page is **still a stub** (`"Brief content rendering is arriving in Step 3.9. For now…"`); Story Nodes / AYR / Query Variants have zero UI; Settings page has only the push toggle; no skeletons, no Framer Motion, no dark mode, no command palette |
| **Integration tests** | 106 unit tests, all passing; one synchronous backend benchmark ([master_benchmark_v2.py](tests/master_benchmark_v2.py)) that exercises 21 single-shot scans | No E2E browser test; no contract test between frontend/backend; no perf budget; no staging smoke |

**The plan in one sentence:** deploy to Railway first so the engine runs 24/7 → validate it works long-term and outperforms competitors → redesign the UI from a founder-approved visual reference → wire it all up with E2E tests.

**Phase order (updated 2026-05-21):**
1. **3.20 Deployment first** — Railway + Vercel. Required for everything else to run continuously.
2. **Phase A** — Backend validation against the live app. A.3 longitudinal tests need 24/7 uptime.
3. **Phase B** — UI redesign. Requires B.REF (founder-validated mockup) before implementation.
4. **Phase C** — E2E tests against the final UI.

**Do not run A/B/C tests on localhost.** The app will not stay up long enough.

---

## Phase A · Backend Validation & Competitive Benchmark

**Goal:** prove three claims with numbers, not vibes.
1. The engine is **accurate** (delta detection works, no hallucinations, no summary rot).
2. The engine is **affordable** (per-brief cost stays under $0.02 at PRO frequency).
3. The engine is **better than** Perplexity / ChatGPT Tasks / Feedly AI on a head-to-head benchmark.

### A.1 · Cost & Latency Telemetry (foundation — blocking everything else)

Without this, every other A-section number is a guess. Build first.

| # | Deliverable | Files | Success criteria | Complexity |
|---|---|---|---|---|
| A.1.1 | `pipeline_run` table: one row per scan, with topic_id, started_at, duration_ms, articles_collected, articles_selected, alphas_extracted, decisions (NEW/UPDATE/DUPLICATE counts), brief_length, exit_status | [src/truebrief/ledger/schema.sql](src/truebrief/ledger/schema.sql) | Row inserted on every scan, even failures | 8 |
| A.1.2 | `llm_call_log` table: one row per LLM call, with pipeline_run_id, stage (query_builder/harvester/arbiter/summarizer/briefer), model, input_tokens, output_tokens, cost_usd, duration_ms | [src/truebrief/ledger/schema.sql](src/truebrief/ledger/schema.sql) | Wired into [llm/client.py](src/truebrief/llm/client.py) as a single instrumentation point | 10 |
| A.1.3 | Cost rate card (Gemini Flash Lite Preview): hard-coded constants in [llm/client.py](src/truebrief/llm/client.py); used to compute `cost_usd` per call | new `llm/pricing.py` | Matches Google's current price page | 2 |
| A.1.4 | `/api/v1/admin/cost-summary` endpoint: per-user, per-day cost totals + breakdown by stage | [src/truebrief/api/routes.py](src/truebrief/api/routes.py) | Returns JSON of last 30 days | 5 |

**Why this matters:** the architecture target is **<$0.02 per brief at scale**. We currently have no way to know if we're hitting it.

### A.2 · Accuracy Test Harness (the science kit)

Six harnesses, each isolating one accuracy claim. Each runs against a frozen *fixture set* of articles checked into the repo, so results are reproducible.

| # | Harness | What it measures | Method |
|---|---|---|---|
| A.2.1 | **Harvester grounding** | % of extracted alphas that appear verbatim (or as paraphrases) in the source article | LLM-as-judge: for each (article, alpha) pair, ask Gemini "does the article support this fact? yes/no with span" — score precision |
| A.2.2 | **Arbiter precision/recall** | False-positive duplicates (rejecting real news) AND false-negative duplicates (re-reporting old news) | Hand-labeled fixture of 50 (new_alpha, existing_facts) pairs with ground-truth NEW/UPDATE/DUPLICATE decisions; replay through [arbiter](src/truebrief/arbiter/arbiter.py) |
| A.2.3 | **Story assignment** | % of alphas placed in the *correct* story node when multiple plausible candidates exist | 30 hand-labeled (alpha, candidate_stories) cases at the 0.70 threshold edge; check assignment matches human |
| A.2.4 | **Summary stability** | Whether story summaries stay coherent and don't lose specific facts after N recursive updates | Synthetic test: feed 20 sequential alphas about the same story into [story_summarizer](src/truebrief/ledger/story_summarizer.py); after each update, LLM-grade if (a) summary still contains the *first* fact's key detail, (b) summary < 500 chars, (c) summary doesn't introduce facts not in the input |
| A.2.5 | **Briefer faithfulness** | Whether the markdown brief introduces claims not present in the underlying alphas | LLM-as-judge: for each (brief, alphas) pair, list any claim in the brief unsupported by the alphas |
| A.2.6 | **Confidence floor consistency** | Whether facts dropped by harvester (<0.60) actually never reach arbiter/briefer | Plumb a `dropped_low_confidence` counter into [pipeline_task](src/truebrief/tasks/pipeline_task.py); assert briefs never cite an alpha with confidence < CONFIDENCE_MIN |

**Output:** a `tests/accuracy/` directory with `fixtures/`, one runner per harness, and a `report.md` printed to stdout (precision, recall, F1, plus example failures).

### A.3 · Longitudinal Stress Tests (your "doesn't collapse over time" concern)

This is the centerpiece. Three multi-day simulations.

| # | Test | Setup | What we measure |
|---|---|---|---|
| A.3.1 | **30-day fast-news simulation** | One topic ("OpenAI") scanned every 15 min (POWER tier) for 30 simulated days, using a frozen RSS replay of real news from a past 30-day window | Brief uniqueness over time (Jaccard distance between consecutive briefs); story-node count growth; summary length distribution; cost trajectory; AYR stability |
| A.3.2 | **Slow-burn topic** | One topic ("CRISPR clinical trial results") scanned hourly for 30 days where genuine new info only appears ~3 times | "Boy who cried wolf" check: do we send too many "nothing new" briefs? Does AYR feedback correctly back off? Does the user get a clear signal when something *real* happens? |
| A.3.3 | **Topic-overlap test** | 10 closely-related topics ("Tesla earnings", "Tesla layoffs", "Tesla autopilot", "Elon Musk", "EV market", "battery technology", "Gigafactory", "Cybertruck", "Tesla stock", "Tesla China") run in parallel for 7 days | Story-merge creep: do stories from different topics get incorrectly merged at the 0.70 threshold? How many cross-topic story collisions? |

**Why this matters:** these directly answer your concerns about "system getting confused with briefs over time," "missing information," and "becoming irrelevant."

**Each test produces:**
- A CSV of every brief with metadata (topic_id, brief_id, length, novel_alpha_count, total_alpha_count, cost_usd, latency_s)
- A timeline chart (using matplotlib) showing the metric over 30 days
- A "regression analyzer" that flags days where the metric trends bad (e.g., briefs getting shorter, alpha count falling, costs rising)

### A.4 · Failure-Mode Tests (kill the obvious bugs before users find them)

Direct stress on the failure modes flagged in the audit.

| # | Failure mode | Test |
|---|---|---|
| A.4.1 | False auto-merge across temporal boundary | Inject "Tesla Q3 2025 earnings: $1B" then "Tesla Q4 2025 earnings: $2B" 48h apart; assert both saved as separate facts |
| A.4.2 | Story merge creep | Inject "Tesla bankruptcy rumor" + "Tesla Gigafactory delay" — semantically similar but distinct stories; assert ≥2 story nodes created |
| A.4.3 | Orphaned story fact | Force `story_manager.assign_to_story()` to throw; assert pipeline still completes and fact is saved (just unassigned) |
| A.4.4 | Embedding batch mismatch | Patch `embed_batch` to return N-1 embeddings; assert MMR falls back to first-N and doesn't crash |
| A.4.5 | Double-schedule race | Kill the Celery worker mid-pipeline; assert scheduler doesn't re-enqueue twice, no double-charge |
| A.4.6 | Hallucination smoke | Run harvester on an article with known facts; LLM-grade output for facts not in the source |
| A.4.7 | Query rotator starvation | Force AYR < 0.10 on every variant for 5 consecutive scans; assert at least 1 variant always remains active |
| A.4.8 | Briefer with zero alphas | Run briefer with `decisions=[]`; assert it returns a sensible "no new info" message, not a hallucinated brief |

### A.5 · Competitor Benchmark (the one you specifically asked for)

**The premise:** TrueBrief's USP is "only show me what's new" — *not* "do a web search." Every competitor benchmark must measure **delta quality over time**, not single-shot retrieval.

**Competitors to benchmark:**

| Competitor | What it is | Why it's the benchmark |
|---|---|---|
| **Perplexity Spaces (Pro)** | Lets you ask the same question repeatedly with prior context | Closest functional analog |
| **ChatGPT Tasks** (formerly "scheduled GPTs") | OpenAI's native scheduled-prompt feature | What a casual user would try first |
| **Feedly AI Leo** | News aggregator + AI summary | Most users will compare to this |
| **Tavily standalone** | Same search API as us, but without our delta engine | Isolates the value of our pipeline over raw search |
| **Google News + manual reading** | The baseline TrueBrief is supposed to replace | Time-saved baseline |

**Methodology (single script: `tests/competitor_benchmark.py`):**

1. **Topic set:** 10 topics across different velocities (5 fast-moving like "AI regulation", 5 slow like "fusion energy"), agreed up front.
2. **Time window:** 14 days. Each system gets "asked" daily.
3. **Output capture:**
   - TrueBrief: pull from `briefs` table.
   - Perplexity / ChatGPT Tasks / Feedly: manually capture each day's output into a `competitor_outputs/{system}/{topic}/{date}.md` file (this is the only manual step — automate it later if needed).
4. **LLM-as-judge scoring** (Gemini Pro, *not* the same model that wrote our briefs, to avoid self-bias):
   - **Novelty precision** (0-100): of the facts in today's output, how many were *not* in yesterday's output from the same system?
   - **Information density** (facts / 100 words): how much signal per unit of reading?
   - **Recall** (0-100): given a "gold standard" set of real news events from the 14 days (curated by hand from Reuters' wire), what % did each system report?
   - **Hallucination rate** (0-100): how many facts in the output don't trace to any real news source?
5. **Cost normalization:** if a competitor is free at consumer tier, count the user's monthly subscription cost. If we use a paid API, count actual usage.
6. **Time-saved estimate:** average reading time of each system's daily output × 14 days.

**Deliverable:** `docs/competitive_scorecard.md` — a publishable scorecard (also useful for marketing if we win).

**Pass criteria:** TrueBrief beats every competitor on at least **3 of 4** metrics (novelty, density, recall) AND ties or beats on hallucination. Cost per brief must stay under $0.02.

**If we don't pass:** the scorecard tells us exactly which lever to pull (e.g. "lost on recall because Feedly's source list is wider → add more RSS feeds").

### A.6 · Public Scorecard & Internal Metrics Dashboard

| # | Deliverable | Purpose |
|---|---|---|
| A.6.1 | `/api/v1/admin/metrics` returning live AYR, cost-per-brief, alphas/day, story_count, average summary length | Internal observability |
| A.6.2 | Simple Streamlit or Next.js admin page at `/admin/metrics` (Clerk-protected to user email = founder) | Glance-able dashboard |
| A.6.3 | `docs/competitive_scorecard.md` | Public scorecard for marketing |

---

## Phase B · UI/UX Redesign

> **Updated 2026-05-21:** Phase B now requires a founder-approved design reference (B.REF) before any implementation begins. See Decision Log above.

**Goal:** make the UI worthy of the engine. Three principles:
1. **Surface the magic.** Story Nodes and AYR are our differentiators — show them.
2. **Finish what's started.** Topic Detail and Settings are stubs.
3. **Polish that signals quality.** Skeletons, animations, dark mode, command palette.

### B.REF · Design Reference (founder task — prerequisite for all B.2–B.5 work)

**This step is done by the founder, not Claude Code.**

1. Go to [aistudio.google.com](https://aistudio.google.com) or [claude.ai](https://claude.ai) (Projects)
2. Upload 2–3 screenshots of the current UI (dashboard, topic detail, brief page)
3. Prompt: *"Redesign this news intelligence SaaS UI. Style: Linear or Vercel dashboard — clean, minimal, dark mode first, information-dense but not cluttered. Output a full HTML + Tailwind CSS mockup of the dashboard and topic detail page."*
4. Open the output in a browser. Iterate the prompt until it looks right.
5. Save the final HTML file or screenshot to `docs/design-reference/` and bring it to Claude Code.

**Only then does B.2 begin.**

### B.0 · Design System Foundation

Before any new screen, lock the foundation so everything composes.

| # | Deliverable | Notes |
|---|---|---|
| B.0.1 | **Design tokens** in `tailwind.config.ts`: colors (light + dark), typography scale, spacing, radii, shadows, motion durations | Use OKLCH for colors; document each token with a comment |
| B.0.2 | **Dark mode** plumbed via `next-themes` + `class` strategy in Tailwind | Toggle in navbar (system / light / dark) |
| B.0.3 | **Motion primitives** via [Framer Motion](https://www.framer.com/motion/) (install): `<FadeIn>`, `<StaggerList>`, `<PageTransition>` | Used everywhere; respects `prefers-reduced-motion` |
| B.0.4 | **Component primitives** via [Radix UI](https://www.radix-ui.com/) (Dialog, DropdownMenu, Popover, Tabs, Toast, Tooltip) | Replace the hand-rolled ConfirmDialog + Toast with Radix-backed versions; keep our styling |
| B.0.5 | **Icon set** — already on Lucide; standardize sizes (16/20/24) | — |
| B.0.6 | **Empty / Loading / Error state primitives** — `<EmptyState>`, `<Skeleton>`, `<ErrorBoundary>` | Every page uses these instead of bespoke implementations |
| B.0.7 | **Typography refresh** — load Inter Variable + a serif (e.g. Source Serif Pro) for brief body; use serif inside [briefs] for readability | Currently all sans-serif |

### B.1 · Critical Gaps (stubs → finished features)

The user clicks "View Topic" and gets a "coming soon" page. This must die in week 1.

| # | Page | Current state | After |
|---|---|---|---|
| B.1.1 | **[Topic Detail (/topics/[id])](frontend/src/app/topics/[id]/page.tsx)** | Stub with placeholder text + scan button | Three-tab layout: **Briefs** (timeline of all briefs for this topic), **Stories** (graph view of story nodes — see B.2.1), **Insights** (AYR chart, source quality, query variants — see B.2.2). Sticky header with topic title, last-scan time, Scan-Now button, settings menu |
| B.1.2 | **[Settings (/settings)](frontend/src/app/settings/page.tsx)** | Only push notifications toggle | Account section (email from Clerk, sign-out, delete account), Subscription section (current plan, manage via Stripe portal, invoice history), Notifications section (push, email digest cadence), Preferences section (default scan frequency, default sources, dark mode), Danger zone (export data, delete everything) |
| B.1.3 | **Per-brief sources panel** in [briefs/[briefId]](frontend/src/app/topics/[id]/briefs/[briefId]/page.tsx) | None | Right-side rail showing the 3-10 articles cited, with source domain favicon + title + open-in-new icon. Click an article to see which alphas came from it. |

### B.2 · New Surfaces (expose backend features that have no UI)

These are the highest-leverage additions. Each unlocks something the engine already does.

| # | Surface | Backend hook | UI concept |
|---|---|---|---|
| B.2.1 | **Story Node graph** | `topics/{id}/stories` (need to add — query [story_manager](src/truebrief/ledger/story_manager.py)) | A vertical timeline: each story is a card with summary + fact count + last update; click expands to show all facts attached, with a mini-timeline of when each was added. "Active" stories (last update <72h) glow. Stories that haven't updated in 30 days collapse to a "dormant" section |
| B.2.2 | **AYR / cost insight** | `topics/{id}/ayr` already exists | Sparkline showing AYR over last 30 days, current scan interval (with "tuned by system" badge), cost-per-brief, total spend MTD. Power-user feature, ships behind a settings flag |
| B.2.3 | **Query variants** | `topics/{id}/query-variants` already exists | Settings panel inside Topic Detail: list of active variants with scans / alphas / AYR; toggle to disable; "+" button to add manual variant |
| B.2.4 | **Real-time scan progress** | [pipeline_task](src/truebrief/tasks/pipeline_task.py) → SSE stream of stage transitions | Replace the "Running…" spinner with a 6-stage progress (Query Build → Collect → Select → Harvest → Judge → Brief) showing live status. Even if it lies a little, the perceived speed is huge |
| B.2.5 | **Command palette** (Cmd/Ctrl + K) | — | `cmdk` library; search topics, jump to brief, "scan all", "go to settings", trigger digest |
| B.2.6 | **Notification inbox** | `briefs` table | Bell icon in navbar; dropdown lists unread briefs from last 7 days; counter badge; click marks read |
| B.2.7 | **Public profile page** (`/u/[username]`) | needs `users.public_handle` | Optional opt-in: a user's public topics + shared briefs. Strong organic growth lever (every share carries a "by @user" link) |

### B.3 · Polish Layer

| # | Item | Where |
|---|---|---|
| B.3.1 | Skeleton loaders | Dashboard topic grid, brief list, brief detail, history page |
| B.3.2 | Optimistic mutations | Topic create/delete, push subscribe, settings toggles (React Query `onMutate`) |
| B.3.3 | Page transitions | All routes (Framer Motion `<PageTransition>` in `layout.tsx`) |
| B.3.4 | Toasts upgraded to Radix Toast + queue system | Replace bespoke toast |
| B.3.5 | Confetti on first brief delivered + on tier upgrade | `canvas-confetti` |
| B.3.6 | Brief markdown: better typography | Pull in `@tailwindcss/typography`; tune for serif body; pretty blockquotes; syntax-highlight code |
| B.3.7 | Mobile action menu | Replace hover-only delete/settings on [TopicCard](frontend/src/components/topics/TopicCard.tsx) with a three-dot menu visible on all screen sizes |
| B.3.8 | Keyboard shortcuts (with `?` showing the legend) | Document inside command palette |
| B.3.9 | OG images per brief | Use Next.js `opengraph-image.tsx` to render a per-brief OG card (great for share virality) |

### B.4 · Copy & Brand Pass

| # | Item | Why |
|---|---|---|
| B.4.1 | Voice & tone document (one page) | So copy is consistent everywhere |
| B.4.2 | Rewrite every empty-state, loading message, error message | Currently utilitarian; should feel like a thoughtful product |
| B.4.3 | Onboarding refinement | Add a "first scan in progress" interstitial that explains what's happening |
| B.4.4 | Marketing-page review on landing | Replace boilerplate pricing copy with use-case-specific value props |

### B.5 · Accessibility & Mobile

| # | Item | Notes |
|---|---|---|
| B.5.1 | Audit with axe-core during build | Add `npm run a11y` |
| B.5.2 | Proper ARIA on every toggle (`role="switch"`, `aria-checked`) | [PushNotificationToggle](frontend/src/components/PushNotificationToggle.tsx) is missing this |
| B.5.3 | Focus traps in all Radix dialogs | Free if we use Radix |
| B.5.4 | Reduced-motion handling | Wrap Framer Motion with `useReducedMotion()` |
| B.5.5 | Brief detail re-flow on mobile | Currently `max-w-4xl` feels narrow; should be edge-to-edge with comfortable padding |
| B.5.6 | TopicCard touch target ≥44px | All action buttons |

---

## Phase C · Integration & End-to-End Testing

**Goal:** prove the new UI works against the real backend, that we have no regressions, and that we have a smoke test we can run before every deployment.

### C.1 · E2E Test Matrix (Playwright)

Add Playwright (`npm i -D @playwright/test`). One test file per critical user journey.

| # | Journey | Steps | Pass criteria |
|---|---|---|---|
| C.1.1 | New user onboarding → first brief | Sign up via Clerk dev mode → walk through onboarding → add topic → wait for first scan → see brief | Brief appears in <90s; no console errors |
| C.1.2 | Free → Pro upgrade | Sign in as free user with 2 topics → try to add 3rd → hit upgrade banner → click Upgrade → Stripe test checkout → return to dashboard | New tier reflected; topic creation now works |
| C.1.3 | Story node accumulation | Sign in → open a topic with ≥3 briefs → switch to Stories tab → expand a story → verify all facts present, sorted by date | Story timeline renders |
| C.1.4 | Share flow | From a brief, click Share → copy link → open in incognito → see brief | Public brief visible without auth |
| C.1.5 | Push notification | Enable push in settings → trigger a manual scan that produces a new brief → assert notification fires | (Use Playwright's notification permission grant) |
| C.1.6 | Rate-limit observance | Hammer POST /topics 25 times from same IP → assert 21st request returns 429 | Confirms Step 3.18 limits work end-to-end |
| C.1.7 | Mobile menu | Set viewport to iPhone 12 → open hamburger → navigate via mobile menu | All links work |
| C.1.8 | Dark mode | Toggle dark mode → reload → assert preference persists | next-themes integration works |

### C.2 · API Contract Tests

The frontend has hand-rolled types in [lib/api.ts](frontend/src/lib/api.ts). When the backend changes a field name, the frontend silently breaks.

| # | Deliverable | Notes |
|---|---|---|
| C.2.1 | Export OpenAPI schema from FastAPI (`/openapi.json` already exists) and consume it via `openapi-typescript` → generated `frontend/src/lib/api-types.ts` | Single source of truth |
| C.2.2 | Backend test: every Pydantic response model has an example payload that round-trips | Prevents schema drift |
| C.2.3 | Frontend test: every API call uses the generated types (no `any`) | TypeScript strict + lint rule |

### C.3 · Performance Budget

| # | Metric | Budget | Tool |
|---|---|---|---|
| C.3.1 | Largest Contentful Paint (landing) | < 2.0s on Slow 3G | Lighthouse CI |
| C.3.2 | First-byte API time (dashboard `/topics`) | p95 < 300ms | Custom backend probe |
| C.3.3 | JS bundle size (each route) | < 250KB gzipped | `@next/bundle-analyzer` |
| C.3.4 | Scan-now to first byte | < 500ms | Same custom probe |
| C.3.5 | Cold pipeline scan duration | p95 < 90s | Sampled from `pipeline_run` (A.1.1) |

### C.4 · Load & Stress

| # | Test | Tool | Pass criteria |
|---|---|---|---|
| C.4.1 | 100 concurrent users on /dashboard | k6 | No 5xx, p95 < 800ms |
| C.4.2 | 50 simultaneous scan triggers (different topics) | k6 + Celery | All complete, no Celery deadlock |
| C.4.3 | Redis outage drill | Stop Redis → assert API stays up (rate limiter falls back gracefully) and scans queue locally | Documented degradation path |
| C.4.4 | Supabase outage drill | Block DB → assert API returns 503 with clean error, no crash loop | — |

### C.5 · Pre-Production Smoke

A single script (`scripts/preflight.sh`) that must pass before any `git push` to the deploy branch:

```bash
pytest tests/                            # 106 backend tests
pytest tests/accuracy/ --quick           # cheap subset of A.2 harnesses
npm --prefix frontend run build          # type-check + build
npm --prefix frontend run test           # vitest
npx playwright test --grep @smoke        # 4-5 critical E2E
python tests/master_benchmark_v2.py --smoke  # 3 topics, not 21
python tests/cost_check.py               # last 100 scans avg < $0.02
```

If any step fails → block deployment.

---

## Sequencing & Time Budget (updated 2026-05-21)

| Week | Focus | Deliverables |
|---|---|---|
| **1** | **3.20 Deployment** — Railway backend + Vercel frontend live | App running 24/7, no more localhost dependency |
| **2** | A.2 (accuracy harnesses) + founder generates B.REF design mockup | Accuracy harnesses green; design reference approved |
| **3** | A.3 (longitudinal stress) starts running on Railway + B.2 implementation against B.REF | Sim running in background; Story Nodes + AYR UI ships |
| **4** | A.4 (failure-mode, already done ✅) + B.3 (polish against B.REF) | Skeletons + animations + command palette |
| **5** | A.5 (competitor benchmark) + B.4–B.5 (copy + a11y) | Scorecard published; UI feels premium |
| **6** | Phase C entirely | Playwright suite + perf budget + smoke script |

> **Key change:** Week 1 is now deployment, not telemetry. A.3 runs in the cloud background starting Week 3 — no need to keep a PC on.
> Compressible to 4 weeks by trimming B.2.6 (notification inbox) and C.4 (load tests).

---

## Open Questions for You

These are decisions only you can make. I won't start any of this work without answers.

1. **Competitor scope.** Of the 5 competitors in A.5, which do you actually want? Each manual capture costs ~20 min/day × 14 days × N competitors. Suggest top 3: **Perplexity, ChatGPT Tasks, Feedly AI**. Drop Tavily standalone and Google News?

2. **Topic set for benchmarks.** Should we agree on the exact 10 topics now, or pull from the existing [master_benchmark_v2.py](tests/master_benchmark_v2.py) categories? My recommendation: 5 from there + 5 we explicitly choose for velocity contrast.

3. **Accuracy harness LLM judge.** Use Gemini Pro? Claude Opus? GPT-4? Different model than the one writing briefs to avoid self-grading bias. Suggest **Claude Opus 4.7 or GPT-4.1** — neither is in our pipeline.

4. **Story-node UI ambition.** B.2.1 has two flavors:
   - **Simple:** vertical timeline list (~3 days work)
   - **Premium:** force-directed graph with zoom + filtering (~10 days work, way more impressive)
   Which?

5. **Public profile page (B.2.7).** Real growth lever or out-of-scope right now? It costs 4–5 days.

6. **Domain pipelines.** Architecture.md describes Phase 6 (Finance / Legal / Medical pipelines). Should the competitive benchmark include a "finance vertical" comparison to demonstrate that direction, or stay general?

7. **Streamlit vs Next.js for admin dashboard (A.6.2).** Streamlit ships in an afternoon and is throwaway. Next.js is consistent with the rest. Recommend Streamlit at this stage.

8. **Cost cap on benchmarks.** Some of these tests (A.3.1 = 30 days × 96 scans/day = 2,880 scans) will cost real money. At ~$0.01/scan that's ~$30, but if we have a bug it could be $300. Set a daily LLM spend cap in code (e.g. $5/day for tests) before starting?

9. **Deploy target.** Architecture.md mentions Railway. Still the plan? Affects C.3 measurements.

10. **Phase B model assignment.** Most B-items are FLASH-complexity UI work. But B.2.1 (story graph), B.2.4 (real-time SSE), and B.0 (design system foundations) are SONNET-grade. Want me to call out per-item once we commit to a step list?

---

## What I'd do next, after your green light

1. Answer the open questions above.
2. I write the first three step specs: `STEP_3.20.md` (Cost Telemetry, A.1), `STEP_3.21.md` (Design System Foundation, B.0), `STEP_3.22.md` (Topic Detail Page, B.1.1).
3. We restructure [docs/roadmap.md](docs/roadmap.md) so this becomes "Phase 3.5: Pre-Deployment" before what's currently 3.20 (Deployment) — keeping the roadmap as the single source of truth.
4. Execute step by step, with each step earning its own commit (`p3-s20`, `p3-s21`, …) following the existing pattern.

> **No code changes have been made.** This plan is a proposal only. Tell me which sections to keep, drop, or modify, and I'll write the per-step specs.
