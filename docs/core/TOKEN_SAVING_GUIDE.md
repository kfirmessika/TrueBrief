# 📉 TrueBrief Token Saving Blueprint
> **Objective:** Reduce token waste and prevent context bloat during AI sessions.

---

## 🔥 Highest Impact (Do These First)

### 1. `.claudeignore` — Block the noise
**Impact:** 40–60% context cut.  
Claude reads everything by default. Block `node_modules`, build folders, lock files, and `.git`. Every file not ignored is potential dead weight.

### 2. One Task per Session — Kill dead context
**Impact:** Prevents 2–4x bloat.  
Every message re-sends history. Don't fix 3 bugs in one chat. Start fresh per task. Use `/clear` or a new chat.

### 3. Lean Boot Files — Constant baseline cost
**Impact:** Saves 5,000+ tokens per turn.  
Keep `BOOT.md` under 200 lines. Move heavy details into load-on-demand files.

### 4. `/compact` — Compress history
**Impact:** Saves quality, prevents context rot.  
Use `/compact` with instructions like: *"Focus on code changes and decisions, discard tool output."*

---

## ⚡ Medium Impact (Easy Wins)

### 5. Point at Specific Files
**Impact:** 40–60% reduction in redundant reads.  
Don't say "fix the auth bug." Say "fix the bug in `src/services/auth/auth.service.ts` line 47."

### 6. Truncate Command Output
**Impact:** Eliminates verbose bloat.  
Run targeted commands (e.g., `npm test -- --testPathPattern=auth`) instead of full test suites.

### 7. Lower Thinking Budget
**Impact:** Saves output tokens.  
For simple tasks, use `/effort low` or set `MAX_THINKING_TOKENS=8000`.

### 8. Subagents for Heavy Tasks
**Impact:** Main thread stays clean.  
Use subagents for whole-repo scans or log analysis to keep context isolated.

---

## 🧠 Out-of-the-Box Tricks

### 9. Context-Mode for MCP
**Impact:** Reduces MCP overhead.  
If using tools (file system, git), `context-mode` dramatically reduces token overhead per call.

### 10. `opusplan` Alias
**Impact:** Opus quality at Sonnet cost.  
Uses Opus for planning (judgment) and switches to Sonnet for code generation.

### 11. Plan Mode First
**Impact:** Catch mistakes before they happen.  
Shift+Tab twice to enter Plan mode. Fixing a plan is free; fixing half-executed wrong code is expensive.

### 12. Skills for Specialized Workflows
**Impact:** Load-on-demand, not always-on.  
Put PR review rules or deployment checklists in skills files that only load when invoked.

### 13. [CAVEMAN MODE] Output Stripping
**Impact:** 50–80% reduction in output tokens.  
Force the AI to speak in "Caveman Style" (broken English). 
**Rules:** No "the/a/is", no politeness, no explanations, use symbols (→, =). 
**Trigger:** *"Activate Caveman Mode."*

---

## 📊 Diagnosis
### Check `/context` before debugging
**Tip:** Find the "quiet offender" first—a big file read early or verbose tool output is usually responsible for the majority of waste.