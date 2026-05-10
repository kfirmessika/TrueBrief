# STEP SPEC — 3.9: Brief Display Page
> **Status:** [x] PLAN COMPLETE | [x] BUILD | [x] UNIT | [x] INTG
> **Planner:** Claude Sonnet (RUN 11)
> **Date:** 2026-05-11
> **Depends on:** 3.8 (Topic Management UI — done), 3.7 (Auth — done)

---

## 🎯 Objective
Replace the two placeholder pages (`briefs/page.tsx` and `briefs/[briefId]/page.tsx`) with fully functional, data-driven implementations: a **Brief History list** (RSC, fetches `GET /topics/{id}/briefs`) and a **Brief Display page** (RSC shell + client interactive layer, fetches `GET /briefs/{briefId}`).

---

## 📐 Design & Logic

### A. API Contracts (source of truth: `routes.py`)

**`BriefResponse`** (from `GET /briefs/{brief_id}` and list endpoint):
```ts
interface Brief {
  id: string;
  topic_id: string;
  content: string;       // raw Markdown string from intelligence pipeline
  delivered_at: string;  // ISO 8601 UTC string, e.g. "2026-05-11T00:00:00Z"
}
```
- `GET /topics/{topic_id}/briefs` → `Brief[]` (ordered by `delivered_at` desc)
- `GET /briefs/{brief_id}` → `Brief | 404`
- Both endpoints **do NOT require auth** (no `get_current_user` dependency in routes.py — use `apiFetch` for RSC but no token is strictly required).

### B. RSC / Client Split Decision

| File | Type | Why |
|---|---|---|
| `app/topics/[id]/briefs/page.tsx` | RSC (async) | Static list, no interactivity needed |
| `app/topics/[id]/briefs/[briefId]/page.tsx` | RSC shell | Data fetch happens server-side |
| `components/briefs/BriefContent.tsx` | `"use client"` | `react-markdown` is a client-side library |
| `components/briefs/CopyLinkButton.tsx` | `"use client"` | Needs `navigator.clipboard` (browser API) |
| `components/briefs/BriefCard.tsx` | RSC-compatible | Pure presentational, no browser APIs |

**Rule:** Pass all data as props into client components. No client-side fetching in the happy path.

### C. Page: Brief History (`briefs/page.tsx`)

**Data:** `apiFetch(`/topics/${id}/briefs`)` — RSC fetch, no `useEffect`.

**Layout:**
```
← Back to Topic
h1: "Brief History" + meta subtitle
[Empty state if no briefs]
[List of BriefCard items, sorted by delivered_at desc — API already sorts]
```

**`BriefCard` props:**
```ts
{ brief: Brief; topicId: string }
```
Renders: delivery date (formatted), content preview (first 200 chars, no markdown symbols — strip with regex `content.replace(/[#*`_]/g, '')`), link to `/topics/{topicId}/briefs/{brief.id}`.

**Empty state:** When `briefs.length === 0`, show a centered card: "No briefs generated yet. Trigger a scan from the topic page."

**Error handling:** If fetch fails (non-200), use Next.js `notFound()` for 404, `throw new Error(...)` for others (triggers `error.tsx` boundary).

### D. Page: Brief Display (`briefs/[briefId]/page.tsx`)

**Data:** Two parallel RSC fetches:
1. `apiFetch(`/briefs/${briefId}`)` → `brief`
2. `apiFetch(`/topics/${id}`)` → `topic` (for breadcrumb — `topic.raw_query`)

Use `Promise.all([...])` for parallelism.

**Layout (3-column on desktop, single on mobile):**
```
[Sticky Header]
  ← Back to History  |  "Intel Brief"  |  [CopyLinkButton]

[Main content: max-width 65ch, centered]
  Topic: {topic.raw_query}        ← h1
  Delivered: {formatted date}     ← meta
  ─────────────────────────────
  [BriefContent: rendered markdown]

