#!/usr/bin/env python3
"""PostToolUse(Edit|Write|MultiEdit) — fast syntax check on edited backend Python.

Compiles the just-edited .py file (only under src/, scripts/, or config/). On a
SyntaxError it exits 2 so the error is fed straight back to the model to fix
immediately. Silent on success and on any non-syntax problem (fails open).
"""
import sys
import json
import os
import py_compile


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    tool_input = data.get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not path.endswith(".py"):
        return 0

    norm = path.replace("\\", "/")
    if not any(seg in norm for seg in ("/src/", "/scripts/", "/config/")):
        return 0
    if not os.path.isfile(path):
        return 0

    try:
        py_compile.compile(path, doraise=True)
    except py_compile.PyCompileError as exc:
        print(f"[py_syntax_check] Syntax error in {path}:\n{exc}", file=sys.stderr)
        return 2
    except Exception:
        return 0  # non-syntax issue — not our job, fail open
    return 0


if __name__ == "__main__":
    sys.exit(main())
