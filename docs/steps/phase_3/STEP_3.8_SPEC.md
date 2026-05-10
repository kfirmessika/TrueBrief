# STEP SPEC — 3.8: Topic Management UI
> **Status:** [x] PLAN COMPLETE | [x] BUILD | [x] UNIT | [x] INTG
> **Planner:** Claude Sonnet 4.6
> **Date:** 2026-05-08
> **Depends on:** 3.6 (Next.js skeleton — done), 3.7 (Auth — done)
> **Blocks:** 3.9 (Brief display deep-link is reachable from this page)

---

## 🎯 Objective

Replace the placeholder `/dashboard` and `/topics/[id]` pages with a working topic-management UI that:

1. Lists the authenticated user's topics (live data from `GET /api/v1/topics`).
2. Lets the user add a topic (POST + optimistic insert; respects 402 from 3.5 enforcement).
3. Lets the user delete a topic (with confirmation; optimistic remove).
4. Lets the user manually trigger a scan from a topic card (POST `/topics/{id}/scan`; respects 429 from 3.5 enforcement; polls task status).
5. Shows tier-aware CTAs: when a Free user is at the 2-topic cap, the "Add Topic" button is replaced with an upgrade prompt.

This step does **not** render brief content — that ships in 3.9. The topic detail page in this step is a thin shell with metadata + a "View briefs" link.

---

## 📐 Design & Logic

### Data flow

```
┌────────────────────┐    React Query     ┌──────────────────────┐
│ /dashboard (RSC)   │────────────────────│ apiFetch (server)    │
│  └─ <TopicList>    │  initial fetch     │   GET /api/v1/topics │
└────────────────────┘                    └──────────────────────┘
        │ hydrate
        ▼
┌────────────────────────────────────────────────────────────┐
│ Client components (use 'use client')                        │
│   TopicCard, AddTopicForm                                   │
│   useApi() → axios w/ Bearer from useAuth().getToken()      │
│   useMutation(createTopic / deleteTopic / triggerScan)      │
│   useQueryClient().invalidateQueries(['topics'])            │
└────────────────────────────────────────────────────────────┘
```

**Two-tier fetch strategy:**
- **Server component (`/dashboard/page.tsx`)** does the *first* fetch via `apiFetch` so SSR has data and auth state. The RSC passes the result as a prop to a client `TopicListClient` wrapper.
- **Client component** owns mutations and polling via React Query, using a new `useApi()` hook that returns an axios instance with the Clerk JWT injected per call.

### Backend contract (already shipped in 3.7)

`GET /api/v1/topics` returns `Topic[]`:
```json
[{"id": "uuid", "raw_query": "AI regulation", "frequency": "hourly", "is_active": true}]
```
`POST /api/v1/topics` body: `{"raw_query": "...", "poll_interval_seconds": 3600}` → `Topic`.
`DELETE /api/v1/topics/{id}` → `{"status": "deleted"}`.
`POST /api/v1/topics/{id}/scan` → `{"status": "queued", "task_id": "...", "topic_id": "..."}`.
`GET /api/v1/scan-status/{task_id}` → `{state, message, result?, error?}`.

**Type mismatch alert:** Current `frontend/src/lib/api.ts` declares `Topic` with `query, name, created_at, last_scan_at`. Backend returns `raw_query, frequency, is_active`. The build session must reconcile this — the `Topic` type and `topicsApi.create(name, query)` signature in `api.ts` are wrong as-shipped. Fix is to make the frontend type match the backend and drop the unused `name` field (users only supply `raw_query`).

### Tier-aware UX

```
┌─────────────────────────────────────────────────────────┐
│ Header: "Your Topics"          [Free: 2/2 used]         │
│                                                          │
│ if (count < max_topics OR power):                       │
│   [+ Add Topic]                                         │
│ else:                                                    │
│   [⚡ Upgrade to Pro to add more topics →]              │
└─────────────────────────────────────────────────────────┘
```

The dashboard fetches `GET /api/v1/billing/status` (already in 3.7) once on mount to know the user's tier + limits. Cached for 5 minutes via React Query.

When a 402 comes back from `POST /topics`, surface the `detail` field in a toast and show the upgrade CTA. When a 429 comes back from `/scan`, show "Scan rate-limited — try again in N minutes" extracted from `detail`.

### Component tree

