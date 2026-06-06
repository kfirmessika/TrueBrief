# Skill: Frontend Editor
# Role: TrueBrief Frontend — Next.js 16 App Router, Clerk auth, React Query, inline CSS vars

---

## WHAT YOU CAN DO

- Add, edit, delete pages, components, hooks, styles in `frontend/`
- Add new API calls (always via `useApi()`)
- Add/modify React Query queries and mutations
- Add new routes under `frontend/src/app/`
- Modify sidebar, topic page, dashboard, new-topic page, settings
- Add/modify source chip behavior, brief parsing, scan progress bar
- Add frontend tests (Vitest + MSW in `frontend/src/test/`)
- Modify auth middleware (`src/proxy.ts`) — protected route list only
- Modify CSS variables in `globals.css`

## WHAT YOU CANNOT DO — ask the backend editor instead

- Touch `src/truebrief/` (Python backend)
- Add/change API endpoints or DB schema
- Modify `railway.toml`, `.env`, or deployment config
- Change Clerk project settings (only proxy.ts route matching is yours)

---

## DEV COMMANDS (run from `frontend/`)

```bash
npm run dev                          # hot-reload dev server at http://localhost:3000
npx tsc --noEmit --skipLibCheck      # type-check — run before finishing ANY change
npm test                             # Vitest + MSW tests
npm run build                        # production build — MUST run and report PASS/FAIL when done
```

**Rule: never report a task done without running `npx tsc --noEmit --skipLibCheck` AND `npm run build`.**

---

## FILE MAP

```
frontend/src/
  app/
    layout.tsx                   root layout — ClerkProvider wraps everything
    providers.tsx                QueryClient (staleTime 60s, retry 1) + ThemeProvider
    (marketing)/                 public landing page — no auth
    (app)/
      layout.tsx                 app shell: <Sidebar> + <main flex-1>
      dashboard/page.tsx         topic feed cards (DashboardItem[])
      topics/
        new/page.tsx             topic creation form
        [id]/page.tsx            brief thread — most complex file
      settings/page.tsx          billing, user prefs, danger zone

  components/
    layout/
      Sidebar.tsx                nav, topic list with 3-dot scan/delete menu
      Navbar.tsx                 top bar with logo, theme toggle, user button
      Footer.tsx                 copyright + policy links
    topics/
      AddTopicForm.tsx           input + submit for new topics
      TopicCard.tsx              dashboard card: title, scan status, 3-dot menu
      ScanButton.tsx             standalone scan trigger with state machine
      ScanStatusBadge.tsx        PENDING/STARTED/SUCCESS/FAILURE badge
      TopicTabs.tsx              briefs/stories/insights tab bar
      UpgradeBanner.tsx          "Limit reached — upgrade" call to action
    briefs/
      BriefCard.tsx              preview card linking to full brief
      BriefContent.tsx           full brief rendered via react-markdown + remark-gfm
      CopyLinkButton.tsx         clipboard copy with 2s "Copied!" feedback
    ui/
      Skeleton.tsx               SkeletonCard, SkeletonBriefRow, SkeletonText({lines})
      Toast.tsx                  bottom-right toast + useToast() hook
      ConfirmDialog.tsx          modal with title/description/confirm/cancel
      EmptyState.tsx             icon + title + description + optional action
      ErrorBoundary.tsx          class component; catches render errors
      motion.tsx                 FadeIn, StaggerList/StaggerItem, PageTransition, ScalePop

  hooks/
    useTopics.ts                 useTopics, useCreateTopic, useDeleteTopic,
                                 useTriggerScan, useScanStatus
    useTier.ts                   useTier() — billing tier + limits
    useStats.ts                  useStats() — total_briefs, articles_scanned, time_saved_minutes
    usePushNotifications.ts      usePushNotifications() — subscribe/unsubscribe web push

  lib/
    useApi.ts                    useApi() — authenticated axios instance (USE THIS for all client calls)
    api.ts                       typed helpers (topicsApi, briefsApi, billingApi, statsApi)
                                 + apiFetch() SERVER-SIDE ONLY
                                 + types: Topic, Brief, TierLimits, BillingStatus, UserStats
    utils.ts                     cn(...classes) — class name merger

  proxy.ts                       Clerk middleware — protects /dashboard /topics /onboarding /settings
  app/globals.css                ALL CSS variables (design tokens, animations)
```

---

## RULES THAT MUST NEVER BE BROKEN

1. **All client API calls go through `useApi()`** — it injects the Clerk JWT. Never use bare `api` from `lib/api.ts` in a `'use client'` file.
2. **`apiFetch` is server-side only** — it calls `auth()` from `@clerk/nextjs/server`. Never import it in a `'use client'` file.
3. **No circular imports** — if two files need shared types, create a third `types.ts`.
4. **Styling rule — do not mix Tailwind and inline styles in the same file:**
   - App shell (`app/(app)/layout.tsx`), topic page (`topics/[id]/page.tsx`), sidebar → inline `style={{}}` with CSS vars
   - Components in `components/` → Tailwind
5. **Never hardcode colors** — always use CSS variables (e.g. `var(--tb-green)`, `var(--color-text-primary)`).
6. **Run `npx tsc --noEmit --skipLibCheck` and `npm run build` before reporting done.** Fix all errors.

---

## AUTH PATTERN

```
Clerk is the auth provider.

Client side:
  useApi()
    └── axios interceptor → getToken() → Authorization: Bearer <jwt>
    └── base URL: NEXT_PUBLIC_API_BASE_URL (default: http://localhost:8000) + /api/v1

Server side:
  import { auth } from '@clerk/nextjs/server'
  const { getToken } = await auth()
  apiFetch(path)   ← handles token internally

Route protection (proxy.ts):
  clerkMiddleware + createRouteMatcher
  Protected: /dashboard(.*), /topics(.*), /onboarding(.*), /settings(.*)
```

---

## REACT QUERY CONVENTIONS

Global defaults: `staleTime: 60_000`, `retry: 1` (set in `providers.tsx`).

| Query key | Endpoint | staleTime override | Notes |
|---|---|---|---|
| `['topics']` | GET /topics | 30s in Sidebar | Sidebar subscribes directly |
| `['topic', id]` | GET /topics/{id} | 0 (always fresh) | Topic page; refetchInterval 60s |
| `['topic-briefs', id]` | GET /topics/{id}/briefs | — | Reversed order; 5s poll when scanning, 60s otherwise |
| `['topic-known-facts', id]` | GET /topics/{id}/known-facts | — | AlphaItem[] for source chip tooltips |
| `['scan-status', taskId]` | GET /scan-status/{taskId} | — | Polls 2s; stops on SUCCESS/FAILURE |
| `['dashboard']` | GET /dashboard | 30s | DashboardItem[] |
| `['shared-topics', query]` | GET /shared-topics?q={q} | 10s | Suggestion pills on new-topic page |