[No sidebar in MVP — deferred to 3.10]
```

**`BriefContent` component (CLIENT):**
```tsx
"use client"
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// Custom renderers to map markdown elements to styled JSX
// h1 → <h2 className="text-2xl font-black text-slate-900 mt-8 mb-3">
// h2 → <h3 className="text-xl font-bold text-slate-800 mt-6 mb-2">
// p  → <p className="text-slate-700 leading-relaxed mb-4">
// ul/ol → styled list with indentation
// a  → <a className="text-indigo-600 underline hover:text-indigo-800">
// strong → <strong className="font-bold text-slate-900">
// hr → <hr className="border-slate-200 my-6">
// blockquote → styled left-border card
// code → inline code with bg-slate-100
```
Props: `{ content: string }` — no state, pure render.

**`CopyLinkButton` component (CLIENT):**
```tsx
"use client"
// onClick: navigator.clipboard.writeText(window.location.href)
// State: idle | copied (2s auto-reset)
// Renders: Share2 icon + text "Copy Link" → "Copied!" with checkmark
```
Props: none (reads from `window.location` on click).

**Not-found handling:** If `GET /briefs/{briefId}` returns 404, call `notFound()` from `next/navigation`.

### E. Design System (match 3.8 language)

- **Colors:** Indigo-600 for CTAs, Slate-900/700/500 for text hierarchy, Slate-100 for code/bg
- **Typography:** `font-black` for display, `font-bold` for section heads, `font-medium` for meta
- **Radius:** `rounded-3xl` for cards, `rounded-xl` for inline elements
- **Spacing:** `max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10` (matches existing pages)
- **Animations:** back-link arrow `group-hover:-translate-x-1 transition-transform` (matches existing pattern)
- **Reading line:** content wrapper `max-w-[65ch] mx-auto` for BriefContent

---

## 📂 File GPS

**Reads:**
- `frontend/src/lib/api.ts` — `apiFetch`, `Brief` type (already exported)
- `frontend/src/app/topics/[id]/page.tsx` — design pattern reference
- `frontend/src/components/topics/TopicCard.tsx` — component structure reference

**Touches (Create):**
- `frontend/src/components/briefs/BriefContent.tsx` (Create)
- `frontend/src/components/briefs/CopyLinkButton.tsx` (Create)
- `frontend/src/components/briefs/BriefCard.tsx` (Create)

**Touches (Modify):**
- `frontend/src/app/topics/[id]/briefs/page.tsx` (Replace placeholder)
- `frontend/src/app/topics/[id]/briefs/[briefId]/page.tsx` (Replace placeholder)
- `frontend/src/lib/api.ts` — **NO CHANGES NEEDED** (`Brief` interface + `briefsApi` already present)

**New test files (Create):**
- `frontend/src/__tests__/briefs.test.tsx` (unit)
- `frontend/src/__tests__/briefs.intg.test.tsx` (integration/MSW)

**Dependencies to install:**
```bash
cd frontend && npm install react-markdown remark-gfm
```
Both are well-maintained, RSC-safe (client-only component wraps them).

---

## 🛠 Execution Steps

1. [ ] Install `react-markdown` and `remark-gfm` (`npm install react-markdown remark-gfm`)
2. [ ] Create `components/briefs/BriefContent.tsx` with full custom renderer map
3. [ ] Create `components/briefs/CopyLinkButton.tsx` with clipboard + state
4. [ ] Create `components/briefs/BriefCard.tsx` (RSC-safe, renders preview + link)
5. [ ] Replace `app/topics/[id]/briefs/page.tsx` with RSC that fetches and renders list
6. [ ] Replace `app/topics/[id]/briefs/[briefId]/page.tsx` with RSC shell + client children
7. [ ] Run unit tests: `npm run test -- --run`
8. [ ] Run integration tests: `npm run test -- --run briefs.intg`

---

## ✅ Testing & Verification

### Unit Tests (Vitest) — Target: 8 test cases
File: `frontend/src/__tests__/briefs.test.tsx`

| # | Component | Test Case |
|---|---|---|
| 1 | `BriefContent` | Renders plain paragraph text |
| 2 | `BriefContent` | Renders `## heading` as styled heading element |
| 3 | `BriefContent` | Renders `**bold**` as `<strong>` |
| 4 | `BriefContent` | Renders `[link](url)` with indigo class |
| 5 | `BriefCard` | Renders delivery date in human-readable format |
| 6 | `BriefCard` | Strips markdown symbols from preview text |
| 7 | `BriefCard` | Has correct `href` linking to `/topics/{topicId}/briefs/{brief.id}` |
| 8 | `CopyLinkButton` | Shows "Copied!" text after click, resets after 2s |

