# TrueBrief — Agent Context

## What This Is
A news intelligence SaaS. Backend: Python/FastAPI/Celery. Frontend: Next.js 16 (App Router) + Clerk auth + Paddle billing. DB: Supabase (Postgres + pgvector). Deployed on Railway.

## Current Status
- **Done:** Phases 0–2 complete. Phase 3 mostly complete (3.12 Onboarding is the only gap — page deleted during redesign, needs rebuild). Phase 3.5 A.1 and A.4 done. B.0 and B.1 done.
- **Next candidates:** (1) Rebuild 3.12 Onboarding, (2) A.6 Admin Metrics Dashboard, (3) Fix stale tests (history.test.tsx + onboarding.test.tsx reference deleted routes), (4) B.REF then B.2 once design mockup is ready
- **Full task list & status:** `docs/roadmap.md`

---

## How to Find Things
- **The plan:** `docs/core/architecture_v3.md` — use the **`architecture-v3-map`** skill to jump to a section; never read it in full. **Task list:** `docs/roadmap.md`.
- **Skills** (`.claude/skills/`, auto-load by topic): `truebrief-pipeline`, `truebrief-backend`, `truebrief-frontend`, `truebrief-database`, `accuracy-eval`, `run-truebrief-locally`, `architecture-v3-map`.
- **Subagents** (`.claude/agents/`): `truebrief-backend`, `truebrief-frontend`, `truebrief-db`, `accuracy-evaluator`, `pipeline-debugger`.
- **Commands** (`.claude/commands/`): `/build-step`, `/accuracy-check`, `/eval-pipeline`, `/db-health`, `/finish-step`.
- **Coding conventions:** the matching `truebrief-*` skill (backend / frontend / database).

---

## How We Work (agentic — not one big chat)
- **`/build-step <step>`** is the orchestrator loop: orient (roadmap + `architecture-v3-map`) → plan (approve before coding) → **delegate to the right subagent** (backend / frontend / db) → validate (`pytest` / `tsc` + `build`) → **`/accuracy-check`** if the pipeline changed → `code-reviewer` → report.
- **Accuracy is gated, per stage.** The `accuracy-evaluator` agent + `accuracy-eval` skill run the Gemini-vs-TrueBrief benchmark (`scripts/quality_benchmark.py`) and the per-stage pytest map. A failing golden test or a dropped judge axis **blocks "done"**.
- **`/finish-step`** runs the completion ritual: validate → commit `p{N}-s{X}` → flip roadmap `[ ]`→`[x]` → session summary.
- **Hooks** (`.claude/hooks/`): `git push` is blocked; edited backend Python is syntax-checked. Activate the hooks + the validation permission allowlist per **`.claude/hooks/README.md`** (you apply `settings.json` — the agent is not allowed to grant its own permissions).

---

## Stack & Conventions

### Backend (Python)
- Framework: FastAPI, Celery, Redis
- DB: Supabase via `supabase-py`. All DB calls go through `src/truebrief/ledger/`
- Auth: Clerk JWT verified in `src/truebrief/auth/dependencies.py`
- Billing: Paddle (Stripe is legacy) in `src/truebrief/billing/`
- Config: `config/settings.py` (env via python-dotenv from `.env`)
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
4. **Never read `docs/core/architecture_v3.md` in full** — it's 36KB. Read only the section referenced in the task.
5. **When done:** Run `npm run build` (frontend) or `pytest` (backend) and report the result explicitly.
6. **Circular imports are a death sentence.** If you need to share types between two files, create a third `models.py` / `types.ts`.
7. **Real tests ≠ MSW mocks.** Integration tests must test against the real backend at least once (smoke test).

---

## Model Selection Guide (Refer to docs/roadmap.md)
- **FLASH (C 1–8)**: UI, Boilerplate, Docs, Simple Logic
- **SONNET (C 9–18)**: Complex Logic, Auth, Integrations, Hard Debugging
- **OPUS (C 19–20)**: Architecture, Massive Refactors, Deep Reasoning

**Task Execution Rule:**
1. Start with **`/build-step <step>`** — it reads `docs/roadmap.md` + the relevant `architecture_v3.md` section (via the `architecture-v3-map` skill) and delegates to the right subagent.
2. Build, Test, and Verify — run **`/accuracy-check`** if the pipeline changed.
3. **MANDATORY on completion** — run **`/finish-step`**, which:
   - commits with the `p{N}-s{X}` prefix (never pushes),
   - updates `docs/roadmap.md` (`[ ]` → `[x]`),
   - outputs the Session Summary block.

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
