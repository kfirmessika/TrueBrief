#!/usr/bin/env python3
"""
scripts/_integrity_redteam_pipeline.py

One command, zero LLM tokens beyond reading the final output. Chains:
    _integrity_redteam_run.py     (hits the real Arbiter + Gemini API — the only
                                    part that has to happen live; ~131 cheap calls)
    _integrity_redteam_grade.py   (pure Python math over the results JSON)
    _integrity_redteam_report.py  (pure Python formatting, reuses each case's
                                    pre-written attack rationale — no LLM writing)

Run this after any change to the arbiter/judge cascade to re-validate against
the same 131 adversarial cases. Then read ONLY the final .md file — the run
and grade steps need no AI attention at all, and the report step needs none
either since it's deterministic.

Usage:
    python scripts/_integrity_redteam_pipeline.py
"""

from __future__ import annotations

import subprocess
import sys
import os
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "docs", "benchmarks", "_data")
REPORT_DIR = os.path.join(ROOT, "docs", "benchmarks")


def main():
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    results_path = os.path.join(DATA_DIR, f"{ts}_arbiter-redteam-results.json")
    grading_path = os.path.join(DATA_DIR, f"{ts}_arbiter-redteam-grading.json")
    report_path = os.path.join(REPORT_DIR, f"{ts}_arbiter-redteam-audit.md")

    steps = [
        (os.path.join(HERE, "_integrity_redteam_run.py"), [results_path]),
        (os.path.join(HERE, "_integrity_redteam_grade.py"), [results_path]),
        (os.path.join(HERE, "_integrity_redteam_report.py"), [grading_path, report_path]),
    ]

    for step, args in steps:
        print(f"\n{'=' * 80}\nRunning: {os.path.basename(step)} {' '.join(args)}\n{'=' * 80}")
        result = subprocess.run([sys.executable, step] + args, cwd=ROOT)
        if result.returncode != 0:
            print(f"\nFAILED at {os.path.basename(step)} (exit {result.returncode}) — stopping pipeline.")
            sys.exit(result.returncode)

    print(f"\n{'=' * 80}\nPipeline complete. Read only:\n  {report_path}\n{'=' * 80}")


if __name__ == "__main__":
    main()
