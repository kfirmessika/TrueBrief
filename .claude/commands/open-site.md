---
description: Start the frontend dev server (if not already running) and give the localhost link to open TrueBrief on your PC.
argument-hint: (none)
---

Start the frontend dev server via `preview_start` with `{name: "frontend"}` (config: `.claude/launch.json`, port 3000; reuses the server if already running).

Once started, tell the user the exact URL to open in their own browser: `http://localhost:3000`. Do not navigate the Browser pane for them — this command is for opening the site in the user's own browser window, not for Claude to preview it.
