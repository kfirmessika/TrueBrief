# BUILD Workflow

## Prerequisites
You've already read BOOT.md and your mode file. You know the current position.

## Steps

### 1. Read the Step Spec
Open `docs/steps/phase_{N}/STEP_{X}_SPEC.md`. This is your "Recipe" for the session. 
If it doesn't exist, you MUST follow the **PLAN** workflow first.

### 2. Read ONLY Whitelisted Files
Open ONLY the files listed in the "Reads" field of the Spec or Plan. 
**In TOKEN_SAVER mode:** If you need another file, ASK the user. Do not browse.

### 3. Build
Write the code specified in the step. Only the listed files. Nothing extra.

### 4. Test
- Run existing tests first → must pass before new code
### 4. Final Summary (Secretary Handoff)
Do NOT update `docs/roadmap.md` or `docs/core/EXECUTION_PLAN.md`. Instead, output a concise summary of your progress (tests passed, files changed) for the Secretary Agent (Flash) to update the project state.

### 5. Handoff
Follow `.ai/workflows/HANDOFF.md`.

### 6. Commit
```
git add -A
git commit -m "p{N}-s{X}: {what was done}"
```
