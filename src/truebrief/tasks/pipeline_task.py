"""
Pipeline Task - tasks/pipeline_task.py

The Celery background task that runs the full intelligence pipeline.
Called by the scan endpoint instead of running the pipeline synchronously.

State transitions:
  PENDING  → task queued, not started yet
  STARTED  → worker picked it up and is running
  SUCCESS  → pipeline completed, result = brief content string
  FAILURE  → pipeline crashed, result = error message

Usage from Python:
  from truebrief.tasks.pipeline_task import run_pipeline_task
  task = run_pipeline_task.delay(topic_id="uuid", raw_query="TSMC chips")
  task.id  # use this to poll /scan-status/{task_id}
"""

from __future__ import annotations

import logging

from truebrief.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="truebrief.pipeline",
    bind=True,               # gives access to self (the task instance)
    max_retries=0,           # pipeline errors should surface, not silently retry
    soft_time_limit=600,     # 10 min soft limit - logs warning
    time_limit=660,          # 11 min hard limit - kills worker gracefully
)
def run_pipeline_task(self, topic_id: str, raw_query: str) -> dict:
    """
    Run the full TrueBrief intelligence pipeline in the background.

    Args:
        topic_id:  The topic UUID from Supabase.
        raw_query: The user's original search query text.

    Returns:
        dict with keys:
          status:   "success" | "no_update" | "rejected" | "error"
          content:  Brief text (on success) or reason string
          brief_id: Supabase brief ID (on success, if saved)
    """
    logger.info(f"[TASK] Starting pipeline: topic_id={topic_id} query='{raw_query}'")

    try:
        from truebrief.pipeline.runner import PipelineRunner
        from truebrief.ledger.database import get_supabase

        runner = PipelineRunner()
        brief_content = runner.run(raw_query, topic_id=topic_id)

        # Detect no-update / rejection from the brief text
        if not brief_content or brief_content.strip() == "":
            logger.info(f"[TASK] Empty brief returned for topic {topic_id}")
            return {"status": "no_update", "content": "No new information found."}

        if brief_content.startswith("Topic rejected:"):
            logger.info(f"[TASK] Topic rejected: {brief_content}")
            return {"status": "rejected", "content": brief_content}

        # Save brief to Supabase
        brief_id = _save_brief(topic_id, brief_content)

        # Recalibrate poll interval based on observed Alpha Yield Rate (fire-and-forget)
        try:
            from truebrief.ledger.ayr_engine import update_topic_interval
            update_topic_interval(topic_id)
        except Exception as ayr_err:
            logger.warning(f"[TASK] AYR recalibration skipped: {ayr_err}")

        logger.info(f"[TASK] Pipeline SUCCESS for topic {topic_id}. Brief ID: {brief_id}")
        return {
            "status": "success",
            "content": brief_content,
            "brief_id": brief_id,
        }

    except Exception as exc:
        logger.error(f"[TASK] Pipeline FAILED for topic {topic_id}: {exc}", exc_info=True)
        # Re-raise so Celery marks the task as FAILURE with the traceback
        raise


def _save_brief(topic_id: str, content: str) -> str | None:
    """Insert brief into Supabase and return the generated ID."""
    try:
        from truebrief.ledger.database import get_supabase
        db = get_supabase()
        res = db.table("briefs").insert({
            "topic_id": topic_id,
            "content": content,
        }).execute()
        if res.data:
            return res.data[0].get("id")
    except Exception as exc:
        logger.error(f"Failed to save brief to DB: {exc}")
    return None
