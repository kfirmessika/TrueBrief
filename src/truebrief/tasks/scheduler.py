"""
Celery Beat Scheduler - tasks/scheduler.py

Periodically checks Supabase for topics that are due for a scan, and enqueues
pipeline tasks for each one.

How it works:
  1. Every 60 seconds, the `check_and_schedule_topics` task fires.
  2. It queries Supabase: active topics WHERE next_run_at <= now()
  3. For each due topic, it:
       a. Immediately updates next_run_at = now() + poll_interval_seconds
          (prevents double-scheduling if the heartbeat fires again quickly)
       b. Enqueues run_pipeline_task.delay(topic_id, raw_query)
  4. The Celery worker picks up the pipeline task and runs it.

This gives us autonomous, per-topic polling without a cron job or external
scheduler service. One Beat process handles all topics.

Start the Beat scheduler (separate terminal, alongside the API server + worker):
  celery -A src.truebrief.tasks.celery_app beat --loglevel=info

Or use the convenience script:
  python scripts/start_beat.py
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from truebrief.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="truebrief.tasks.scheduler.check_and_schedule_topics",
    bind=False,
    ignore_result=True,   # heartbeat results don't need to be stored
)
def check_and_schedule_topics() -> dict:
    """
    Heartbeat task: find due topics and enqueue their pipeline tasks.

    Called every 60 seconds by Celery Beat (registered in celery_app.py).

    Returns:
        dict with keys:
          scheduled: list of topic IDs that were enqueued this tick
          skipped:   number of topics that weren't due yet
    """
    from truebrief.ledger.database import get_supabase
    from truebrief.tasks.pipeline_task import run_pipeline_task

    try:
        db = get_supabase()

        # Query topics that are active AND due for a scan
        # Supabase doesn't have a native "now()" filter client-side,
        # so we use the current UTC time as a string comparison.
        now_iso = datetime.now(timezone.utc).isoformat()

        response = (
            db.table("topics")
            .select("id, raw_query, poll_interval_seconds, next_run_at")
            .eq("is_active", True)
            .lte("next_run_at", now_iso)    # next_run_at <= now
            .not_.is_("next_run_at", "null")  # exclude topics with no next_run_at set
            .limit(50)                       # safety cap: max 50 topics per tick
            .execute()
        )

        due_topics = response.data or []

        if not due_topics:
            logger.debug("Scheduler heartbeat: no topics due for scanning.")
            return {"scheduled": [], "skipped": 0}

        logger.info(f"Scheduler heartbeat: {len(due_topics)} topic(s) due for scanning.")

        scheduled = []
        for topic in due_topics:
            topic_id = topic["id"]
            raw_query = topic["raw_query"]
            interval = topic.get("poll_interval_seconds") or 3600

            # Step 1: Advance next_run_at BEFORE enqueuing (prevents double-schedule)
            _advance_next_run(db, topic_id, interval)

            # Step 2: Enqueue the pipeline task
            task = run_pipeline_task.delay(topic_id=topic_id, raw_query=raw_query)
            scheduled.append(topic_id)
            logger.info(
                f"  Enqueued topic '{raw_query[:50]}' "
                f"(id={topic_id}, task={task.id}, interval={interval}s)"
            )

        return {"scheduled": scheduled, "skipped": 0}

    except Exception as exc:
        logger.error(f"Scheduler heartbeat FAILED: {exc}", exc_info=True)
        return {"scheduled": [], "skipped": -1, "error": str(exc)}


def _advance_next_run(db, topic_id: str, interval_seconds: int) -> None:
    """
    Set next_run_at = now() + interval_seconds AND update last_run_at = now().
    Done BEFORE enqueuing to prevent double-scheduling on overlapping heartbeats.
    """
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    next_run = now + timedelta(seconds=interval_seconds)

    try:
        db.table("topics").update({
            "next_run_at": next_run.isoformat(),
            "last_run_at": now.isoformat(),
        }).eq("id", topic_id).execute()
    except Exception as exc:
        logger.error(f"Failed to advance next_run_at for topic {topic_id}: {exc}")


def set_next_run(topic_id: str, interval_seconds: int | None = None) -> None:
    """
    Public helper: schedule (or re-schedule) a topic for its next run.

    Called from:
      - create_topic API endpoint (schedule first scan immediately)
      - Any code that wants to force a topic to re-scan soon

    Args:
        topic_id:         The topic UUID.
        interval_seconds: Override the topic's configured interval.
                          If None, reads poll_interval_seconds from DB.
    """
    from truebrief.ledger.database import get_supabase
    from datetime import timedelta

    db = get_supabase()
    now = datetime.now(timezone.utc)

    if interval_seconds is None:
        res = (
            db.table("topics")
            .select("poll_interval_seconds")
            .eq("id", topic_id)
            .single()
            .execute()
        )
        interval_seconds = (res.data or {}).get("poll_interval_seconds", 3600)

    next_run = now + timedelta(seconds=interval_seconds)

    db.table("topics").update({
        "next_run_at": next_run.isoformat(),
    }).eq("id", topic_id).execute()

    logger.info(
        f"Scheduled topic {topic_id}: next_run_at={next_run.isoformat()} "
        f"(in {interval_seconds}s)"
    )
