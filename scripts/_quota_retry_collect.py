#!/usr/bin/env python3
"""
scripts/_quota_retry_collect.py

Standalone, collection-ONLY driver for judge_accuracy_audit.py's corpus collection,
built 2026-08-13 to work around an empirically-observed constraint: background
processes in this execution environment get killed at roughly the ~50-60 minute mark
regardless of an in-script retry budget -- a single Python process holding a 9-hour
retry-with-backoff loop (judge_accuracy_audit.py's own _collect_with_retry) cannot be
trusted to survive a multi-hour Google Search grounding quota outage.

This script does ONE bounded attempt per invocation (a short retry budget -- a few
quick tries, then gives up) and exits 0 either way, so an external shell supervisor can
call it every ~60s indefinitely (across many separate short-lived processes) without
ever holding a single process alive for hours. Critically, it does ONLY collection --
it does NOT run embedding/grading/pipeline/report, so repeated retries don't burn real
money re-grading the same pairs over and over (which running the full audit script on
every retry would do, since main() proceeds to grade+pipeline+report even when
collection partially failed).

Usage (called by a shell loop, not directly by a person):
    python scripts/_quota_retry_collect.py

Exits 0 whether or not this attempt fully succeeded -- check the corpus JSON's topic
count against DEFAULT_TOPICS to know if collection is actually complete.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(ROOT, ".env"))
os.environ["EMBED_PROVIDER"] = "gemini"

import judge_accuracy_audit as jaa  # noqa: E402
from truebrief.llm.client import LLMClient  # noqa: E402

CORPUS_PATH = os.path.join(ROOT, "docs", "benchmarks", "_data", "2026-08-12_judge-accuracy-corpus.json")
TOPICS = jaa.DEFAULT_TOPICS


def main() -> int:
    corpus: dict = {}
    if os.path.exists(CORPUS_PATH):
        with open(CORPUS_PATH, "r", encoding="utf-8") as f:
            corpus = json.load(f)

    missing = [t for t in TOPICS if t not in corpus]
    if not missing:
        print(f"[driver] all {len(TOPICS)} topics already collected -- nothing to do.")
        return 0

    print(f"[driver] {len(corpus)}/{len(TOPICS)} collected. Attempting missing: {missing}")
    llm = LLMClient()
    try:
        jaa.collect_corpus(
            TOPICS, llm, sleep_s=2.0, corpus=corpus, save_path=CORPUS_PATH,
            max_wait_hours=0.06,       # ~3.6 min of in-script retry budget per topic call
            retry_initial_wait_s=25.0,
            retry_max_wait_s=50.0,
        )
    except Exception as exc:
        print(f"[driver] this attempt ended without full success (expected during an "
              f"outage -- the shell supervisor will call this again): {exc!r}")
        return 0

    print("[driver] all topics collected successfully in this attempt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
