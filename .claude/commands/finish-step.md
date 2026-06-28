---
description: The TrueBrief completion ritual — validate, review the diff, commit with the p{N}-s{X} prefix, flip the roadmap to done, and emit the Session Summary. Never pushes.
argument-hint: <p{N}-s{X} + short description, e.g. "p3-s12 onboarding flow">
---

Run the mandatory completion ritual for: **$ARGUMENTS**

1. **VALIDATE.** Backend: `.venv/Scripts/python.exe -m pytest tests/`. If the frontend changed: `npm run build` (from `frontend/`). Report PASS/FAIL explicitly. **Do not proceed on red** — fix first.
2. **REVIEW THE DIFF.** `git diff --stat` then scan the diff: confirm only intended files changed, and grep for leftover `TODO` / `placeholder` / bare `pass` / `...`. If scope drifted, stop and flag it.
3. **COMMIT (never push).** Stage and commit with the project prefix:
   `p{N}-s{X}: <what was built>` (for a numbered roadmap step), or a Conventional Commit `feat|fix|chore(scope): …` otherwise. End the message with the `Co-Authored-By` trailer.
4. **ROADMAP.** In `docs/roadmap.md`, flip this step's `[ ]` → `[x]` (use `[~]` if only partial).
5. **SESSION SUMMARY.** Emit:
```
## Session Summary
Task: {Step — Title}
Status: DONE / PARTIAL / BLOCKED
Files created: [...]
Files modified: [...]
Tests: {Unit: X/X | Build: PASS/FAIL | Accuracy: pass/regressed/n-a}
Next task: {from roadmap.md}
Blockers for next task: {none / describe}
```

If a pipeline stage changed and `/accuracy-check` hasn't run yet, run it before committing.