### Integration Tests (MSW) — Target: 3 scenarios
File: `frontend/src/__tests__/briefs.intg.test.tsx`

Use the same MSW server pattern as `topics.intg.test.tsx`.

| # | Scenario | Mock | Assert |
|---|---|---|---|
| 1 | Happy path | `GET /briefs/brief-1` → 200 + fixture | Rendered markdown text appears in DOM |
| 2 | 404 brief | `GET /briefs/missing` → 404 | `notFound()` called OR not-found element shown |
| 3 | Empty history | `GET /topics/topic-1/briefs` → 200 `[]` | Empty-state message visible |

### Smoke Checklist (VERTICAL) — includes 3.8 deferred items
- [ ] Boot full stack (`uvicorn` backend + `npm run dev` frontend)
- [ ] Sign in via Clerk
- [ ] Dashboard loads topic list
- [ ] Click a topic → topic detail page loads
- [ ] Click "View Briefs" → brief history list loads (or shows empty state)
- [ ] If briefs exist: click a brief → display page renders markdown (no raw `#` or `**` symbols)
- [ ] CopyLink button → URL in clipboard, "Copied!" flash shown
- [ ] Mobile (375px): reading column collapses, no horizontal scroll
- [ ] **3.8 Deferred smoke (8 steps):**
  - [ ] POST /topics with free-tier user → 402 if at cap → upgrade banner shown
  - [ ] POST /topics/{id}/scan with free-tier at speed limit → 429 → error toast shown
  - [ ] Clerk sign-out → protected page redirects to /sign-in
  - [ ] Clerk sign-in → redirect back to /dashboard
  - [ ] Topic created → appears in list immediately (optimistic or refetch)
  - [ ] Delete topic → removed from list
  - [ ] Scan triggered → ScanStatusBadge shows PENDING → SUCCESS
  - [ ] Navigate directly to `/topics/bad-id` → not-found page renders

---

## 📝 Planner Notes

1. **`Brief.content` is raw markdown.** The pipeline generates markdown-formatted text. Do NOT escape it before passing to `BriefContent`.
2. **No `delta_score` field exists in `BriefResponse` yet.** The skeleton spec mentioned "Delta Score" — omit this from MVP. Do not invent a field.
3. **`delivered_at` format:** Backend returns ISO 8601 UTC. Use `date-fns` `format(new Date(delivered_at), 'MMMM d, yyyy · h:mm a')` for the display page header. Use `formatDistanceToNow` for list cards.
4. **Auth on brief endpoints:** `GET /briefs/{id}` and `GET /topics/{id}/briefs` have no `get_current_user` dependency in current routes.py. Use `apiFetch` (which will still send the token if present) — this is correct behavior and no backend change is needed.
5. **`react-markdown` version:** Install latest (`^9.x`). It ships ESM-only. Next.js 14+ handles this natively — no transpile config needed.
6. **`remark-gfm` version:** Install `^4.x`. Match the major version to react-markdown v9.
7. **No sidebar in MVP.** The floating ToC was in the skeleton spec — defer to 3.10 (Brief History Page) or a future polish pass. Keep layout simple: single centered column.
8. **Parallel fetch in RSC:** Use `Promise.all` not sequential `await` — this shaves latency off the page render.
9. **Type safety:** Do NOT re-declare `Brief`. Import it from `@/lib/api`. If you need a new type (e.g., `BriefCardProps`), co-locate it in the component file.
10. **Do NOT add** `"use client"` to the page files — they are RSCs. Only the leaf components (`BriefContent`, `CopyLinkButton`) need it.