**On scan SUCCESS/FAILURE:** invalidate `['topics']`, `['topic', id]`, `['topic-briefs', id]`.

---

## SCAN TASK FLOW (end to end)

```
1. Trigger (sidebar 3-dots → Scan, OR new topic creation)
   └── POST /topics/{id}/scan
   └── Backend returns { task_id, topic_id, status }
   └── Store in localStorage: scan_task_${topicId} = task_id

2. Topic page polls localStorage every 500ms
   └── Picks up task_id → sets scanTaskId state → renders ScanProgressBar

3. ScanProgressBar
   └── Calls useScanStatus(taskId, topicId)
   └── Shows 8 friendly step labels, cycling every 4s:
       "Searching the web…" → "Collecting articles…" → "Reading sources…"
       → "Filtering relevant content…" → "Analyzing what matters…"
       → "Connecting the dots…" → "Writing your brief…" → "Almost done…"
   └── Progress bar grows fast then slows near 90% (never lies — caps at 90% until backend confirms)

4. useScanStatus polls GET /scan-status/{taskId} every 2s
   └── On SUCCESS or FAILURE:
       └── Invalidates ['topics'], ['topic', id], ['topic-briefs', id]
       └── Returns false from refetchInterval (stops polling)

5. ScanProgressBar on SUCCESS
   └── Bar jumps to 100%, shows "Done!"
   └── After 600ms: removes localStorage entry, calls onDone()
   └── onDone() calls handleScanDone() in page → clears scanTaskId state

6. 429 rate-limit error from scan endpoint
   └── Sidebar reads `Retry-After` header
   └── Shows inline error: "Next scan available in X hours" for 5s
```

---

## TOPIC PAGE INTERNALS (`topics/[id]/page.tsx`)

The most complex file. Read this carefully before touching it.

### Types defined in file

```ts
Brief      { id, topic_id, content, delivered_at }
Topic      { id, raw_query, frequency, last_scan_at }
SourceChip { domain, label, url? }
AlphaItem  { source_domain, source_url?, alpha_text, first_seen_at }
BriefSection { heading?, body: string[], sources: SourceChip[], isBadge?, badgeType?, badgeCount? }
```

### Helper functions

```ts
timeAgo(iso)            → "Xm ago" / "Xh ago" / "Xd ago"
formatDate(iso)         → "Jan 15"
formatTime(iso)         → "2:30 PM"
parseContent(raw)       → strips "📋 TrueBrief | …" header line
parseSourceLine(line)   → parses "→ Sources: [Name](url), …" → SourceChip[]
parseBriefSections(md)  → splits markdown → BriefSection[]
inlineFormat(text)      → renders **bold**, *italic*, `code`, [links] inline
renderBodyLine(line, k) → renders bullet/paragraph with inline source chips
```

### Components defined in file

```
DomainAlphasCtx         React context: Map<domain, AlphaItem[]>
SourcePill({chip})      domain chip + favicon + tooltip with raw alpha articles
                        200ms hide delay, pointerEvents:'auto', scrollable 340px max
BriefSection({section}) renders badge section OR heading+body+inline sources
BriefBubble({brief})    full brief card; filters error/short (<30 char) briefs;
                        source favicon row + timestamp footer
DateSeparator({label})  horizontal rule with date label
Skeleton()              2 fake brief shimmer cards
ScanProgressBar({topicId, taskId, onDone})
                        8-step label cycle + animated bar; calls useScanStatus
```

### Page state

```ts
scanTaskId: string|null  — from localStorage scan_task_{id}; drives progress bar
                           polled every 500ms via setInterval (cross-tab sync)
domainAlphas: Map<…>     — memoized from known-facts query
```

### Brief markdown format (LLM output)

```
📋 TrueBrief | Topic | Date
🆕 NEW STORIES (N)
━━━━━━━━━━━━
**Section Title**
• Bullet text. → Sources: [domain.com](https://full-article-url)
• Another bullet. → Sources: [a.com](url1), [b.com](url2)
📈 UPDATES (N)
━━━━━━━━━━━━
**Section Title**
• WHAT'S NEW: … → Sources: [domain.com](url)
• FULL CONTEXT: … → Sources: [domain.com](url)
```

Old format (before per-bullet sources): single `→ Sources:` line at end of section. Both are supported.

---

## SIDEBAR INTERNALS (`components/layout/Sidebar.tsx`)

```
State:
  hoveredTopic: string|null    controls 3-dot button visibility
  openMenu: string|null        which topic menu is open
  scanError: string|null       429 message, auto-clears after 5s

3-dot menu per topic (appears on hover, invisible otherwise):
  Scan   → POST /topics/{id}/scan → stores task_id in localStorage
  Delete → confirm() dialog → DELETE /topics/{id} → invalidates ['topics']

Footer:
  User initials avatar (--tb-green bg)
  Display name + email
  Tier badge ("Free" | "Pro" | "Power")
```

---

## DESIGN SYSTEM (CSS VARIABLES)

All variables defined in `app/globals.css`. Always use variables — never hardcode colors.

### App shell tokens (always light)

```css
/* Backgrounds */
--color-background-primary      #ffffff
--color-background-secondary    #F9F8F5
--color-background-tertiary     #F1EFE8

/* Borders */
--color-border-secondary        #D0CEC6
--color-border-tertiary         #E5E3DC

/* Text */
--color-text-primary            #1A1917
--color-text-secondary          #6B6963
--color-text-tertiary           #9B9B9B

/* Brand */
--tb-green                      #0F6E56    main brand green
--tb-green-light                           hover/active tint
--tb-green-dark                            pressed state
--tb-green-border                          border for green active states

/* Accents */
--tb-amber                      #EF9F27    scanning pulse, warning
--tb-coral-dot                             delete/danger red
--tb-coral-bg                              danger background
--tb-coral-text                            danger text
```

### Semantic tokens (theme-aware, light+dark)

```css
--color-brand                   indigo
--color-brand-subtle            light indigo tint
--color-success                 green
--color-success-subtle          light green tint
--color-warning                 orange
--color-danger                  red
--color-danger-subtle           light red tint
--color-info                    blue
--color-info-subtle             light blue tint
--color-surface-overlay         near-white overlay (96%)
--color-text-muted              lightest text
```

### Animations

```css
@keyframes tb-pulse   opacity 0% → 30% → 100%   used for scanning dot in sidebar
```

---

## MOTION COMPONENTS (`components/ui/motion.tsx`)

