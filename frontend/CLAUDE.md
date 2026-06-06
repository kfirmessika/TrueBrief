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
    dashboard/       # Topic feed with preview cards
    topics/new/      # Topic creation page
    topics/[id]/     # Topic thread — briefs, source chips, scan progress
    settings/        # User/billing settings
  sign-in/ sign-up/  # Clerk hosted auth pages
```

### Auth + API pattern
- **Every authenticated API call** must go through `useApi()` (`src/lib/useApi.ts`), which injects the Clerk JWT automatically via an axios interceptor.
- `src/lib/api.ts` exports typed API helpers (`topicsApi`, `briefsApi`, `billingApi`) and the `apiFetch` server-side helper that uses `auth()` from `@clerk/nextjs/server`.
- The middleware (`src/proxy.ts`) protects `/dashboard`, `/topics`, `/onboarding`, `/settings` via Clerk.
- Never use the bare `api` export from `lib/api.ts` in client components — it has no auth token. Use `useApi()` instead.

### Data fetching
- All client-side data fetching via React Query (`@tanstack/react-query`).
- Global `QueryClient` lives in `src/app/providers.tsx` — default `staleTime: 60_000`, `retry: 1`.
- Query keys follow this convention:
  - `['topics']` — sidebar list
  - `['topic', id]` — single topic (includes `last_scan_at`)
  - `['topic-briefs', id]` — briefs for topic page
  - `['topic-known-facts', id]` — raw alpha articles (source chip tooltips)
  - `['scan-status', taskId]` — Celery task poll (2s interval, stops on SUCCESS/FAILURE)
  - `['dashboard']` — dashboard feed

### Scan task flow
When a scan is triggered (sidebar 3-dots → Scan, or new topic creation), the backend returns a `task_id`. The frontend stores it in `localStorage` as `scan_task_${topicId}`. The topic page polls `localStorage` every 500ms to pick it up and render `ScanProgressBar`. `useScanStatus` polls `/scan-status/{taskId}` every 2s; on SUCCESS it invalidates `['topic', id]`, `['topic-briefs', id]`, and `['topics']`. On 429 errors, the sidebar shows a rate-limit message.

### Styling
- **No Tailwind in the app shell or topic page** — those use inline `style={{}}` props with CSS variables from the design system (e.g. `var(--color-text-primary)`, `var(--tb-green)`).
- Tailwind is used in some older components under `src/components/`.
- Don't mix the two approaches within a single file.

### Topic page (`topics/[id]/page.tsx`)
This is the most complex file. Key internal architecture:

- **`parseBriefSections(md)`** — splits brief markdown into `BriefSection[]`. Each section has a heading, body lines, and sources. Badge lines (`🆕 NEW STORIES`) become `isBadge: true` sections.
- **`renderBodyLine(line, key)`** — renders a single body line. Detects ` → Sources: [Name](url)` at the end of a bullet and renders `SourcePill` chips inline (per-bullet attribution). Falls back to section-level sources for old briefs.
- **`SourcePill`** — reads `DomainAlphasCtx` (React context) to populate its tooltip with raw alpha articles from `known_facts`. Uses a 200ms hide delay so the user can hover into the tooltip.
- **`DomainAlphasCtx`** — populated from `GET /topics/{id}/known-facts`, grouped by `source_domain`. Provided at page root, consumed by every `SourcePill`.
- **`ScanProgressBar`** — shown when `scanTaskId` is set. Receives `taskId` as a prop; internally calls `useScanStatus`.

### Brief content format
Briefs are raw markdown strings stored in the `briefs` table. The LLM outputs:
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
• WHAT'S NEW: ... → Sources: [domain.com](url)
• FULL CONTEXT: ... → Sources: [domain.com](url)
```
The `parseContent()` helper strips the `📋 TrueBrief` header line before passing to `parseBriefSections`.

### Source chips
- `parseSourceLine(line)` parses `→ Sources: [Name](url), ...` into `SourceChip[]`.
- `SourceChip.url` = full article URL; `SourceChip.domain` = hostname (e.g. `reuters.com`).
- Chips link directly to the article URL when available, otherwise to the domain homepage.
- Tooltip shows: domain header + up to N raw alpha articles from that domain for this topic (text snippet, date, "View article →" link).

### Hooks (`src/hooks/`)
- `useTopics` / `useCreateTopic` / `useDeleteTopic` / `useTriggerScan` / `useScanStatus` — all in `useTopics.ts`
- `useTier` — reads billing tier for gating UI
- `useStats` — user stats for the dashboard
- `usePushNotifications` — web push subscription management
