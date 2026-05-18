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
import time

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
    started_at = time.monotonic()

    # --- Telemetry: open a pipeline_run row ---
    tel = None
    run_id = None
    try:
        from truebrief.ledger.telemetry import get_telemetry
        tel = get_telemetry()
        if tel:
            run_id = tel.start_run(topic_id=topic_id)
    except Exception:
        pass  # telemetry must never crash the pipeline

    # Set context var so LLMClient auto-tags every call with this run_id
    from truebrief.llm.client import pipeline_run_id_var
    token = pipeline_run_id_var.set(run_id)

    brief_length = 0
    exit_status = "error"

    try:
        from truebrief.pipeline.runner import PipelineRunner

        runner = PipelineRunner()

        # --- Run and capture intermediate metrics ---
        # We instrument run() by injecting a metrics-aware wrapper around _collect_all
        # and the decisions list. Rather than refactor PipelineRunner (which would break
        # tests), we patch after run() and read the runner's internal state.
        brief_content = runner.run(raw_query, topic_id=topic_id)

        # Detect no-update / rejection from the brief text
        if not brief_content or brief_content.strip() == "":
            logger.info(f"[TASK] Empty brief returned for topic {topic_id}")
            exit_status = "no_update"
            _finish_telemetry(tel, run_id, started_at, exit_status=exit_status)
            return {"status": "no_update", "content": "No new information found."}

        if brief_content.startswith("Topic rejected:"):
            logger.info(f"[TASK] Topic rejected: {brief_content}")
            exit_status = "rejected"
            _finish_telemetry(tel, run_id, started_at, exit_status=exit_status)
            return {"status": "rejected", "content": brief_content}

        brief_length = len(brief_content)
        exit_status = "success"

        # Save brief to Supabase
        brief_id = _save_brief(topic_id, brief_content)

        # --- Telemetry: close the run with summary counts ---
        _finish_telemetry(
            tel, run_id, started_at,
            exit_status=exit_status,
            brief_length=brief_length,
        )

        # Recalibrate poll interval based on observed Alpha Yield Rate (fire-and-forget)
        try:
            from truebrief.ledger.ayr_engine import update_topic_interval
            update_topic_interval(topic_id)
        except Exception as ayr_err:
            logger.warning(f"[TASK] AYR recalibration skipped: {ayr_err}")

        # Fire web push notification (fire-and-forget)
        try:
            from truebrief.ledger.database import get_supabase as _get_db
            from truebrief.tasks.push_task import send_push_notifications_task

            _db = _get_db()
            _topic_res = _db.table("topics").select("user_id, raw_query").eq("id", topic_id).execute()
            if _topic_res.data:
                _row = _topic_res.data[0]
                send_push_notifications_task.delay(
                    user_id=str(_row["user_id"]),
                    topic_name=_row["raw_query"],
                    brief_id=str(brief_id) if brief_id else "",
                )
        except Exception as push_err:
            logger.warning(f"[TASK] Push notification skipped: {push_err}")

        logger.info(f"[TASK] Pipeline SUCCESS for topic {topic_id}. Brief ID: {brief_id}")
        return {
            "status": "success",
            "content": brief_content,
            "brief_id": brief_id,
        }

    except Exception as exc:
        logger.error(f"[TASK] Pipeline FAILED for topic {topic_id}: {exc}", exc_info=True)
        _finish_telemetry(tel, run_id, started_at, exit_status="error", error_message=str(exc))
        raise

    finally:
        # Always restore context var
        pipeline_run_id_var.reset(token)


def _finish_telemetry(
    tel,
    run_id,
    started_at: float,
    exit_status: str = "success",
    brief_length: int = 0,
    error_message: str | None = None,
) -> None:
    """Helper: finalize the pipeline_run telemetry row. Never raises."""
    if tel is None or run_id is None:
        return
    try:
        duration_ms = int((time.monotonic() - started_at) * 1000)
        tel.finish_run(
            run_id,
            duration_ms=duration_ms,
            brief_length=brief_length,
            exit_status=exit_status,
            error_message=error_message,
        )
    except Exception as exc:
        logger.debug("Telemetry finish_run failed (non-fatal): %s", exc)


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
