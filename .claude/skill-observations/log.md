# Skill Observation Log

Observations captured during task-oriented work.

**Status key:** OPEN = not yet actioned | ACTIONED (YYYY-MM-DD) = skill updated/created | DECLINED (YYYY-MM-DD) = user decided not to pursue — resolved statuses always carry their resolution date

---

### Observation 1: dev-server skill is documentation-only, not executable

**Status:** OPEN
**Date:** 2026-07-28
**Session context:** User requested dev-server start/stop wrapping. Created `.claude/skills/dev-server.md` documenting the PowerShell scripts.
**Skill:** dev-server (new)
**Type:** internal
**Phase/Area:** TrueBrief local development workflow

**Issue:** Created skill file documents start-local.ps1 / stop-local.ps1 commands but doesn't provide an executable workflow. User still types the full PowerShell commands. Skill is reference-only, not actionable.

**Suggested improvement:** Wrap with a `.claude/commands/dev-server.md` command that provides `/dev-server start`, `/dev-server stop`, `/dev-server restart` for quicker invocation. Or convert skill to invoke via Bash tool with cleaner UX.

**Principle:** A documented workflow is incomplete if it still requires full manual command entry. Wrapper commands reduce friction for repeated tasks.

---

### Observation 2: start-local.ps1 leaves orphaned child processes

**Status:** OPEN
**Date:** 2026-07-28
**Session context:** Stopped server multiple times; final close required force-killing node/python/redis processes that should have been cleaned up by stop-local.ps1.
**Skill:** run-truebrief-locally
**Type:** internal
**Phase/Area:** Process cleanup in start/stop scripts

**Issue:** `stop-local.ps1` killed top-level FastAPI/Next.js processes but didn't fully reap child workers. Tasklist still showed 20+ node processes + python + redis after "all services stopped". Required `Stop-Process -Force` in PowerShell to fully clean up.

**Suggested improvement:** Update `scripts/stop-local.ps1` to iterate child processes (e.g., via Get-ChildItem \\.\pipe\\ or tasklist /v) and wait for children to terminate before exiting. Or add a hard kill step after graceful shutdown with a 5s timeout.

**Principle:** Shutdown scripts that leave orphaned children cause confusion ("why is port 8000 still bound?") and cascading force-kills. Process cleanup must be verifiable.

---

### Observation 3: Caveman mode working as designed

**Status:** ACTIONED (2026-07-28) — session applied mode without issue
**Date:** 2026-07-28
**Session context:** User activated caveman mode; responded to 11 tool calls throughout session with terse, fragment-based language.
**Skill:** caveman (global mode)
**Type:** internal
**Phase/Area:** Interaction style

**Issue:** None. Mode worked exactly as specified — dropped articles/filler, preserved code/commits/security-sensitive output at normal length, responded quickly to repeated start/stop requests.

**Suggested improvement:** None for caveman itself. Observation logs that caveman mode is transparent and reduces unnecessary fluff effectively.

**Principle:** Caveman mode successfully compresses conversational overhead without sacrificing clarity on technical content.
