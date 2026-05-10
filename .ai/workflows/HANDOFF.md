# HANDOFF Workflow — Session End Protocol

## Do This at the End of Every Session

### 1. Write HANDOFF_STATE.md
Overwrite `.ai/state/HANDOFF_STATE.md` with:

```markdown
# Last Session
**Date:** {date}
**Model:** {your model ID}
**Mode:** {BUILD / PLAN / REVIEW}

## Done
- {What was completed — one line per item}

### 2. Update Checkpoints
- Ensure the relevant Roadmap and Phase Plan checkboxes (`[ ] PLAN`, `[ ] BUILD`, etc.) are updated based on the work done.
- Do NOT mark a phase as done if its sub-checkpoints are not yet finished.

## Current State
- {Key files changed and their state}
- {Anything half-done}

## Next
- **Step:** {N.X} — {title}
- **Model:** {recommended model ID}
- **First action:** {one sentence on what to do first}

## 🛑 MANDATORY: Next Steps for USER
**You must tell the user exactly how to proceed. Copy this format:**
> "I am finished with this session. To save tokens and stay organized, please:
> 1. Run `/clear` to reset the context.
> 2. Switch to model **{Model Name}**.
> 3. Give this command to the new model: 'Read .ai/BOOT.md and start Step {N.X}.'"
```

### 2. Update CURRENT_POSITION.md
Overwrite `.ai/state/CURRENT_POSITION.md`:
```
Phase: {N}
Step: {N.X} — {title}
Mode: {BUILD / PLAN / REVIEW}
```

### 3. Commit
```
git add -A
git commit -m "handoff: end of session p{N}-s{X}"
```
