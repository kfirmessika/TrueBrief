# PLAN Workflow

## When to Use
Planning a new phase — writing step files and assigning models. No code.

## Steps

### 1. Read Model Router
Open `.ai/refs/MODEL_ROUTER.md` → understand which models fit which tasks.

### 2. Read Roadmap
Open `docs/roadmap.md` → find the next unplanned phase.  
(In FULL_POWER mode: read the whole thing. In TOKEN_SAVER: read just the phase header.)

### 3. Read Architecture (section only)
Open `docs/core/architecture.md` → read ONLY sections relevant to this phase.

### 4. Write Step Definition & Spec
For each step in the phase, ensure it exists in the blueprint file (`docs/blueprints/phase_{N}.md`) with:
```markdown
## Step N.X — Title
**Model:** {model ID}
**Reads:** {files to read}
**Touches:** {files to create/edit}
```

### 5. Create the Execution Spec
BEFORE handing off to a BUILDER, the PLANNER must create a **Step Spec** file.
1. **Load Template:** Read `.ai/refs/STEP_SPEC_TEMPLATE.md`.
2. **Populate:** Fill in all fields based on the phase plan and current architecture.
3. **Save to Home:** Save the file as `docs/steps/phase_{N}/STEP_{X}_SPEC.md` (e.g., `docs/steps/phase_3/STEP_3.4_SPEC.md`).
4. **Link:** Mention the file path in your final response.

### 6. Final Summary (Secretary Handoff)
Do NOT update `docs/roadmap.md` or `docs/core/EXECUTION_PLAN.md`. Instead, output a concise summary of the plan you created for the Secretary Agent (Flash) to update the project state.

### 7. Handoff
Follow `.ai/workflows/HANDOFF.md`.