```tsx
<FadeIn delay={0} duration={0.3} y={8}>          // fade + lift entrance
<StaggerList>                                     // wraps staggered children
  <StaggerItem>…</StaggerItem>
</StaggerList>
<PageTransition>…</PageTransition>               // page route change animation
<ScalePop>…</ScalePop>                           // hover scale up, tap scale down
```

All respect `prefers-reduced-motion`. Easing: `[0.4, 0, 0.2, 1]`.

---

## ADDING THINGS

### New page

```
1. Create frontend/src/app/(app)/your-route/page.tsx
   → 'use client'; at top if it uses hooks/state
2. Add to protected routes in src/proxy.ts if auth-required
3. Add nav link in Sidebar.tsx if it needs navigation
4. Fetch data: useApi() + useQuery inside the component
```

### New hook

```
1. Create in frontend/src/hooks/
2. Call useApi() INSIDE the hook (not outside — it's a hook itself)
3. Export named functions, no default export
4. Follow the React Query key table above
```

### New client API call

```
1. Use useApi() to get the axios instance
2. Backend base: NEXT_PUBLIC_API_BASE_URL/api/v1 (useApi() handles this)
3. Check lib/api.ts for existing typed helpers first
4. Wrap in useMutation or useQuery from @tanstack/react-query
```

### New component

```
Styling choice:
  - If it's in components/ → use Tailwind
  - If it's in app/(app)/layout.tsx or topics/[id]/page.tsx → use inline style={{}} + CSS vars
  - Never mix in the same file

Export: named export (not default) for components in components/
```

### New query key

```
Add to the React Query table above.
Convention: ['noun', id?] — always lowercase, always array.
```

---

## HOOKS REFERENCE

### `useTopics()`
Fetches `GET /topics` → `Topic[]`. No params.

### `useCreateTopic()`
Returns mutation for `POST /topics`.
```ts
const { mutateAsync } = useCreateTopic()
const topic = await mutateAsync(raw_query: string)
// topic.scan_task_id may be present → store in localStorage
```

### `useDeleteTopic()`
Returns mutation for `DELETE /topics/{id}`. Invalidates `['topics']`.

### `useTriggerScan()`
Returns mutation for `POST /topics/{id}/scan`.
```ts
const { mutateAsync } = useTriggerScan()
const { task_id } = await mutateAsync(topicId)
localStorage.setItem(`scan_task_${topicId}`, task_id)
```

### `useScanStatus(taskId, topicId?)`
Polls `GET /scan-status/{taskId}` every 2s. Stops on SUCCESS/FAILURE.
Returns `{ data: { state: 'PENDING'|'STARTED'|'SUCCESS'|'FAILURE' } }`.
On completion invalidates `['topics']`, `['topic', topicId]`, `['topic-briefs', topicId]`.

### `useTier()`
Fetches `GET /billing/status` → `BillingStatus { tier, status, limits: TierLimits }`.
```ts
const { data: tier } = useTier()
tier.tier          // 'free' | 'pro' | 'power'
tier.limits.max_topics
tier.limits.scan_interval_hours
```

### `useStats()`
Fetches `GET /users/me/stats` → `{ total_briefs, articles_scanned, time_saved_minutes }`.

### `usePushNotifications()`
```ts
const { isSupported, isSubscribed, isLoading, subscribe, unsubscribe } = usePushNotifications()
```
Manages service worker + PushManager. Calls `POST /push/subscribe` and `DELETE /push/subscribe`.

---

## COMPONENTS REFERENCE

### `<Toast message type onClose duration?>`
Types: `'error' | 'success' | 'info'`. Auto-dismisses after `duration` ms (default 5000).
Use `useToast()` hook for imperative control:
```ts
const { showToast, hideToast } = useToast()
showToast('Saved!', 'success')
```

### `<ConfirmDialog isOpen title description confirmLabel? cancelLabel? onConfirm onCancel>`
Modal overlay. Only renders when `isOpen === true`.

### `<EmptyState icon? title description? action? className?>`
Centered layout with optional Lucide icon, title, description, and action node.

### `<ErrorBoundary fallback?>`
Class component. Catches render errors; shows fallback or default AlertTriangle message.

### `<Skeleton>` / `<SkeletonCard>` / `<SkeletonBriefRow>` / `<SkeletonText lines={n}>`
Animated pulse loading placeholders.

### `<UpgradeBanner currentCount maxTopics>`
Shows when user is at topic limit. Links to `/settings`.

### `<ScanStatusBadge taskId onFinished?>`
Shows state pill. Returns null when taskId is null.

### `<ScanButton topicId className? onComplete?>`
Self-contained scan trigger + state machine (idle→queuing→running→done/error). Internal poller, max 4 min.

### `<BriefContent content>`
Renders markdown string. Uses react-markdown + remark-gfm. All elements Tailwind-styled.

### `<CopyLinkButton shareUrl?>`
Copies `shareUrl` or current URL. Shows "Copied!" for 2s.

---

## TYPES REFERENCE (`lib/api.ts`)

```ts
Topic {
  id: string
  raw_query: string
  frequency?: string
  is_active?: boolean
  last_scan_at?: string | null   // ISO string; maps to DB column last_run_at
  scan_task_id?: string | null   // present only in create response (first scan)
}

Brief {
  id: string
  topic_id: string
  content: string               // raw markdown
  delivered_at: string          // ISO string
}

BillingStatus {
  tier: 'free' | 'pro' | 'power'
  status: string
  paddle_customer_id?: string
  current_period_end?: string
  limits: TierLimits
}

TierLimits {
  max_topics: number
  scan_interval_hours: number
}

UserStats {
  total_briefs: number
  articles_scanned: number
  time_saved_minutes: number
}
```

---

## KNOWN GOTCHAS

1. **`last_scan_at` vs `last_run_at`** — The DB column is `last_run_at`. The API serializes it to `last_scan_at` in the `TopicResponse` model. Frontend uses `last_scan_at`. Do not query the DB for `last_scan_at` directly — it doesn't exist.

2. **Next.js 16 / App Router** — This is NOT standard Next.js 13/14. Breaking changes exist. Before using any API (router, params, cookies, headers), read `node_modules/next/dist/docs/` for the current behavior.

3. **`params` in page components are async** — `{ params }: { params: Promise<{ id: string }> }` → use `const { id } = use(params)`.

4. **`useApi()` returns a new axios instance on every call** — always call it at the top of the component, not inside event handlers or effects.

