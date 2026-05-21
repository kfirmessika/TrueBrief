# HOW TO RUN A STEP — Your Exact Playbook

> Read this once. This replaces EXECUTION_PLAN.md, HANDOFF_STATE.md, mode files, and all the workflow complexity.
> **You manage the project. The AI executes the task.**

---

## 🗺️ The 3 Files You Need Daily

| File | What it's for |
|---|---|
| `docs/roadmap.md` | See what's done, what's next |
| `docs/steps/phase_{N}/STEP_{X}.md` | The task spec for the current step |
| `CLAUDE.md` | Always open in the AI's context |

---

## ▶️ How to Start a Step

### Option A — Flash does it (simple tasks, C≤10)

**When to use:** UI pages, boilerplate, docs, simple endpoints (e.g., 3.10 Brief History, 3.11 Landing Page)

1. Open a new Flash session (Gemini Flash / Claude Haiku)
2. Add `CLAUDE.md` to context (attach/pin the file)
3. Add `docs/steps/phase_{N}/STEP_{X}.md` to context
4. Say: **"Execute this step. Build, test, report."**
5. Flash works. You review the diff.
6. If it looks good → `git add -A && git commit -m "p3-s10: brief history page"`
7. Mark `docs/roadmap.md` → `[x]`

---

### Option B — Sonnet plans, Flash builds (medium tasks, C 11–18)

**When to use:** Multi-file logic, auth flows, complex hooks (e.g., 3.12 Onboarding, 3.15 Email Digest)

**Part 1 — Sonnet writes the spec (you + Sonnet, ~10 min)**
1. Open Sonnet session
2. Add `CLAUDE.md` to context
3. Say: **"Write the step spec for 3.12 Onboarding Flow. Use the template at `.ai/refs/STEP_SPEC_TEMPLATE.md`. Be specific about every file, type, and test target."**
4. Sonnet outputs the spec. You review it, paste into `docs/steps/phase_3/STEP_3.12.md`
5. Close Sonnet session.

**Part 2 — Flash builds from the spec**
1. Open Flash session
2. Add `CLAUDE.md` + `docs/steps/phase_3/STEP_3.12.md` to context
3. Say: **"Execute this step."**
4. Flash builds. You review. Commit.

---

### Option C — You + Sonnet design, then Flash builds (hard tasks, C≥19)

**When to use:** Architecture decisions, Stripe/Billing logic, plugin systems (e.g., 4.6 Usage Billing, 5.4 Contradiction Detection)

1. Open Sonnet thinking session
2. Say: **"I need to design step 4.6 (Usage & Billing). Here's what I know: [describe the problem]. Help me figure out the architecture and write the step spec."**
3. Have a conversation. Decide the approach together.
4. Sonnet writes the spec → save to `docs/steps/phase_4/STEP_4.6.md`
5. Open Flash → build from spec → you review.

---

## 🔍 How to Review Flash's Output

After Flash finishes, check 3 things:

1. **Tests passed?** Flash should report `X/X unit tests passed` and `npm run build: PASS`. If not, tell Flash to fix it before you accept.
2. **Scope respected?** Flash should only have touched files in the spec's "Modify/Create" list. Open the git diff: `git diff --stat`. If Flash touched unexpected files → ask why.
3. **No lazy code?** Search for `TODO`, `placeholder`, `pass`, `...`. If you find any → reject and ask Flash to complete it.

**If Flash breaks something:** Switch to Sonnet. Say: *"Flash built step 3.X and here's the error: [paste error]. Fix it."*

---

## 📝 Spec Writing Tips (for Option B/C)

A good spec is **specific, not long**. The goal is zero ambiguity for Flash.

✅ Good: *"Create `GET /briefs/history` that returns `{brief_id, topic_name, created_at, summary_preview}[]` sorted by `created_at DESC`, scoped to `current_user.id`"*

❌ Bad: *"Add a history endpoint"*

✅ Good: *"Reuse `BriefCard.tsx` from 3.9 — do NOT recreate it"*

❌ Bad: *"Create a card component for briefs"*

---

## 🚨 When Things Go Wrong

| Problem | Fix |
|---|---|
| Flash drifted from spec, added random files | Reject the diff. `git checkout -- .` to reset. Rewrite the spec to be more specific. |
| Flash circular import / missing dependency | Switch to Sonnet to debug. It's faster than iterating with Flash. |
| Flash says "I can't find file X" | Check `CLAUDE.md` has the right path. Update `PROJECT_MAP.md`. |
| Tests fail before you start | Stop. Tell Flash: "Tests fail before any changes: [paste output]. Fix the existing test first." |
| Flash produces placeholder code | Reject. Say: "Do not use placeholder code. Implement it fully or tell me what you're missing." |

---

## 🗂️ File Lifecycle

```
You look at docs/roadmap.md
  → Find next [ ] item
  → Check if docs/steps/phase_{N}/STEP_{X}.md exists
      YES → give it to Flash → Flash builds
      NO  → you + Sonnet write the spec → then Flash builds
  → Review diff
  → Commit
  → Mark [x] in roadmap.md
```

---

## ⏱️ Rough Time Per Step

| Complexity | Spec writing | Build time | Review |
|---|---|---|---|
| Low (C≤5) | 0 min (spec already exists or Flash writes it) | ~15 min | 5 min |
| Medium (C 6–10) | 10 min with Sonnet | ~20 min | 10 min |
| Hard (C 11–18) | 20 min with Sonnet | ~30 min | 15 min |
| Architectural (C≥19) | 30–45 min discussion | ~45 min | 20 min |

---

## ✅ Right Now — Your Next Step

**Step 3.10 — Brief History Page**
- Spec is written: `docs/steps/phase_3/STEP_3.10.md`
- Complexity: Low. Flash can do it alone.

**Do this:**
```
1. Open a Flash session
2. Add to context: CLAUDE.md + docs/steps/phase_3/STEP_3.10.md
3. Say: "Execute this step. Build, test, report."
4. Review output → commit → mark [x] in roadmap.md
```