```
src/
├── app/
│   ├── dashboard/
│   │   ├── page.tsx                  # RSC — initial fetch, hand to client wrapper
│   │   └── DashboardClient.tsx       # 'use client' — list + add form + mutations
│   └── topics/[id]/
│       └── page.tsx                  # RSC — fetch one topic, render shell
├── components/
│   ├── topics/
│   │   ├── TopicCard.tsx             # 'use client' — single topic row, scan/delete buttons
│   │   ├── AddTopicForm.tsx          # 'use client' — input + submit, optimistic update
│   │   ├── UpgradeBanner.tsx         # 'use client' — shown at cap
│   │   └── ScanStatusBadge.tsx       # 'use client' — polls scan-status until terminal
│   └── ui/
│       ├── ConfirmDialog.tsx         # delete confirmation
│       └── Toast.tsx                 # surfaces 402/429 errors
├── lib/
│   ├── api.ts                        # FIX existing — reconcile Topic type
│   └── useApi.ts                     # NEW — client-side axios w/ Bearer
└── hooks/
    └── useTopics.ts                  # NEW — useQuery + mutations bundle
```

### `useApi.ts` (client-side Bearer injection)

```typescript
'use client';
import axios, { AxiosInstance } from 'axios';
import { useAuth } from '@clerk/nextjs';
import { useMemo } from 'react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export function useApi(): AxiosInstance {
  const { getToken } = useAuth();
  return useMemo(() => {
    const instance = axios.create({ baseURL: API_BASE_URL });
    instance.interceptors.request.use(async (config) => {
      const token = await getToken();
      if (token) config.headers.Authorization = `Bearer ${token}`;
      return config;
    });
    return instance;
  }, [getToken]);
}
```

### `useTopics.ts`

```typescript
'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';

export function useTopics() {
  const api = useApi();
  return useQuery({
    queryKey: ['topics'],
    queryFn: async () => (await api.get<Topic[]>('/topics')).data,
  });
}

export function useCreateTopic() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (raw_query: string) =>
      api.post<Topic>('/topics', { raw_query, poll_interval_seconds: 3600 }).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['topics'] }),
    // 402 / 429 surface as AxiosError; consumer reads err.response?.data.detail
  });
}

export function useDeleteTopic() { /* mutationFn = api.delete; invalidate */ }

export function useTriggerScan() { /* mutationFn = api.post(.../scan); returns task_id */ }

export function useScanStatus(taskId: string | null) {
  const api = useApi();
  return useQuery({
    queryKey: ['scan-status', taskId],
    queryFn: async () => (await api.get(`/scan-status/${taskId}`)).data,
    enabled: !!taskId,
    refetchInterval: (data) =>
      data?.state === 'SUCCESS' || data?.state === 'FAILURE' ? false : 2000,
  });
}
```

### `TopicCard` UX

```
┌────────────────────────────────────────────────────┐
│ AI regulation                              ⚙ 🗑    │
│ Last scan: 2h ago · 3 briefs                       │
│                                                     │
│ [↻ Scan now]   [→ View briefs]                     │
└────────────────────────────────────────────────────┘
```

When `Scan now` is clicked:
1. POST `/topics/{id}/scan` via `useTriggerScan`.
2. Store the returned `task_id` in local state.
3. `useScanStatus(taskId)` polls `/scan-status/{task_id}` every 2s.
4. Card shows a spinner badge with the current `state`. On `SUCCESS`, it invalidates `['topics']` (to refresh `last_scan_at`) and clears `task_id`. On `FAILURE`, it shows `error` text + a retry button.

### Empty state, loading, error

- **Loading:** skeleton cards (3 placeholders).
- **Empty:** the existing dashed-box "No topics yet" placeholder, with the `AddTopicForm` inline.
- **Error (5xx):** "Couldn't load topics" + retry button. (401 should not happen on this page — Clerk middleware redirects.)

---

## 📂 File GPS

**Reads (BUILD session):**
- `frontend/src/app/dashboard/page.tsx` — current placeholder
- `frontend/src/app/topics/[id]/` — existing scaffolding (if any)
- `frontend/src/lib/api.ts` — to fix the Topic type
- `frontend/src/components/layout/Navbar.tsx` — for tier badge integration
- `src/truebrief/api/routes.py` — to confirm response shapes
- `src/truebrief/billing/billing_routes.py` — for `/billing/status` shape