5. **`memory://` broker** — If `REDIS_URL` is not set in `.env`, Celery uses an in-memory broker that only works within a single process. Always set `REDIS_URL=redis://localhost:6379/0` for local dev (Redis installed at `C:\Program Files\Redis\`).

6. **`scan_task_id` in create response** — Only present when a new topic is created (not when subscribing to an existing shared topic). Always check for its existence before storing.

7. **Brief content filtering** — `visibleBriefs` filters out any brief where `parseContent(b.content)` contains "error generating" or has length < 30. Don't add briefs shorter than 30 chars or containing that string.

8. **Sidebar styling** — Sidebar is always light mode (uses hard-coded `--color-background-secondary` token which is fixed light). Do not add `dark:` Tailwind classes to Sidebar.

---

## SECTION FOR OTHER EDITORS

The sections below are reserved for backend, infra, and other editors to add their skills.

<!-- BACKEND EDITOR: section below -->

---

# Skill: Backend Editor
# Role: TrueBrief Python Backend — FastAPI, Celery, pipeline, LLM, billing, auth

---

## WHAT YOU CAN DO

- Add/edit/delete Python files in `src/truebrief/`
- Add or modify API endpoints in `src/truebrief/api/routes.py` and other route files
- Add/modify pipeline stages: collector, harvester, arbiter, briefer, ledger, story manager
- Modify Celery tasks in `src/truebrief/tasks/`
- Modify LLM calls — always through `src/truebrief/llm/client.py`
- Add/modify billing logic in `src/truebrief/billing/`
- Add/modify auth logic in `src/truebrief/auth/`
- Modify push notifications in `src/truebrief/push/`
- Modify digest (email) logic in `src/truebrief/digest/`
- Write and run Python tests with `pytest tests/`
- Write audit/inspection scripts in `scripts/`
- Modify `config/settings.py` (env var config)
- Modify `railway.toml` for deployment config

## WHAT YOU CANNOT DO — ask the relevant editor instead

- Touch `frontend/` (frontend editor)
- Run SQL migrations or alter DB schema directly (database editor)
- Change Clerk project settings (only read JWT in `auth/dependencies.py`)
- Change Paddle/Stripe dashboard settings (only code-side webhook handling)

---

## DEV COMMANDS (run from project root `d:\projects\Apps\TrueBrief\`)

```powershell
# Start everything locally (Redis + Celery worker + beat + FastAPI)
.\scripts\start-local.ps1

# Stop everything
.\scripts\stop-local.ps1

# Run tests
pytest tests/

# Run a single pipeline manually for a topic
python scripts/run_pipeline.py "your topic here"

# Audit all stored data for a topic keyword → writes to reports/
python scripts/audit_topic.py "keyword"

# Type-check (no type stubs enforced, but run if touching models)
# No mypy config — rely on pytest for correctness
```

**Rule: never report a task done without running `pytest tests/` and reporting PASS/FAIL.**

---

## PROJECT LAYOUT

```
src/truebrief/
  api/
    server.py              FastAPI app factory, CORS, router registration
    routes.py              topics CRUD + pipeline trigger + scan status
    rate_limit.py          slowapi rate limiter (per-user, per-IP)
    push_routes.py         web push subscribe/unsubscribe
    digest_routes.py       email digest endpoints
    billing_routes.py      Paddle webhook + billing status

  pipeline/
    runner.py              PipelineRunner — orchestrates all 6 stages end-to-end

  collector/
    base.py                SourceLayer ABC — all sources implement search(query)
    query_builder.py       QueryBuilder — LLM builds SearchQuery from raw topic
    extractor.py           ArticleExtractor — fetches + extracts full article text
    rss_layer.py           RSS feed source
    google_news_layer.py   Google News scraper source
    tavily_layer.py        Tavily search API source
    brave_layer.py         Brave search API source
    exa_layer.py           Exa neural search source

  harvester/
    harvester.py           Harvester — LLM extracts Alpha facts from article text

  arbiter/
    arbiter.py             Arbiter — judges NEW / UPDATE / DUPLICATE per Alpha
    judge.py               JudgeLLM — grey-zone LLM call with structured output
    temporal.py            adjusted_similarity() — penalizes old facts

  briefer/
    briefer.py             Briefer — LLM formats delta facts → markdown brief

  ledger/
    vector_store.py        VectorStore — embed + store + find_similar (pgvector)
    story_manager.py       StoryManager — clusters facts into StoryNodes
    story_summarizer.py    StorySummarizer — refreshes story summaries on UPDATE
    ayr_engine.py          AYR (Adaptive Yield Rate) — sets poll_interval after run
    query_rotator.py       QueryRotator — tracks best-performing search variants
    source_logger.py       SourceQualityLogger — logs NEW/DUPLICATE per domain
    database.py            get_supabase() — singleton Supabase client
    telemetry.py           Pipeline telemetry logging

  llm/
    client.py              LLMClient — single entry point for all LLM calls + embeddings
    pricing.py             Token cost tracking per model

  models/
    alpha.py               Alpha, AlphaDecision, DecisionType dataclasses
    article.py             RawArticle dataclass
    brief.py               Brief model
    story.py               StoryNode, StoryStatus dataclasses
    topic.py               Topic model
    tier.py                Tier enum + limits

  auth/
    dependencies.py        get_current_user() FastAPI dependency — verifies Clerk JWT
    clerk.py               Clerk JWT verification logic
    models.py              User dataclass
    user_repo.py           User DB read/write

  billing/
    tiers.py               enforce_topic_limit(), enforce_speed_limit() dependencies
    stripe_service.py      Stripe integration (legacy — Paddle is current)
    paddle_service.py      Paddle webhook processing
    billing_routes.py      /billing/status, /billing/webhook

  tasks/
    celery_app.py          Celery app + beat schedule definition
    pipeline_task.py       run_pipeline_for_topic() Celery task
    digest_task.py         send_daily_digest() Celery task
    push_task.py           send_push_notification() Celery task
    scheduler.py           scan scheduling helpers

  push/
    client.py              Web push (pywebpush) send logic

  digest/
    mailer.py              Email send via SMTP
    renderer.py            Digest HTML/text rendering

config/
  settings.py              All env vars via pydantic Settings — single source of truth

scripts/
  run_pipeline.py          Manual pipeline run for a topic
  audit_topic.py           Dump all stored data for a keyword → reports/
  start-local.ps1          Start Redis + Celery worker + beat + FastAPI (Windows)
  stop-local.ps1           Stop all local processes
  migrations/              SQL migration files (applied by DB editor)
```

---

## PIPELINE STAGES (in order)

```
1. QueryBuilder.build(raw_topic)
   → LLM generates SearchQuery: topic_name, primary_query, alt_queries[], scope

2. QueryRotator.select_variant(topic_id, raw_query, alt_queries)
   → picks best-performing query variant from DB history

3. _collect_all(query)
   → runs all SourceLayer plugins in parallel, deduplicates by URL
   → RSS/GoogleNews: keyword pre-filter; Tavily/Brave/Exa: trusted, no filter

4. _mmr_select(query, articles, limit=5)
   → Maximal Marginal Relevance: λ=0.65 relevance + diversity balance
   → embeds query + all article titles, iterative greedy MMR selection

5. ArticleExtractor.extract(article) + Harvester.extract(article, topic_id)
   → fetches full article text; LLM extracts Alpha[] (atomic facts)
   → each Alpha: alpha_text, entities, event_date, context, confidence, source

6. Arbiter.judge(alpha, topic_id)
   → embeds alpha, fetches top-3 similar from VectorStore (threshold 0.50)
   → temporal adjustment via adjusted_similarity()
   → score ≥ 0.97 → AUTO-DUPLICATE (no LLM)
   → score < 0.75 → AUTO-NEW (no LLM)
   → 0.75–0.97 → JudgeLLM (structured output: MERGE/UPDATE/NEW + delta)

7. StoryManager.assign_to_story(decision, topic_id)
   → UPDATE → joins matched fact's StoryNode
   → NEW → match_stories RPC (similarity ≥ 0.70) or create new StoryNode

8. VectorStore.add_fact(alpha, story_node_id)
   → embeds alpha_text, inserts into known_facts with story_node_id

9. StorySummarizer.refresh_summary(story_node_id, new_alpha)
   → only on UPDATE to existing story; LLM re-summarizes, re-embeds story

10. AYR engine: ayr_engine.record_run(topic_id, alphas, dupes)
    → sets next poll_interval_seconds based on yield rate

11. Briefer.generate(decisions, topic_name)
    → only NEW + UPDATE decisions; LLM formats → markdown brief
    → saved to briefs table via pipeline_task.py after runner returns
```

---

## LLM CLIENT — HOW TO USE

**All LLM calls go through `LLMClient` in `src/truebrief/llm/client.py`. Never call any LLM SDK directly.**

```python
from truebrief.llm.client import LLMClient
llm = LLMClient()

# Text generation
response = llm.call(
    step_name="my_step",      # used for cost tracking
    prompt="...",
    system_prompt="...",      # optional
    json_mode=False,          # True → forces JSON output
)

# Embedding (single)
embedding: list[float] = llm.embed("text to embed")

# Embedding (batch)
embeddings: list[list[float]] = llm.embed_batch(["text1", "text2"])
```

**Model selection — defined in `config/settings.py`, never hardcode:**
```python
settings.LLM_MODEL_FLASH    # fast/cheap: harvester, query builder
settings.LLM_MODEL_SONNET   # capable: arbiter judge, briefer, summarizer
settings.LLM_MODEL_OPUS     # powerful: reserved for complex reasoning
settings.EMBEDDING_MODEL    # text-embedding-004 (768 dims)
```

**Never hardcode model names.** Always read from `settings.*`.

---

## API ENDPOINTS REFERENCE

All routes under `/api/v1`. Auth via `get_current_user` dependency (Clerk JWT).

```
Topics:
  GET    /topics                      list user's subscribed topics
  POST   /topics                      create or subscribe to topic
  GET    /topics/{id}                 single topic details
  DELETE /topics/{id}                 unsubscribe (deletes sub row, not topic)
  GET    /topics/{id}/briefs          list briefs for topic (latest first)
  GET    /topics/{id}/known-facts     list Alpha facts for topic
  POST   /topics/{id}/scan            trigger pipeline (returns task_id)
  GET    /scan-status/{task_id}       poll Celery task state

Billing:
  GET    /billing/status              user's tier + limits + subscription status
  POST   /billing/webhook             Paddle webhook handler

Push:
  POST   /push/subscribe              register push subscription
  DELETE /push/subscribe              remove push subscription

Digest:
  GET    /digest/preview              preview today's digest for user
  POST   /digest/send                 manually trigger digest send

Admin (founder-only):
  GET    /admin/topics                all topics + subscriber counts
  POST   /admin/topics/{id}/run       force pipeline run for any topic

Users:
  GET    /users/me/stats              total_briefs, articles_scanned, time_saved_minutes
  GET    /users/me                    current user profile
```

### Adding a new endpoint

```python
# In routes.py (or a new *_routes.py file registered in server.py):
@router.get("/your-path")
async def your_endpoint(
    user: User = Depends(get_current_user),
    db = Depends(get_supabase),
):
    ...
    return {"key": "value"}

# Register new router in server.py:
from truebrief.api.your_routes import router as your_router
app.include_router(your_router, prefix="/api/v1")
```

---

## AUTH PATTERN

```python
# Protect any endpoint:
from truebrief.auth.dependencies import get_current_user, User

@router.get("/protected")
async def endpoint(user: User = Depends(get_current_user)):
    user.id      # Clerk user_id (UUID string)
    user.email   # user's email

# Founder-only guard:
from truebrief.api.routes import _require_founder
_require_founder(user)   # raises 403 if not founder email
```

JWT is verified against Clerk JWKS. `CLERK_SECRET_KEY` must be in `.env`.

---

## CELERY TASKS

```python
# Defined in tasks/celery_app.py
# Beat schedule: every topic's next_run_at is checked every 60s

# Pipeline task (tasks/pipeline_task.py):
run_pipeline_for_topic.delay(topic_id)
# → runs PipelineRunner.run(), saves brief to DB, updates last_run_at/next_run_at

# Digest task (tasks/digest_task.py):
send_daily_digest.delay(user_id)

# Push task (tasks/push_task.py):
send_push_notification.delay(user_id, title, body)
```

**Local Celery requires Redis.** Set `REDIS_URL=redis://localhost:6379/0` in `.env`.
Windows Redis is at `C:\Program Files\Redis\redis-server.exe`.

---

## SETTINGS / ENV VARS (`config/settings.py`)

```python
from config.settings import settings

settings.SUPABASE_URL
settings.SUPABASE_KEY              # anon key (for normal queries)
settings.SUPABASE_SERVICE_ROLE_KEY # service role (for admin ops)
settings.CLERK_SECRET_KEY
settings.REDIS_URL
settings.TAVILY_API_KEY
settings.BRAVE_API_KEY
settings.EXA_API_KEY
settings.GOOGLE_GEMINI_API_KEY
settings.LLM_MODEL_FLASH           # default: gemini-1.5-flash-lite or equivalent
settings.LLM_MODEL_SONNET          # default: gemini-1.5-pro or equivalent
settings.EMBEDDING_MODEL           # default: text-embedding-004
settings.FOUNDER_EMAIL             # email for admin-only endpoints
settings.PADDLE_WEBHOOK_SECRET
settings.VAPID_PRIVATE_KEY         # web push
settings.VAPID_PUBLIC_KEY
settings.SMTP_*                    # email digest
```

All env vars loaded from `.env` at project root via `python-dotenv`.

---

## BILLING / TIERS

```python
from truebrief.billing.tiers import enforce_topic_limit, enforce_speed_limit

# Enforce max topics per tier before creating a new one:
@router.post("/topics")
async def create_topic(...):
    await enforce_topic_limit(user, db)   # raises 403 if at limit

# Enforce scan rate limit:
@router.post("/topics/{id}/scan")
async def scan_topic(...):
    await enforce_speed_limit(user, db, topic_id)  # raises 429 with Retry-After header
```

**Tier limits (from `tier_intervals` table + `billing/tiers.py`):**
```
free:  max_topics=3,  scan_interval_hours=24
pro:   max_topics=10, scan_interval_hours=1
power: max_topics=∞,  scan_interval_hours=0.25 (15min)
```

---

## MODELS REFERENCE

### `Alpha` (`models/alpha.py`)
```python
@dataclass
class Alpha:
    alpha_text: str           # the fact itself — self-contained sentence
    entities: list[str]       # named entities (companies, people, places)
    source_url: str
    source_name: str
    event_date: Optional[datetime]   # WHEN did the event happen (not publish date)
    context: Optional[str]           # one sentence: why this fact matters
    confidence: float                # 0.0–1.0; facts < 0.6 dropped by Harvester
    id: str                          # uuid4
    topic_id: Optional[str]
    embedding: Optional[list[float]] # populated after Arbiter embeds it
```

### `AlphaDecision` (`models/alpha.py`)
```python
@dataclass
class AlphaDecision:
    alpha: Alpha
    decision: DecisionType           # NEW | UPDATE | DUPLICATE
    similarity_score: float
    matched_alpha_id: Optional[str]  # id of the fact this duplicates/updates
    reasoning: Optional[str]
    delta: Optional[str]             # UPDATE only: one sentence — what is new
```

### `StoryNode` (`models/story.py`)
```python
@dataclass
class StoryNode:
    id: str
    topic_id: str
    title: str
    summary: str                     # LLM-maintained rolling summary of all facts
    status: StoryStatus              # ACTIVE
    fact_count: int                  # manually maintained — no DB trigger
    created_at / updated_at
```

---

## ADDING A NEW PIPELINE STAGE

1. Create `src/truebrief/your_stage/your_stage.py`
2. Accept `LLMClient` and/or `VectorStore` in `__init__` (never instantiate them internally)
3. Instantiate in `PipelineRunner.__init__()` — pass shared `self.vector_store.llm`
4. Call from `PipelineRunner.run()` in the correct sequence
5. Never import from a downstream stage (no circular imports — create a `models/` file if types are shared)

---

## ADDING A NEW SOURCE LAYER

```python
# In collector/your_source_layer.py:
from truebrief.collector.base import SourceLayer
from truebrief.models.article import RawArticle
from truebrief.collector.query_builder import SearchQuery

class YourSourceLayer(SourceLayer):
    name = "your_source"   # used in tier filtering

    def search(self, query: SearchQuery) -> list[RawArticle]:
        # call external API, return RawArticle list
        ...

# Register in PipelineRunner.__init__():
all_sources = [..., YourSourceLayer()]
```

---

## ARBITER THRESHOLDS (tuning guide)

```python
# arbiter/arbiter.py
AUTO_MERGE_THRESHOLD = 0.97   # above this → AUTO-DUPLICATE (no LLM)
GREY_ZONE_MIN        = 0.75   # below this → AUTO-NEW (no LLM)
LEDGER_FETCH_LIMIT   = 3      # top-N matches retrieved for judgment
LEDGER_FETCH_THRESHOLD = 0.50 # minimum score to even retrieve a match

# story_manager.py
STORY_ASSIGNMENT_THRESHOLD = 0.70  # minimum similarity to join existing story
```

**If too many duplicates reach the LLM (slow + expensive):** raise `AUTO_MERGE_THRESHOLD`.
**If new facts are being merged incorrectly:** lower `AUTO_MERGE_THRESHOLD` or raise `GREY_ZONE_MIN`.
**If new facts keep creating new stories instead of joining existing ones:** lower `STORY_ASSIGNMENT_THRESHOLD`.

---

## KNOWN ISSUES / GOTCHAS

1. **`event_date` is 87% empty** — The harvester extracts it but the LLM rarely populates it. The extractor prompt needs explicit instruction to extract temporal context from article text. Known gap.

2. **Arbiter sees paraphrases as NEW** — Same fact from different articles with different wording can slip through as NEW. The GREY_ZONE_MIN threshold (0.75) may be too low. Raising it to 0.80–0.85 and relying more on JudgeLLM would help.

3. **Collector re-scrapes same articles across runs** — No per-article URL deduplication against `known_facts.source_url`. The pipeline processes 5 articles per run but they may be the same 5 as last time. Add a `source_url IN (already_seen)` filter before MMR selection.

4. **`briefs.facts_json` is always NULL** — Dead column. Pipeline never writes it. Don't rely on it.

5. **`usatoday.com` injects wrong event_dates (2020 dates)** — The extractor accepts dates from article content without sanity-checking against the topic's time range. A date more than 2 years ago should be rejected or flagged.

6. **AYR engine and tier trigger conflict** — After a pipeline run, AYR sets `poll_interval_seconds`. After a subscription change, the tier trigger overwrites it. Last writer wins. This is a known design tension.

7. **Celery beat and worker must both be running** for scheduled scans to work. `start-local.ps1` starts both.

8. **`MAX_ARTICLES = 5` in runner.py** — Only 5 articles per pipeline run. Tune this if signal is thin.

9. **Circular imports are fatal** — If you need a type in two modules, put it in `models/`. Never import a downstream module from an upstream one.

10. **`memory://` Celery broker** — If `REDIS_URL` is missing from `.env`, Celery uses in-memory broker. Tasks won't persist across restarts and beat won't work. Always set `REDIS_URL`.

---

## BRIEF FORMAT (LLM output from Briefer)

```
📋 TrueBrief | {Topic Name} | {Date}

🆕 NEW STORIES ({N})
━━━━━━━━━━━━━━━━━━━━━━━━━━
**Story Title**
• Bullet fact one sentence. → Sources: [Source Name](url)
• Bullet fact two sentence. → Sources: [Name 1](url1), [Name 2](url2)

📈 UPDATES ({N})
━━━━━━━━━━━━━━━━━━━━━━━━━━
**Story Title**
• WHAT'S NEW: The delta fact. → Sources: [Source Name](url)
• FULL CONTEXT: Why this matters. → Sources: [Source Name](url)
```

Rules enforced in briefer prompt:
- Every bullet ends with `→ Sources: [Name](url)`
- Do NOT hallucinate — use only facts from the JSON payload
- If a section has 0 items, omit it entirely
- Group related facts under one `**heading**`

---

## INSPECTION / DEBUGGING SCRIPTS

```powershell
# Full audit of all stored data for a topic keyword
python scripts/audit_topic.py "iran"
# Output: reports/audit_iran_YYYYMMDD_HHMMSS.md
# Contains: all facts (with event_date, source, story), all story nodes with summaries,
#           all delivered briefs, signal stats (% with event_date, source diversity)

# Manual pipeline run (no Celery, runs synchronously, prints brief to console)
python scripts/run_pipeline.py "your topic"
python scripts/run_pipeline.py "your topic" --debug   # verbose logging

# Test DB + API connections
python scripts/test_connections.py

# Inspect AYR engine state
python scripts/test_ayr.py
```

<!-- INFRA/DEVOPS EDITOR: add your section here -->

---

# Skill: Database Editor
# Role: TrueBrief Supabase / Postgres — schema, migrations, data inspection, RLS

---

## WHAT YOU CAN DO

- Connect to the live Supabase project via MCP (`project_ref=lopsqdnfivdpsvsqzwdc`)
- Read, query, and inspect any table via `mcp__supabase__execute_sql`
- Apply schema migrations via `mcp__supabase__apply_migration`
- List tables, migrations, extensions via `mcp__supabase__list_*`
- Enable/disable RLS and create/drop policies
- Deduplicate, backfill, and repair data
- Add/drop columns, constraints, indexes, triggers, functions
- Wipe data from tables (DELETE, TRUNCATE) — with explicit user confirmation
- Write and maintain migration files in `scripts/migrations/`

## WHAT YOU CANNOT DO — ask the relevant editor instead

- Touch Python backend code in `src/truebrief/` (backend editor)
- Touch Next.js frontend code in `frontend/` (frontend editor)
- Change Clerk or Stripe settings
- Push to Railway / modify `railway.toml` (infra editor)

---

## MCP CONNECTION

The Supabase MCP server must be authenticated before any tool works.

```
project_ref: lopsqdnfivdpsvsqzwdc
MCP server: https://mcp.supabase.com/mcp?project_ref=lopsqdnfivdpsvsqzwdc
```

**Auth flow:**
1. Call `mcp__supabase__authenticate` — returns an OAuth URL
2. User opens the URL in browser and authorizes
3. If browser shows a connection error on redirect: paste the full redirect URL and call `mcp__supabase__complete_authentication`
4. On success, all `mcp__supabase__*` tools become available

**All MCP tools are deferred — load schema before calling:**
```
ToolSearch: "select:mcp__supabase__execute_sql,mcp__supabase__apply_migration,..."
```

---

## TOOLS REFERENCE

| Tool | What it does |
|---|---|
| `mcp__supabase__execute_sql` | Run any SELECT / DML — use for queries, inspections, data fixes |
| `mcp__supabase__apply_migration` | Run DDL (ALTER, CREATE, DROP, triggers, functions) — recorded in migration history |
| `mcp__supabase__list_tables` | List all tables with RLS status and row counts |
| `mcp__supabase__list_migrations` | List applied migration history |
| `mcp__supabase__get_advisors` | Security + performance advisories (RLS gaps, missing indexes, etc.) |
| `mcp__supabase__get_logs` | Fetch recent Postgres / API logs for debugging |

**Rule: use `execute_sql` for reads/data changes. Use `apply_migration` for schema changes** — migrations are recorded in Supabase history; `execute_sql` is not.

---

## SCHEMA

### Core tables

```
topics
  id                  uuid PK
  raw_query           text UNIQUE (lowercased) ← enforced by migration 007
  user_id             uuid nullable (original creator only — FK to users)
  is_active           bool
  poll_interval_seconds int  (set by AYR engine after each run; OR by tier trigger)
  last_run_at         timestamptz
  next_run_at         timestamptz

topic_subscriptions
  id                  uuid PK
  user_id             uuid NOT NULL → users(id) ON DELETE CASCADE
  topic_id            uuid NOT NULL → topics(id) ON DELETE CASCADE
  created_at          timestamptz
  UNIQUE(user_id, topic_id)

users
  id                  uuid PK  (Clerk user_id)
  email               text
  created_at          timestamptz

user_subscriptions
  user_id             uuid → users(id)
  tier                text  ('free' | 'pro' | 'power')

tier_intervals
  tier                text PK
  poll_interval_seconds int
  Values: free=86400, pro=3600, power=900

story_nodes
  id                  uuid PK
  topic_id            uuid → topics(id) ON DELETE CASCADE
  title               text
  summary             text
  summary_embedding   vector
  status              text  ('active')
  fact_count          int   (manually maintained — incremented in story_manager.py)
  created_at / updated_at timestamptz

known_facts
  id                  uuid PK
  topic_id            uuid → topics(id) ON DELETE CASCADE
  story_node_id       uuid → story_nodes(id)  ← NO ACTION (blocks story delete if facts exist)
  alpha_text          text
  alpha_embedding     vector
  entities            jsonb
  event_date          timestamptz
  confidence          float
  source_url          text
  source_domain       text
  first_seen_at       timestamptz

briefs
  id                  uuid PK
  topic_id            uuid → topics(id) ON DELETE CASCADE
  content             text  (rendered markdown — never an error string in current code)
  facts_json          jsonb (dead column — never populated; do not rely on it)
  delivered_at        timestamptz
  is_read             bool

source_quality_log
  topic_id            uuid → topics(id) ON DELETE CASCADE
  source_domain       text
  decision            text  ('NEW' | 'UPDATE' | 'DUPLICATE')
  (used by AYR engine to compute yield rate)

topic_query_variants
  topic_id            uuid → topics(id) ON DELETE CASCADE
  query_text          text
  UNIQUE(topic_id, query_text)
```

### FK cascade summary (important for delete order)

```
topics  ←CASCADE—  topic_subscriptions
        ←CASCADE—  story_nodes  ←NO ACTION—  known_facts.story_node_id
        ←CASCADE—  known_facts (via topic_id)
        ←CASCADE—  briefs
        ←CASCADE—  source_quality_log
        ←CASCADE—  topic_query_variants
users   ←CASCADE—  topic_subscriptions
```

**Safe delete order (children first):**
```sql
DELETE FROM known_facts;
DELETE FROM story_nodes;
DELETE FROM briefs;
DELETE FROM source_quality_log;
DELETE FROM topic_query_variants;
DELETE FROM topic_subscriptions;
DELETE FROM topics;
```

---

## MIGRATION CONVENTIONS

- Migration files live in `scripts/migrations/`
- Naming: `NNN_short_description.sql` (e.g. `008_tier_intervals_rls.sql`)
- Always use `IF EXISTS` / `IF NOT EXISTS` guards so migrations are re-runnable
- Always add a `-- Verify` SELECT at the end to confirm the result
- **Apply via `apply_migration` (not `execute_sql`)** so it's recorded in history
- **After applying**, run the verify SELECT with `execute_sql` to confirm

---

## SHARED TOPICS MODEL (migration 007)

Topics are shared — one row per unique `raw_query`. Multiple users subscribe via `topic_subscriptions`.

**Key invariants:**
- `topics.raw_query` is always lowercase and unique (UNIQUE constraint)
- `create_topic` in routes.py matches on `lower(raw_query)` before inserting
- `poll_interval_seconds` is set by two competing systems:
  1. **AYR engine** — after each successful pipeline run, sets interval based on yield rate (30min → 6h)
  2. **Tier trigger** (`trg_topic_sub_interval`) — on subscribe/unsubscribe, calls `refresh_topic_interval()` which sets interval = MIN across all subscribers' tiers
  - These two systems can conflict. AYR wins on pipeline runs; tier wins on subscription changes.

---

## RLS STATUS

```
topics                  RLS enabled
topic_subscriptions     RLS enabled
users                   RLS enabled
user_subscriptions      RLS enabled
known_facts             RLS enabled
briefs                  RLS enabled
story_nodes             RLS enabled
source_quality_log      RLS enabled
topic_query_variants    RLS enabled
tier_intervals          RLS enabled  ← migration 008: public SELECT only, no writes
push_subscriptions      RLS enabled
processed_paddle_events RLS enabled
```

All tables have RLS. `tier_intervals` allows public SELECT (config data), no writes via client.

---

## INSPECTION QUERIES

### Full topic health snapshot
```sql
SELECT
    t.raw_query,
    t.is_active,
    t.poll_interval_seconds,
    t.last_run_at,
    t.next_run_at,
    EXTRACT(EPOCH FROM (now() - t.last_run_at))::int / 3600 AS hours_since_run,
    (SELECT count(*) FROM topic_subscriptions ts WHERE ts.topic_id = t.id) AS subs,
    (SELECT count(*) FROM story_nodes sn WHERE sn.topic_id = t.id) AS stories,
    (SELECT count(*) FROM known_facts kf WHERE kf.topic_id = t.id) AS facts,
    (SELECT count(*) FROM briefs b WHERE b.topic_id = t.id) AS briefs
FROM topics t
ORDER BY subs DESC, facts DESC;
```

### Orphan facts (no story)
```sql
SELECT t.raw_query,
       count(*) FILTER (WHERE kf.story_node_id IS NULL) AS orphan_facts,
       count(*) AS total_facts
FROM topics t
LEFT JOIN known_facts kf ON kf.topic_id = t.id
GROUP BY t.raw_query
HAVING count(*) FILTER (WHERE kf.story_node_id IS NULL) > 0;
```

### story_nodes.fact_count drift
```sql
SELECT sn.id, sn.title, sn.fact_count AS declared,
       count(kf.id) AS actual
FROM story_nodes sn
LEFT JOIN known_facts kf ON kf.story_node_id = sn.id
GROUP BY sn.id, sn.title, sn.fact_count
HAVING sn.fact_count != count(kf.id);
```

### Subscription → user health
```sql
SELECT ts.user_id, ts.topic_id, t.raw_query,
       (SELECT count(*) FROM users u WHERE u.id = ts.user_id) AS user_exists,
       (SELECT us.tier FROM user_subscriptions us WHERE us.user_id = ts.user_id LIMIT 1) AS tier
FROM topic_subscriptions ts
JOIN topics t ON t.id = ts.topic_id;
```

### Brief quality (error strings, empty facts_json)
```sql
SELECT t.raw_query,
       count(*) FILTER (WHERE b.content LIKE '%Error generating brief%') AS error_briefs,
       count(*) FILTER (WHERE length(b.content) < 30) AS too_short,
       count(*) AS total
FROM briefs b
JOIN topics t ON t.id = b.topic_id
GROUP BY t.raw_query
ORDER BY error_briefs DESC;
```

### Row counts for all tables
```sql
SELECT table_name,
       (xpath('/row/cnt/text()', query_to_xml(
           'SELECT count(*) AS cnt FROM ' || quote_ident(table_name),
           false, true, '')))[1]::text::int AS row_count
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name;
```

---

## KNOWN ISSUES / GOTCHAS

1. **`known_facts.story_node_id` is NO ACTION** — deleting a story_node that still has facts will fail. Always delete facts first, or update `story_node_id = NULL` before deleting a story.

2. **`story_nodes.fact_count` is manually maintained** — there is no DB trigger. It's incremented in `story_manager.py`. If facts are deleted directly from DB, `fact_count` will drift. Use the drift detection query above.

3. **`briefs.facts_json` is always NULL** — the column exists in schema but the pipeline never writes it. Do not rely on it. Consider dropping it in a future migration.

4. **`briefs` has no `created_at`** — only `delivered_at`. Cannot distinguish generation time from delivery time.

5. **AYR vs tier interval conflict** — after a pipeline run, AYR may overwrite the tier-based `poll_interval_seconds`. After a subscription change, the tier trigger overwrites AYR. The last writer wins.

6. **Orphan subscriptions** — if a user is deleted via Clerk but their `users` row is not cleaned up first, the FK cascade won't fire. Always delete from `users` table before or alongside Clerk deletion.

7. **`topic_query_variants` has UNIQUE(topic_id, query_text)** — when merging duplicate topics, delete conflicting variants from the dup before re-pointing, or use ON CONFLICT DO NOTHING.

8. **`topics.user_id` is nullable** (migration 007) — it's original-creator metadata only. Never use it to fan out push notifications; always use `topic_subscriptions` instead.

---

## DATA WIPE PROCEDURE

When doing a full clean slate (keep schema + config, wipe all collected data):

```sql
-- Wipe collected data (safe order)
DELETE FROM known_facts;
DELETE FROM story_nodes;
DELETE FROM briefs;
DELETE FROM source_quality_log;
DELETE FROM topic_query_variants;
DELETE FROM topic_subscriptions;
DELETE FROM topics;
-- Optional: wipe user accounts too
DELETE FROM user_subscriptions;
DELETE FROM users;
-- DO NOT wipe: tier_intervals (config needed by trigger)
-- DO NOT wipe: push_subscriptions, processed_paddle_events (unless explicitly asked)
```
