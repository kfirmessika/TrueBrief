# BOOT — Read This First. Nothing Else.

## 🏁 Rule 0: Cost Control & Navigation (MANDATORY)
1. **Surgical Reading:** Read ONLY the specific section for your current step in `docs/blueprints/phase_{N}.md`.
4. **Handoff:** Follow `.ai/workflows/HANDOFF.md` at the end of EVERY session.
5. **Professional Communication:** Always communicate in professional English. Use **[CAVEMAN MODE]** only if explicitly triggered. (See `.ai/refs/CAVEMAN_ISTRACTIONS.md` for rules).
6. **No Placeholders:** Never use placeholders. Write working code.

## Step 1: Know Your Mode
- **You are Claude, Sonnet, Opus, Gemini Pro,or any PAID model?** → Read `.ai/modes/TOKEN_SAVER.md` and follow it strictly.
- **You are Gemini Flash or any FREE model?** → Read `.ai/modes/FULL_POWER.md`.
- **Not sure?** → Default to TOKEN_SAVER.

## Step 2: Know Where You Are
Read `.ai/state/CURRENT_POSITION.md` (1-3 lines). This tells you the phase, step, and mode.

## Step 2.5: Know the Plan
Read `docs/core/EXECUTION_PLAN.md`. This is the surgical, model-aware roadmap. You are forbidden from deviating from this sequence or planning beyond its horizon.

## Step 3: Know What Happened Last
Read `.ai/state/HANDOFF_STATE.md` if it exists. Skip if it doesn't (first session).

## Step 4: Know Your Execution Pattern
Before opening any workflow file, check your task complexity vs. the patterns in `.ai/refs/MODEL_ROUTER.md §Complexity-Based Execution Patterns`:
- **C ≤ 5** → ATOMIC: Flash does everything in 1 run. Do NOT split into 4 runs.
- **C 6–10** → SPEC+SHIP: Sonnet plans, Flash ships BUILD+UNIT+INTG together.
- **C 11–18** → GUIDED BUILD: Sonnet plans, Flash builds, Sonnet owns INTG.
- **C ≥ 19** → FULL CYCLE: Opus plans, Sonnet validates, Flash builds, Sonnet verifies.

## Step 5: Do the Work
Based on the task, read ONE workflow file:
- **Building code** → `.ai/workflows/BUILD.md`
- **Planning a phase** → `.ai/workflows/PLAN.md`
- **Reviewing code** → `.ai/workflows/REVIEW.md`

## Step 6: Find Files
**NEVER browse the codebase.** Use these maps:
- **Where is file X?** → `.ai/maps/PROJECT_MAP.md`
- **What is the current Step Spec?** → `docs/steps/phase_{N}/STEP_{X}_SPEC.md`
- **What does module X do?** → `.ai/maps/MODULE_INDEX.md`

## Step 7: End of Session
Write `.ai/state/HANDOFF_STATE.md` → follow `.ai/workflows/HANDOFF.md`.

---

## Reference Files (read ONLY when needed)
- `.ai/refs/MODEL_ROUTER.md` — Which model for which task (PLAN mode only)
- `.ai/refs/PATTERNS.md` — Coding conventions (BUILD mode only, if unsure)
- `.ai/refs/COMMANDS.md` — Token-saving commands cheatsheet
- `.ai/refs/CAVEMAN_ISTRACTIONS.md` — Rules for Professional vs Caveman Style
- `.ai/refs/EXECUTION_PLANNER_SPEC.md` — The V2 Vertical Chaining & Flash Focus laws.

## DO NOT READ
- `docs/core/architecture.md` — 36KB. Read ONLY the section referenced in your step file.
- `docs/roadmap.md` — Use CURRENT_POSITION.md instead.
- Any file not listed in your step's "Reads" field.