**Touches:**
- `frontend/src/lib/api.ts` — **Modify** (reconcile `Topic` type to backend; drop `name`; keep `apiFetch` for RSC usage)
- `frontend/src/lib/useApi.ts` — **Create** (client axios + Clerk bearer)
- `frontend/src/hooks/useTopics.ts` — **Create** (`useTopics`, `useCreateTopic`, `useDeleteTopic`, `useTriggerScan`, `useScanStatus`)
- `frontend/src/hooks/useTier.ts` — **Create** (`useTier()` → React Query against `/billing/status`)
- `frontend/src/app/dashboard/page.tsx` — **Modify** (RSC, prefetch via `apiFetch`, hand to client)
- `frontend/src/app/dashboard/DashboardClient.tsx` — **Create**
- `frontend/src/app/topics/[id]/page.tsx` — **Create or Modify** (topic detail shell)
- `frontend/src/components/topics/TopicCard.tsx` — **Create**
- `frontend/src/components/topics/AddTopicForm.tsx` — **Create**
- `frontend/src/components/topics/UpgradeBanner.tsx` — **Create**
- `frontend/src/components/topics/ScanStatusBadge.tsx` — **Create**
- `frontend/src/components/ui/ConfirmDialog.tsx` — **Create**
- `frontend/src/components/ui/Toast.tsx` — **Create** (or use a small toast lib if simpler)
- `frontend/src/app/providers.tsx` — **Modify** (ensure `QueryClientProvider` wraps the tree if not already)
- `frontend/src/__tests__/topics.test.tsx` — **Create** (UNIT — see Testing section)

**Do NOT touch (deferred):**
- Brief rendering (NEW/UPDATE blocks, full content) → 3.9
- Brief history pagination → 3.10
- Onboarding-specific topic suggestions → 3.12
- Public sharing UI → 3.14

---

## 🛠 Execution Steps (for the BUILD session — RUN 10)

1. [ ] Reconcile `frontend/src/lib/api.ts` `Topic` type to `{ id: string; raw_query: string; frequency: string; is_active: boolean; last_scan_at?: string | null }`. Drop the `name`-based create signature.
2. [ ] Create `frontend/src/lib/useApi.ts` (client axios w/ Bearer) and `frontend/src/hooks/useTopics.ts` + `useTier.ts`.
3. [ ] Confirm `app/providers.tsx` wraps the tree in `QueryClientProvider` (create or extend it). If not already, add it under `<ClerkProvider>` in `layout.tsx`.
4. [ ] Build `TopicCard.tsx` — stateless props: `topic`, `onScan`, `onDelete`. Emits intents up to `DashboardClient`.
5. [ ] Build `AddTopicForm.tsx` — controlled input + submit, optimistic insert via `useCreateTopic`.
6. [ ] Build `UpgradeBanner.tsx` — shown when `tier === 'free' && topics.length >= 2`.
7. [ ] Build `ScanStatusBadge.tsx` — wraps `useScanStatus`, shows pill (`Queued` / `Running` / `Done` / `Failed`).
8. [ ] Build `ConfirmDialog.tsx` (small, no dep) — used by delete flow.
9. [ ] Build `Toast.tsx` for 402/429 surfacing. Show the backend `detail` verbatim.
10. [ ] Replace `app/dashboard/page.tsx` — RSC that uses `apiFetch` + hands data to `DashboardClient`.
11. [ ] Build `DashboardClient.tsx` — composes `useTopics`, `useTier`, all mutations, conditional CTA.
12. [ ] Create `app/topics/[id]/page.tsx` — RSC fetch of one topic via `apiFetch`, shows raw_query, last_scan_at, link to `/topics/[id]/briefs` (placeholder for 3.9), and `Scan now` + `Delete` buttons.
13. [ ] Run `npm run build` and `npm run lint`. Fix all type errors.
14. [ ] Hand-test in dev server (golden path + at-cap path + delete + scan).

---

## ✅ Testing & Verification

### Unit Tests (target: 8 tests)

Frontend unit tests can use **Vitest** + **React Testing Library** (add to `devDependencies` if not present). Each test renders a component with a mocked `useApi` returning a stub axios.

- [ ] `TopicCard renders raw_query and last_scan_at humanized`.
- [ ] `TopicCard fires onScan when Scan-now clicked`.
- [ ] `TopicCard fires onDelete only after ConfirmDialog accepts`.
- [ ] `AddTopicForm disables submit when input is empty`.
- [ ] `AddTopicForm calls createTopic with the trimmed raw_query`.
- [ ] `UpgradeBanner is rendered when tier=free & count>=2 & not power`.
- [ ] `UpgradeBanner is hidden when tier=pro`.
- [ ] `ScanStatusBadge stops polling on SUCCESS`.

