# STEP 3.10 — Brief History Page

> **Status:** [ ] Ready to build
> **Complexity:** Low (C=5) — Flash can do this alone in one session.

## 🎯 Goal
Build a `/history` page that shows all past briefs across all of the user's topics, sorted newest-first. Simple, clean list view.

## 📐 What to Build

### Page: `frontend/src/app/history/page.tsx`
- RSC (server component)
- Fetches all briefs for the current user across all topics
- Groups by topic name
- Sorted: newest brief first
- Empty state: "No briefs yet. Add a topic to get started."

### API endpoint needed: `GET /briefs/history`
- Auth: Clerk Bearer token required
- Returns: `{ topic_id, topic_name, brief_id, created_at, summary_preview (first 200 chars) }[]`
- Sorted by `created_at DESC`
- Max 50 results (no pagination needed yet)

### Backend file: `src/truebrief/api/briefs.py`
- Add new route `GET /briefs/history`
- Query: join `briefs` + `topics` where `topics.user_id = current_user.id`
- Return the shape above

### Component: `frontend/src/components/briefs/BriefCard.tsx`
- Already exists from 3.9. Reuse it. Do NOT recreate.

## 📂 Files to Touch
**Read first:**
- `frontend/src/app/topics/[id]/briefs/page.tsx` — pattern to follow for brief listing
- `frontend/src/components/briefs/BriefCard.tsx` — reuse this component
- `src/truebrief/api/topics.py` — pattern for user-scoped queries
- `src/truebrief/auth/dependencies.py` — how to get `current_user`

**Create:**
- `frontend/src/app/history/page.tsx`
- `frontend/src/__tests__/history.test.tsx`

**Modify:**
- `src/truebrief/api/briefs.py` — add the `/history` route
- `frontend/src/app/layout.tsx` or nav — add "History" nav link

## ✅ Done When
1. `GET /briefs/history` returns correct data for authenticated user
2. `/history` page renders the brief list (test with real backend)
3. Unit tests pass: `npm test` (add 3–4 tests for the new page)
4. `npm run build` passes with no errors
5. `pytest tests/` passes with no regressions

## ⚠️ Watch Out
- `BriefCard.tsx` already exists — import it, don't recreate
- The backend route must scope to `current_user.id` — never expose other users' briefs
- Empty state must render gracefully (no briefs = friendly message, not a crash)
