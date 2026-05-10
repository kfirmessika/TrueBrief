"""
Start Celery Beat Scheduler - scripts/start_beat.py

Starts the Celery Beat process that fires the scheduler heartbeat every 60 seconds.
Run this alongside the API server and the Celery worker.

Terminal layout:
  Terminal 1: uvicorn (API server)        ← already running
  Terminal 2: python scripts/start_worker.py   ← pipeline worker
  Terminal 3: python scripts/start_beat.py     ← this file (scheduler)

What happens after Beat starts:
  - Every 60 seconds, Beat fires check_and_schedule_topics()
  - That function queries Supabase for topics where next_run_at <= now()
  - Due topics get their pipeline queued automatically
  - next_run_at is advanced immediately to prevent double-scheduling

In production (with Redis):
  Beat uses Redis to persist its schedule state.
  In dev (in-memory broker) Beat still works but state resets on restart.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

subprocess.run(
    [
        sys.executable, "-m", "celery",
        "-A", "src.truebrief.tasks.celery_app",
        "beat",
        "--loglevel=info",
        "--scheduler", "celery.beat.PersistentScheduler",
    ],
    cwd=str(ROOT),
    env={
        **__import__("os").environ,
        "PYTHONPATH": str(ROOT),
    }
)
