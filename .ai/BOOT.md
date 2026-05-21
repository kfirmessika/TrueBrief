# BOOT — Read This First

> This file is a **navigation pointer only**. Read it once, then go do the work.

## Step 1 — Get context
Read `CLAUDE.md` at the project root. It has everything: stack, conventions, hard rules, model guide.

## Step 2 — Find the next task
Read `docs/roadmap.md`. Find the first `[ ]` item. That's your task.

## Step 3 — Read the task spec
Open `docs/steps/phase_{N}/STEP_{X}.md`. This is your complete instruction set.
If the spec file doesn't exist yet → you need to write it first (see below).

## Step 4 — Execute
Build → Test → Report. All in one session if possible.

## Step 5 — Close out
- Output the Session Summary block (format is in `CLAUDE.md`)
- Mark `docs/roadmap.md`: `[ ]` → `[x]`
- Commit: `git add -A && git commit -m "p{N}-s{X}: description"`

---

## If the spec file doesn't exist
You are in PLAN mode. Write `docs/steps/phase_{N}/STEP_{X}.md` using the template at `.ai/refs/STEP_SPEC_TEMPLATE.md`.
Keep it under 60 lines. Every line must be actionable signal. No filler.

## Reference Files (only read when needed)
- `.ai/maps/PROJECT_MAP.md` — where is file X?
- `.ai/maps/MODULE_INDEX.md` — what does module X do?
- `.ai/refs/PATTERNS.md` — coding conventions
- `docs/roadmap.md` — task status tracker
