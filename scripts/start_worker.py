"""
Start Celery Worker - scripts/start_worker.py

Starts the TrueBrief Celery background task worker.

Usage:
  # From project root (with .venv activated):
  python scripts/start_worker.py

  # Or directly via Celery CLI:
  celery -A src.truebrief.tasks.celery_app worker --loglevel=info -P solo

Notes:
  - Use -P solo on Windows (Windows doesn't support Celery's default fork model)
  - In production with Redis: set REDIS_URL in .env first
  - In development (no Redis): works out of the box with in-memory broker
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

subprocess.run(
    [
        sys.executable, "-m", "celery",
        "-A", "src.truebrief.tasks.celery_app",
        "worker",
        "--loglevel=info",
        "-P", "solo",          # Required on Windows
        "--concurrency=1",     # One pipeline at a time (they're heavy)
    ],
    cwd=str(ROOT),
    env={
        **__import__("os").environ,
        "PYTHONPATH": str(ROOT),
    }
)