### Integration Tests (target: 4 tests)

Run via Playwright or Vitest with MSW (mock service worker) intercepting the backend. Bring up the dev server, log in via Clerk's `setupClerkTestingToken` helper, hit each path:

- [ ] `Add topic → appears in list within 1s` (golden path).
- [ ] `Add 3rd topic on Free tier → toast shows "Upgrade your plan"`.
- [ ] `Delete topic → row disappears, list refetches`.
- [ ] `Trigger scan → badge cycles through STARTED → SUCCESS, last_scan_at refreshes`.

### Browser Smoke (RUN 10 — INTG)

This step's INTG cycle is bundled into RUN 10 (Flash). Smoke checklist:

1. Boot backend (`uvicorn`) + frontend (`npm run dev`) + Celery worker (`scripts/start_worker.py`).
2. Sign in with a Free-tier test user (one already created in 3.7 smoke).
3. From `/dashboard`: add 2 topics, confirm both appear; try a 3rd → toast shows the 402 detail.
4. Click **Scan now** on one topic; badge cycles through `STARTED → SUCCESS`. `last_scan_at` updates.
5. Try **Scan now** again immediately → toast shows the 429 detail.
6. Click **Delete** on a topic; confirm dialog appears; accept → row disappears.
7. Visit `/topics/<id>` → shell loads with `raw_query` and a link to (placeholder) briefs.
8. Open the Network tab — every request to `/api/v1/*` carries `Authorization: Bearer <jwt>`.

**Acceptance criteria** (mirrored from blueprint § 3.8):
- Topic appears in list within 2s of submit (optimistic).
- Scan button shows spinner during scan.
- Delete confirmation modal appears.
- Free user at 2-topic limit sees the upgrade prompt instead of "Add Topic".

---

## 📝 Planner Notes

**Why a `useApi` hook instead of a singleton axios.** Clerk's `getToken()` is async and tied to the user's React context. A module-level axios instance can't reach `useAuth`. Alternatives are: (a) attach the token at every call site, (b) use `apiFetch` from `lib/api.ts` everywhere, (c) build a hook. (c) is the standard Clerk + React Query pattern and gives us a single interceptor to evolve later (retries, refresh handling).

**Why keep both `apiFetch` (server) and `useApi` (client).** RSC pages can prefetch with `apiFetch` for SSR; client components mutate with `useApi`. Mixing the two is fine — React Query's `dehydrate`/`hydrate` keeps the initial server result populated in the cache so the first client render doesn't re-fetch.

**Polling strategy for scan status.** Real-time would need a SSE/WebSocket from the Celery worker. Out of scope here; 2s polling is acceptable for manual scans the user explicitly triggered. Auto-scheduled scans don't need a UI badge — the next dashboard load surfaces the new brief.

**Don't render brief content here.** The blueprint reserves brief rendering for 3.9 (NEW/UPDATE blocks). The topic detail page in this step has only metadata + a forward link, otherwise we double-build and slow 3.9.

**Type reconciliation is mandatory.** The `Topic` interface in `lib/api.ts` was wrong as shipped — the BUILD session must fix it before anything else. Skipping that fix means `topic.name` references will compile but blow up at runtime (`undefined`).

**Optimistic updates without server roundtrip risk.** React Query's `onMutate` rollback handles the 402/429 case — if the POST fails, the optimistic row is removed. This is the cleanest pattern; document it in the test.

**Vitest vs Jest.** Next.js 16 ships with Turbopack and integrates better with Vitest. If Jest is already configured, use it; otherwise add Vitest (smaller, faster) — that decision is the BUILD session's call.

**Frontend `AGENTS.md` warning.** The frontend folder has a sticky note: *"This is NOT the Next.js you know"* — directs the builder to read `node_modules/next/dist/docs/` before writing code. The BUILD session should heed it, especially around RSC vs client-component boundaries and the `app/` router conventions in v16. The patterns above (`'use client'` directive, server-side `apiFetch`) match v16 docs as of this writing, but verify before committing.

**Model recommendation for BUILD (RUN 10):** Flash. UI scaffolding is mechanical once the spec is set.

**Model recommendation for INTG (bundled into RUN 10):** Flash is acceptable since this is browser smoke; if Playwright orchestration grows complex, escalate to Sonnet.
