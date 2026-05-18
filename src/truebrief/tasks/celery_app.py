"""
Celery App - tasks/celery_app.py

Central Celery application configuration.

Development (no Redis installed):
  Uses fakeredis as both broker and result backend.
  Zero infrastructure needed - everything runs in the same process.

Production (Redis running):
  Set REDIS_URL in .env → real Redis used automatically.

Start the worker:
  celery -A src.truebrief.tasks.celery_app worker --loglevel=info -P solo

Start the Beat scheduler (Phase 2.5):
  celery -A src.truebrief.tasks.celery_app beat --loglevel=info
"""

from __future__ import annotations

import logging
import os

from celery import Celery

logger = logging.getLogger(__name__)

# ── Redis / Broker URL ────────────────────────────────────────────────────────
# In production: set REDIS_URL=redis://localhost:6379/0 in .env
# In development (no Redis): REDIS_URL is unset → fakeredis is used
_REDIS_URL: str = os.getenv("REDIS_URL", "")

if _REDIS_URL:
    _BROKER_URL = _REDIS_URL
    _BACKEND_URL = _REDIS_URL
    logger.info(f"Celery: using real Redis at {_REDIS_URL}")
else:
    # fakeredis transport - no Redis installation needed for dev
    _BROKER_URL = "memory://"
    _BACKEND_URL = "cache+memory://"
    logger.info("Celery: no REDIS_URL set - using in-memory broker (dev mode)")


# ── App ───────────────────────────────────────────────────────────────────────
celery_app = Celery(
    "truebrief",
    broker=_BROKER_URL,
    backend=_BACKEND_URL,
    include=[
        "truebrief.tasks.pipeline_task",
        "truebrief.tasks.scheduler",
        "truebrief.tasks.digest_task",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=3600,           # Task results kept for 1 hour
    task_track_started=True,       # Enables STARTED state (shows "in progress")
    worker_prefetch_multiplier=1,  # Process one task at a time (pipeline is heavy)
    task_acks_late=True,           # Acknowledge AFTER task completes (safer on crash)
)

# ── Celery Beat Schedule ──────────────────────────────────────────────────────
# Beat fires check_and_schedule_topics every 60 seconds.
# That function queries Supabase for due topics and enqueues pipeline tasks.
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    "scheduler-heartbeat": {
        "task": "truebrief.tasks.scheduler.check_and_schedule_topics",
        "schedule": 60.0,   # every 60 seconds
        "options": {"queue": "celery"},
    },
    "daily-digest": {
        "task": "truebrief.tasks.digest_task.send_digest_task",
        "schedule": crontab(hour=8, minute=0),  # every day at 08:00 UTC
        "options": {"queue": "celery"},
    },
}
celery_app.conf.timezone = "UTC"
