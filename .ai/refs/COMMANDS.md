# Token-Saving Commands Cheatsheet

## Claude Code (CC) Commands
| Command | When | What It Does |
|---|---|---|
| `/compact` | Session length > 40 messages | Compresses conversation history. **Recommended prompt:** `/compact Focus on code changes and technical decisions made; discard tool output verbosity.` |
| `/clear` | When switching task domains | Hard reset. Drops all context. Use between unrelated tasks. |
| `/context` | At session start | Shows what's eating context. Find and kill bloat. |
| `/effort low` | Simple tasks | Lowers the "thinking budget" to save output tokens. |
| `/config context-mode on` | MCP-heavy work | Dramatically reduces token overhead for tool calls (file system, git, etc). |
| `/model opusplan` | Planning + Build | Uses Opus for the PLAN and Sonnet for the BUILD. Best quality/cost ratio. |
| `Shift+Tab Shift+Tab` | Terminal Shortcut | Enters **Plan Mode** immediately. Catch mistakes before they cost tokens. |
| `npm test -- -t {pattern}` | Testing | Targeted testing. Never run full suites; only run what matches the pattern. |

## Antigravity (AG) Tips
- Use `tree` or `ls` to discover file structure (costs ~50 tokens)
- Never `cat` unknown/large files (costs thousands of tokens)
- Ask the user for file paths instead of searching
- Read `.ai/maps/PROJECT_MAP.md` instead of browsing

## Universal Rules
1. **80% Rule:** If token usage hits 80%, stop. Handoff. New session.
2. **Scout/Sniper:** Use a cheap model (Flash) to find what you need, then use the expensive model to do the work.
3. **Point, don't search:** "Fix JWT in src/auth/validate.js line 42" beats "Fix the auth bug" by 10x in tokens.
4. **Paste functions, not files:** For small edits, paste only the function, not the 1000-line file.
5. **Subagents for Heavy Lifting:** Use subagents for whole-repo scans, log analysis, or multi-file research. It keeps the main session's context clean.
6. **Load-on-Demand (Skills):** Don't read all workflows. Read ONLY the one needed for your current mode.
7. **The Quiet Offender:** Before debugging bloat, use `/context` to find the "quiet offender" (one massive file read early or verbose tool output) and fix that first.
