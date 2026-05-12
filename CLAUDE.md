# TrueBrief — Agent Context

## What This Is
A news intelligence SaaS. Backend: Python/FastAPI/Celery. Frontend: Next.js 14 (App Router) + Clerk auth + Stripe billing. DB: Supabase (Postgres + pgvector). Deployed on Railway.

## Current Status
- **Done:** Phases 0–2 complete. Phase 3 steps 3.4–3.9 complete.
- **Next task:** Step 3.12 — Onboarding Flow
- **Full task list & status:** `docs/roadmap.md`

---

## How to Find Things
- **Project file map:** `.ai/maps/PROJECT_MAP.md`
- **Module responsibilities:** `.ai/maps/MODULE_INDEX.md`
- **Current task spec:** `docs/steps/phase_{N}/STEP_{X}.md`
- **Coding conventions:** `.ai/refs/PATTERNS.md`

---

## Stack & Conventions

### Backend (Python)
- Framework: FastAPI, Celery, Redis
- DB: Supabase via `supabase-py`. All DB calls go through `src/truebrief/ledger/`
- Auth: Clerk JWT verified in `src/truebrief/auth/dependencies.py`
- Billing: Stripe in `src/truebrief/billing/`
- Config: `src/truebrief/config/settings.py` (env via python-dotenv from `.env`)
- LLM: All calls go through `src/truebrief/llm/` — never hardcode model names
- Tests: pytest. Run with `pytest tests/` from project root
- Naming: `snake_case` files/vars, `PascalCase` classes, `UPPER_SNAKE_CASE` constants

### Frontend (Next.js)
- Router: App Router (`frontend/src/app/`)
- Auth client: Clerk (`@clerk/nextjs`). Token injected via `useAuth().getToken()`
- API calls: `frontend/src/lib/useApi.ts` (axios with Bearer token)
- State/data: React Query (`@tanstack/react-query`)
- Styling: Tailwind CSS
- Tests: Vitest + MSW for mocks. Run with `npm test` from `frontend/`
- Naming: `PascalCase` components, `camelCase` hooks/utils

### Git Commits
```
p{N}-s{X}: short description of what was built
```

---

## Hard Rules (Never Break)
1. **Never modify files not listed in the task spec's "Touches" section** without flagging it first.
2. **Always run existing tests before writing new code.** If tests fail before you start, stop and report.
3. **Never use placeholder code.** If you don't know a value, ask. Don't write `TODO` and move on.
4. **Never read `docs/core/architecture.md` in full** — it's 36KB. Read only the section referenced in the task.
5. **When done:** Run `npm run build` (frontend) or `pytest` (backend) and report the result explicitly.
6. **Circular imports are a death sentence.** If you need to share types between two files, create a third `models.py` / `types.ts`.
7. **Real tests ≠ MSW mocks.** Integration tests must test against the real backend at least once (smoke test).

---

## Model Selection Guide (Refer to docs/roadmap.md)
- **FLASH (C 1–8)**: UI, Boilerplate, Docs, Simple Logic
- **SONNET (C 9–18)**: Complex Logic, Auth, Integrations, Hard Debugging
- **OPUS (C 19–20)**: Architecture, Massive Refactors, Deep Reasoning

**Task Execution Rule:**
1. Read the `docs/steps/phase_{N}/STEP_{X}.md` spec.
2. Build, Test, and Verify.
3. **MANDATORY**: Upon completion, you MUST:
   - Run a git commit with the `p{N}-s{X}` prefix.
   - Update `docs/roadmap.md` by changing `[ ]` to `[x]` for the task.
   - Output the Session Summary block.

---

## Session End Checklist
When you finish a task, output this summary block:

```
## Session Summary
Task: {Step X.Y — Title}
Status: DONE / PARTIAL / BLOCKED

Files created: [list]
Files modified: [list]

Tests: {Unit: X/X passed | Integration: X/X passed | Build: PASS/FAIL}

Next task: {Step X.Z — Title}
Blockers for next task: {none / describe}
```

Then update `docs/roadmap.md`: change `[ ]` → `[x]` for the completed step.
