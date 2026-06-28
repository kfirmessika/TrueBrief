---
description: Orchestrate one roadmap step / task end-to-end — plan, delegate to the right specialist subagents, validate, accuracy-check, review, and report. The main agentic loop.
argument-hint: <roadmap step id or task description, e.g. "p3-s12 onboarding flow">
---

You are the **orchestrator** for TrueBrief. Drive this task to done by coordinating specialist subagents — do **not** try to implement everything yourself in one context.

**Task:** $ARGUMENTS

Run this loop:

1. **ORIENT.** Read `docs/roadmap.md` to locate the step. Use the `architecture-v3-map` skill to find the relevant `architecture_v3.md` section and read **only that slice** (never the whole 36KB file). Restate the goal + acceptance criteria in one short paragraph.
2. **PLAN.** Decide which layer(s) this touches: backend, frontend, database, and/or pipeline. For anything bigger than a one-line fix, write a short plan and get the user's approval **before** editing code (project workflow).
3. **DELEGATE** to the right subagent(s) — give each the goal, the exact files, and the acceptance criteria. Launch independent agents in parallel:
   - backend (`src/truebrief/**`, FastAPI, Celery, pipeline) → **truebrief-backend** agent
   - frontend (`frontend/**`) → **truebrief-frontend** agent
   - schema / migration / data → **truebrief-db** agent
4. **VALIDATE.** Backend: `.venv/Scripts/python.exe -m pytest tests/`. Frontend: `npx tsc --noEmit --skipLibCheck` + `npm run build`. Stop and fix on any red — do not proceed on a broken baseline.
5. **ACCURACY (if the pipeline was touched).** Dispatch the **accuracy-evaluator** agent (it uses the `accuracy-eval` skill). A failing golden test or a dropped judge axis vs the last `docs/benchmarks/` report is a **blocker**, not a warning. If it regressed and the cause isn't obvious, dispatch **pipeline-debugger**.
6. **REVIEW.** Run the **code-reviewer** agent on the diff. Resolve correctness/security findings before declaring done.
7. **REPORT.** Summarize what changed, the test + accuracy results, and any follow-ups. Then offer to run **`/finish-step`** to commit (`p{N}-s{X}`), flip the roadmap, and emit the session summary.

**Guardrails:** smallest change that works; one logical change at a time; never modify files outside the task's scope without flagging first; never `git push`.
