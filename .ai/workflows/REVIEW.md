# REVIEW Workflow

## When to Use
After a phase is complete — validating code quality, test coverage, and doc accuracy.

## Steps

### 1. Check Completion
Verify all steps in the phase are marked `[x]` in `docs/roadmap.md`.

### 2. Review Code
For each step's "Touches" files:
- Does the code match the architecture design?
- Any hardcoded values that should be configurable?
- Any leftover TODOs, debug prints, or commented-out code?
- Security issues?

### 3. Review Tests
- Are all modules tested?
- Any obvious edge cases missing?
- Run full test suite: `python -m pytest tests/ -v`

### 4. Review Maps
- Is `.ai/maps/PROJECT_MAP.md` current?
- Is `.ai/maps/MODULE_INDEX.md` current?
- Any new modules missing from the index?

### 5. Fix Issues
Fix → test → commit per issue: `git commit -m "review-p{N}: {what}"`

### 6. Mark Phase Complete
Update `docs/roadmap.md` — mark phase complete.
Update `.ai/state/CURRENT_POSITION.md` → next phase.

### 7. Handoff
Follow `.ai/workflows/HANDOFF.md`.
