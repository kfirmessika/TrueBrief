# Token Saver Mode — For Claude & Expensive Models

> You are using limited, paid tokens. Every file read, every exploration, every long explanation costs money. Be surgical.

## Hard Rules

1. **NEVER browse the codebase.** Use `.ai/maps/PROJECT_MAP.md` to find files. If it's not in the map, ask the user.
2. **NEVER read files not listed in the step file.** The step's "Reads" field is your whitelist. 
3. **NEVER read `docs/architecture.md` or `docs/roadmap.md` in full.** If the step says "see architecture §Data Model" — read only that section.
4. **NEVER write essays.** Code first, minimal explanation. The user will ask if they want more.
5. **ONE task per session.** Finish the step → handoff → stop. Don't chain tasks.
6. **Ask, don't search.** If you need a file path or pattern and the maps don't have it, ask the user. It costs them 5 seconds. Searching costs you 5,000 tokens.
7. **Use `tree` or `ls` for discovery, never `cat` on unknown files.** Looking at file names = cheap. Reading file contents = expensive.
8. **Map-First Reading (Surgical Strike):** Do not read entire files to find logic or endpoints. Use `grep` or `search` to find the specific line numbers first, then use `view_file` on ONLY that range. Reading more than 100 lines at once is usually a waste.

## Claude Code Specific
- Run `/compact` after completing each step.
- Run `/clear` when switching between unrelated tasks.
- Run `/context` at session start to see what's eating your context window.
- Watch the token % in the status bar. At 80% → stop, handoff, new session.

## What You Must Do at Session Start
1. Read `.ai/BOOT.md` ✓ (you already did)
2. Read THIS file ✓ (you're reading it)
3. Read `.ai/state/CURRENT_POSITION.md`
4. Read `.ai/state/HANDOFF_STATE.md` (if exists)
5. Read the relevant workflow file
6. **That's it.** Start working. Don't read anything else until the step file tells you to.

## What You Must Do at Session End
1. **NO PAPERWORK:** Do NOT update `docs/roadmap.md`, `docs/core/EXECUTION_PLAN.md`, or `docs/blueprints/`.
2. **THE SUMMARY:** Instead, output a concise **"Update Summary"** for the Secretary Agent (Flash). Include:
    - Task status (e.g., 3.4 PLAN complete).
    - Key findings/gaps for the next session.
    - Files created/modified.
    - Next model recommendation.
3. **UNIFIED METADATA CLOSURE:** Metadata updates (Position, Step Specs) are prohibited during the build. They MUST be performed as a single batch in your final turn before the handoff.
4. **Efficiency Audit:** Briefly flag any action that was token-heavy or wasteful.
