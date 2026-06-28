---
name: truebrief-frontend
description: Conventions for editing the TrueBrief Next.js frontend (frontend/**) — App Router pages, Clerk auth, React Query hooks, useApi, Tailwind/CSS-variable styling, and brief rendering. Use when writing or changing frontend code. Covers the query-key table, the styling split, topic-page internals, Next.js 16 gotchas, and the mandatory tsc + build gate.
---

# TrueBrief Frontend — Next.js 16 App Router · Clerk · React Query

**Scope:** `frontend/`. Do NOT touch `src/truebrief/` (see [[truebrief-backend]]), DB schema, or deployment config.

## Dev commands (from `frontend/`)
```bash
npm run dev                       # hot-reload at http://localhost:3000
npx tsc --noEmit --skipLibCheck   # type-check — run before finishing ANY change
npm test                          # Vitest + MSW
npm run build                     # production build — MUST run and report PASS/FAIL
npm run lint                      # eslint
```
**Rule: never report done without running `npx tsc --noEmit --skipLibCheck` AND `npm run build`.**

## Rules that must never break
1. **All client API calls go through `useApi()`** (`lib/useApi.ts`) — it injects the Clerk JWT. Never use bare `api` from `lib/api.ts` in a `'use client'` file.
2. **`apiFetch` is server-side only** — it calls `auth()` from `@clerk/nextjs/server`. Never import it in a client component.
3. **No circular imports** — shared types go in a third `types.ts`.
4. **Styling split (never mix in one file):** app shell (`app/(app)/layout.tsx`), topic page (`topics/[id]/page.tsx`), sidebar → inline `style={{}}` with CSS vars. Components in `components/` → Tailwind.
5. **Never hardcode colors** — use CSS vars (`var(--tb-green)`, `var(--color-text-primary)`), all defined in `app/globals.css`.
6. Components in `components/` use **named exports** (no default).

## File map (`frontend/src/`)
`app/` — layout.tsx (ClerkProvider), providers.tsx (QueryClient staleTime 60s, retry 1), `(marketing)/` public landing, `(app)/` shell (Sidebar + main): `dashboard/`, `topics/new/`, `topics/[id]/` (most complex), `settings/`. `components/` — layout (Sidebar, Navbar, Footer), topics (AddTopicForm, TopicCard, ScanButton, ScanStatusBadge, TopicTabs, UpgradeBanner), briefs (BriefCard, BriefContent, CopyLinkButton), ui (Skeleton, Toast+useToast, ConfirmDialog, EmptyState, ErrorBoundary, motion). `hooks/` — useTopics, useTier, useStats, usePushNotifications. `lib/` — useApi, api (typed helpers + apiFetch + types), utils (cn). `proxy.ts` — Clerk middleware (protects /dashboard /topics /onboarding /settings).

## React Query keys
| Key | Endpoint | Notes |
|---|---|---|
| `['topics']` | GET /topics | Sidebar subscribes; 30s |
| `['topic', id]` | GET /topics/{id} | staleTime 0; refetch 60s |
| `['topic-briefs', id]` | GET /topics/{id}/briefs | 5s poll while scanning, else 60s |
| `['topic-known-facts', id]` | GET /topics/{id}/known-facts | source-chip tooltips |
| `['scan-status', taskId]` | GET /scan-status/{taskId} | 2s poll; stops on SUCCESS/FAILURE |
| `['dashboard']` | GET /dashboard | 30s |
| `['shared-topics', q]` | GET /shared-topics?q= | 10s |
On scan SUCCESS/FAILURE invalidate `['topics']`, `['topic', id]`, `['topic-briefs', id]`. Key convention: `['noun', id?]`, lowercase, array.

## Scan flow (end to end)
Trigger (sidebar 3-dots Scan / new topic) → `POST /topics/{id}/scan` → store `scan_task_${topicId}` in localStorage → topic page polls localStorage every 500ms → renders `ScanProgressBar` (8 friendly step labels, bar caps at 90% until backend confirms) → `useScanStatus` polls `/scan-status/{taskId}` every 2s → on SUCCESS bar → 100%, clears localStorage, invalidates queries. 429 → sidebar reads `Retry-After`, shows "Next scan available in X hours".

## Gotchas
1. **`last_scan_at` vs `last_run_at`** — DB column is `last_run_at`; API serializes to `last_scan_at`; frontend uses `last_scan_at`. Don't query `last_scan_at` in the DB.
2. **Next.js 16, not 13/14** — before using router/params/cookies/headers, check current behavior. `params` are async: `{ params }: { params: Promise<{id: string}> }` → `const { id } = use(params)`.
3. **`useApi()` returns a new axios instance each call** — call it at the top of the component, not inside handlers/effects.
4. **`scan_task_id`** only present on new-topic create (not when subscribing to a shared topic) — check before storing.
5. **Brief filtering** — `visibleBriefs` drops briefs containing "error generating" or `< 30` chars. Don't emit shorter/error briefs.
6. **Sidebar is always light** — no `dark:` classes there.

## Verifying UI in this session
The session may expose **Preview** (`mcp__Claude_Preview__*`) and **Chrome** (`mcp__Claude_in_Chrome__*`) MCP tools — use them to start the dev server, screenshot, click, and read console/network for real UI verification. See the `/verify` and `/run` skills.

Brief markdown format is shared with the backend — see [[truebrief-pipeline]] for the exact section/source syntax.
