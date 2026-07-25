# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

---

## Commands

```bash
# Dev server (from frontend/)
npm run dev          # http://localhost:3000

# Type check
npx tsc --noEmit --skipLibCheck

# Tests
npm test             # Vitest + MSW

# Production build (run before finishing any task)
npm run build
```

---

## Architecture

### Route layout
```
src/app/
  (marketing)/       # Public landing page — no auth
  (app)/             # All authenticated routes — wrapped by AppLayout (Sidebar + main)
    dashboard/       # "Today" feed — per-topic flip cards (unseen alphas / cheap-LLM summary)
    topics/new/      # Topic creation page
    topics/[id]/     # Topic view — sticky header (scan + schedule) + alpha/context timeline
    admin/compare/   # Internal-only: V4 vs V5 vs reference brief comparison tool
    settings/        # User/billing settings
  sign-in/ sign-up/  # Clerk hosted auth pages
```

**V5 note (2026-07):** there is no user-facing "Brief" page/route. The backend's `Briefer`
still generates a markdown brief every scan (`docs/core/architecture_v5.md`), but the only
place it's ever rendered is `admin/compare` (internal pipeline-comparison tool, via
`BriefContent`). Regular users see the raw alpha+context timeline (topic page) and a cheap
per-visit LLM summary (dashboard flip card) — never the Briefer markdown directly. Don't
reintroduce a brief-viewing route without checking this is still true; several dead
components (`TopicCard`, `TopicTabs`, `BriefCard`, `CopyLinkButton`, a `briefsApi` export, a
`useMarkBriefsRead` hook, a non-functional "Search briefs" box) were removed 2026-07-26
because they pointed at a `/topics/{id}/briefs` route that never existed as a real page.

### Auth + API pattern
- **Every authenticated API call** must go through `useApi()` (`src/lib/useApi.ts`), which injects the Clerk JWT automatically via an axios interceptor.
- `src/lib/api.ts` exports typed API helpers (`topicsApi`, `billingApi`) and the `apiFetch` server-side helper that uses `auth()` from `@clerk/nextjs/server`.
- The middleware (`src/proxy.ts`) protects `/dashboard`, `/topics`, `/onboarding`, `/settings` via Clerk.
- Never use the bare `api` export from `lib/api.ts` in client components — it has no auth token. Use `useApi()` instead.

### Data fetching
- All client-side data fetching via React Query (`@tanstack/react-query`).
- Global `QueryClient` lives in `src/app/providers.tsx` — default `staleTime: 60_000`, `retry: 1`.
- Query keys follow this convention:
  - `['topics']` — sidebar list
  - `['topic', id]` — single topic (includes `last_scan_at`)
  - `['topic-history', id]` — the alpha/context timeline (`GET /topics/{id}/history`)
  - `['topic-schedule', id]` — alarm-clock run times (`GET/PUT /topics/{id}/schedule`)
  - `['scan-status', taskId]` — Celery task poll (2s interval, stops on SUCCESS/FAILURE)
  - `['feed']` — dashboard "Today" feed (`GET /feed`, unseen alphas per topic)

### Scan task flow
When a scan is triggered (sidebar 3-dots → Scan, or new topic creation), the backend returns a `task_id`. The frontend stores it in `localStorage` as `scan_task_${topicId}`. The topic page polls `localStorage` every 500ms to pick it up and render `ScanProgressBar`. `useScanStatus` polls `/scan-status/{taskId}` every 2s; on SUCCESS it invalidates `['topic', id]`, `['topic-history', id]`, and `['topics']`. On 429 errors, the sidebar shows a rate-limit message.

### Styling
- **No Tailwind in the app shell or topic page** — those use inline `style={{}}` props with CSS variables from the design system (e.g. `var(--color-text-primary)`, `var(--tb-green)`).
- Tailwind is used in some older components under `src/components/`.
- Don't mix the two approaches within a single file.

### Topic page (`topics/[id]/page.tsx`)
- **Sticky header**: topic name, scan status/button (`ScanProgressBar` while running), and the
  alarm-clock schedule picker (`GET/PUT /topics/{id}/schedule` — daily UTC run times, default
  1/day; replaces the old Auto/Slow/Medium/Fast/Ultra-Fast interval picker, see
  `docs/core/architecture_v5.md §7`).
- **`HistoryView`**: fetches `GET /topics/{id}/history`, renders every stored fact grouped by
  day, newest first. This is the entire content area — no tabs, no story mode (removed
  2026-07-26; it hallucinated causation/corrupted numbers and was never proven better than
  the plain feed — see `docs/core/V4_ARCHIVE.md`).
- **`HistoryFactRow`**: the actual per-fact presentation — fact text, its additive `context`
  line directly below (from the harvester/collector's context field, never a restatement),
  an event-class chip for `state_change`/`escalation` only, a `SourceChip`, a
  "✓ N sources" badge when corroborated, and a "⚠️ Disputed" badge when `contradiction_note`
  is set.

### Source chips
- `SourceChip` (`src/components/SourceChip.tsx`) takes `{ domain, url }` and renders a
  favicon-linked chip to the source article (falls back to the domain homepage).
- Used identically in `HistoryFactRow` (topic page) and `AlphaRow` (dashboard flip card) —
  the two real places facts are ever shown to a user.

### Hooks (`src/hooks/`)
- `useTopics` / `useCreateTopic` / `useDeleteTopic` / `useTriggerScan` / `useScanStatus` — all in `useTopics.ts`
- `useTier` — reads billing tier for gating UI
- `useStats` — user stats for the dashboard
- `usePushNotifications` — web push subscription management
