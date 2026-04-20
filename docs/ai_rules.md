# TrueBrief — AI Session Rules & Workflow

> **⚡ MANDATORY FIRST READ.** Every AI session starts here before touching any code or plans.  
> This file defines how we work, who does what, and the document flow.

---

## 📋 The 3-Document System (Read in This Order)

Every session, BEFORE working, read these three documents in order:

```
1. 📍 roadmap.md          → WHERE we are (current sprint, task status, what's done / in progress / next)
2. 📐 implementation_plan.md → HOW to build it (step-by-step tasks, code specs, ADRs, v1 reuse map)
3. 🏛️ architecture.md      → WHY it works this way (full theoretical picture, design decisions)
```

**Rule:** Never start coding without reading all three. They must stay in sync.  
**Rule:** If a change affects any plan, STOP — update all affected docs before moving to the next task.  
**Rule:** When roadmap status changes, check if implementation_plan.md and architecture.md need updates too.

---

## 🧑‍💼 Roles & Jobs

| Role | Who | Responsibilities |
|------|-----|-----------------|
| **Developer** | You (the user) | Review code, make decisions, approve plans, test on your machine, git commit |
| **Builder** | AI | Write code, spec files BEFORE touching them, implement roadmap tasks |
| **Tester** | AI + You | Verify acceptance criteria, run tests, confirm working before moving on |
| **Architect** | AI | Keep all 3 documents in sync, flag conflicts, propose ADRs for big decisions |
| **Planner** | AI | Update roadmap status, break tasks into subtasks, keep plans versioned |

---

## ⚙️ The Work Loop (For Every Task)

```
1. READ    → Read all 3 docs. Know where we are.
2. PLAN    → State exactly what we're building this session. Confirm with user.
3. SPEC    → List exact files to change BEFORE writing any code.
4. BUILD   → Write the code. One feature at a time.
5. TEST    → Run it. Verify acceptance criteria pass.
6. UPDATE  → Update roadmap.md status (and implementation_plan.md / architecture.md if changed).
7. COMMIT  → User commits to git with clean message.
8. NEXT    → Pick next task from roadmap.
```

---

## 📏 Ground Rules

| Rule | Detail |
|------|--------|
| **Never guess** | If unclear: ask the user. Don't assume architecture, business logic, or intent. |
| **Reuse v1 first** | Before writing new code, check the V1 Reuse Map in implementation_plan.md. |
| **One task per session** | Stay focused. One roadmap item per session. |
| **Test before moving on** | No skipping. Acceptance criteria must pass before marking `[x]`. |
| **Git commit after every working feature** | Small clean commits. Not one giant "add everything". |
| **Sync all docs on change** | Changing a design decision? Update architecture.md AND implementation_plan.md AND roadmap.md. |
| **Roadmap is the source of truth for current status** | implementation_plan.md is HOW; roadmap.md is WHERE. |
| **Never break what works** | If refactoring: run existing tests first, confirm green, then refactor. |

---

## 🗂️ Plan Update Protocol

When making changes that affect the plans:

1. **Small task complete** → Update `roadmap.md` status (`[ ]` → `[x]`). Done.
2. **Design change** → Update `architecture.md` first (theory), then `implementation_plan.md` (steps), then `roadmap.md` (status). In that order.
3. **New task discovered** → Add to `roadmap.md` under the correct phase/sprint. If it needs detail, add a step to `implementation_plan.md`.
4. **Scope change** → STOP. Tell the user. Agree on the change. Update all 3 docs together before continuing.

> ⚠️ **Never update just one doc.** If the theory changes, the plan changes. If the plan changes, the roadmap changes. Always check all three.

---

## 🚀 How to Start a Session

Say something like:
> *"Let's work on Phase 1, Step 1.2 — the RSS Layer."*

The AI will:
1. Read `roadmap.md` → find current status, confirm task
2. Read `implementation_plan.md` → find the step spec, v1 reuse map, acceptance criteria
3. Read `architecture.md` → confirm architectural fit
4. Propose a spec (exact files to change)
5. Wait for your "go" before writing any code

---

## 📁 Document Index

| File | Purpose |
|------|---------|
| `docs/ai_rules.md` | **This file.** Rules, roles, workflow. Read first every session. |
| `docs/roadmap.md` | Sprint map. Task list with statuses. Where we are right now. |
| `docs/implementation_plan.md` | Tactical build plan. Step-by-step specs, ADRs, code blueprints, v1 reuse map. |
| `docs/architecture.md` | Full system design. Theory, data models, algorithms, business logic. |
| `config/settings.py` | Central config. LLM config, env vars, all settings. |
| `config/routing_rules.yaml` | Source routing rules (which plugins fire for which topics). |
| `config/rss_feeds.yaml` | Curated RSS feed database by category. |
