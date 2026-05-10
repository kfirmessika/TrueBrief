# 🛰️ Technical Spec: Execution Run Planner
> **Objective:** Group project tasks into "Execution Runs" to minimize context re-reading and maximize credit efficiency.

## 📥 Input Data
To build the plan, you must analyze:
1. **`docs/architecture.md`**: To understand data flow and shared services.
2. **`docs/plans/`**: To see the specific files touched by each step.
3. **`docs/roadmap.md`**: For the list of steps.

---

## 🛠 Optimization Constraints

### 1. Model Purity (Hard Constraint)
- All tasks in a single **Run** must use the same **Model**.
- If a task requires OPUS for planning, it cannot be in a Run where the rest of the tasks use Pro.
- FLASH is uniq model that not need to get group cose is cost for us is 0.

### 2. Context Similarity (Primary Goal)
- Group tasks that touch the **same files**.
- *Example:* If tasks 3.6, 3.8, and 3.10 all touch `frontend/src/app/page.tsx`, they favorite to be in the same Run.

### 3. Dependency Logic (Hard Constraint)
- Tasks must be in sequential order. No task in `Run 5` can depend on a task in `Run 6`.

### 4. Complexity Isolation (Safety Rule)
- **Extreme Tasks:** If a task is marked as "Complex" or "Architectural" (e.g., Stripe Integration, Story Node logic), it should be a **Solo Run** or have very few companions. Do not drown complex logic in boilerplate.

### 5. Sequential Chaining Limit (Anti-Hallucination)
- **Constraint:** Do not plan more than 2-3 tasks ahead of the current build progress in a single run.
- **Reason:** Long-range planning without existing code leads to hallucinations. Keep the "Plan -> Build" loop tight.

---

## 📄 Target Output Format
*The Planner should produce a list in this format:*

### RUN [XX] - Model: [Model Name]
**Context:** [Shared File Paths]
**Tasks:**
1. **[Step #] [Action]** (e.g., 3.1 Build)
2. **[Step #] [Action]** (e.g., 3.2 Unit Test)
3. **[Step #] [Action]** (e.g., 3.5 Plan)

**Goal:** [One sentence on what this run achieves]

---

## 🧠 Brain Logic for the Planner
1. **Map** every task to its primary "Touch Files."
2. **Cluster** tasks into "Context Hubs" (Auth, Database, UI, AI).
3. **Sequence** the hubs based on the dependency graph.
4. **Split** clusters into individual "Runs" based on Model assignments.
