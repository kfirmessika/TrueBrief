#!/usr/bin/env python3
"""PreToolUse(Bash) guard — blocks a few never-without-asking git operations.

Enforces the project rule "never push unless the user explicitly asks" and the
harness rule "never skip hooks / signing". Fails OPEN (exit 0) on any parse error
so a malformed event never blocks legitimate work. Only speaks when it blocks.
"""
import sys
import json
import re

BLOCKED = [
    # (regex on the command, message shown to the model on stderr)
    (r"\bgit\s+(?:-\S+\s+|--\S+\s+|-C\s+\S+\s+)*push\b",
     "BLOCKED: `git push` is not allowed. TrueBrief never pushes unless the user "
     "explicitly asks. If they asked, let them run it, or ask them to confirm first."),
    (r"--no-verify\b",
     "BLOCKED: `--no-verify` (skipping hooks) is not allowed unless the user explicitly asked."),
    (r"--no-gpg-sign\b",
     "BLOCKED: `--no-gpg-sign` (bypassing signing) is not allowed unless the user explicitly asked."),
]


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0  # fail open
    command = (data.get("tool_input") or {}).get("command", "") or ""
    for pattern, message in BLOCKED:
        if re.search(pattern, command):
            print(message, file=sys.stderr)
            return 2  # exit 2 → block the tool call, feed stderr back to the model
    return 0


if __name__ == "__main__":
    sys.exit(main())
