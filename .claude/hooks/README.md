# TrueBrief Claude Code hooks

Two small, surgical hooks. Both **fail open** (never block legitimate work on an internal error) and
are **quiet** — they only emit output when something is actually wrong, so they add no turn-by-turn noise.

| Hook | Event | What it does |
|---|---|---|
| `guard_bash.py` | `PreToolUse(Bash)` | Blocks `git push`, `--no-verify`, `--no-gpg-sign` (exit 2). Enforces "never push / never skip hooks unless the user asks." |
| `py_syntax_check.py` | `PostToolUse(Edit\|Write\|MultiEdit)` | `py_compile`s the just-edited `.py` under `src/`, `scripts/`, `config/`. On a SyntaxError exits 2 so the model fixes it immediately. |

Both were tested by piping sample events:
```bash
echo '{"tool_input":{"command":"git push origin main"}}' | python .claude/hooks/guard_bash.py   # → exit 2, blocked
echo '{"tool_input":{"file_path":"scripts/quality_benchmark.py"}}' | python .claude/hooks/py_syntax_check.py  # → exit 0
```

---

## Activating the hooks + validation permissions (YOU must apply this)

Claude Code has a security guardrail: **an agent cannot edit `.claude/settings.json` to grant itself
permissions or wire hooks.** That's intentional — only you can widen Claude's access. So apply the
block below yourself.

**How:** open `.claude/settings.json` and merge in the `permissions.allow`, `permissions.deny`, and
`hooks` keys below. (Or run the `/update-config` skill and tell it "add these permissions and hooks",
or use `/permissions` in an interactive `claude` terminal.)

```jsonc
{
  "permissions": {
    "allow": [
      // ── validation / test / build (read + run only) ──
      "Bash(pytest:*)",
      "Bash(python -m pytest:*)",
      "Bash(.venv/Scripts/python.exe -m pytest:*)",
      "Bash(python -m py_compile:*)",
      "Bash(.venv/Scripts/python.exe -m py_compile:*)",
      "Bash(python scripts/:*)",
      "Bash(.venv/Scripts/python.exe scripts/:*)",
      "Bash(npm run build:*)",
      "Bash(npm run lint:*)",
      "Bash(npm test:*)",
      "Bash(npm run test:*)",
      "Bash(npx tsc:*)",
      "Bash(npx vitest:*)",
      // ── read-only git ──
      "Bash(git status:*)",
      "Bash(git diff:*)",
      "Bash(git log:*)",
      "Bash(git show:*)",
      "Bash(git branch:*)",
      "Bash(git ls-files:*)",
      "Bash(git tag:*)",
      // ── supabase MCP: read-only inspection only ──
      "mcp__supabase__list_tables",
      "mcp__supabase__list_migrations",
      "mcp__supabase__list_extensions",
      "mcp__supabase__get_advisors",
      "mcp__supabase__get_logs",
      "mcp__supabase__get_project_url",
      // ── context7 docs ──
      "mcp__context7__resolve-library-id",
      "mcp__context7__query-docs"
    ],
    "deny": [
      "Bash(git push:*)"
    ]
  },
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash", "hooks": [ { "type": "command", "command": "python .claude/hooks/guard_bash.py" } ] }
    ],
    "PostToolUse": [
      { "matcher": "Edit|Write|MultiEdit", "hooks": [ { "type": "command", "command": "python .claude/hooks/py_syntax_check.py" } ] }
    ]
  }
}
```

### Notes / deliberate choices
- **"Validation" = read + run, not mutate.** `git commit`/`git add`, `mcp__supabase__execute_sql`, and
  `apply_migration` are **left out on purpose** so they still prompt you — a write to the DB or repo
  should keep a human gate. Add `mcp__supabase__execute_sql` yourself if you want `/db-health` to run
  without a prompt.
- **`.env` rules removed.** Your existing `settings.json` had `Read/Edit(.env)` allow rules; they
  conflict with a global `.env` **deny**, so they're not in this block. Scripts still load `.env`
  directly via `dotenv`, so benchmarks/pipeline runs are unaffected.
- After you save `settings.json`, Claude Code may ask you to review the new hooks once — that's expected.
