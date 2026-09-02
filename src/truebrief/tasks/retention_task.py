"""
Retention Task — tasks/retention_task.py

Celery Beat task: keeps the two fastest-growing tables bounded.

  - llm_call_log:  keeps every cost/latency column forever; drops the heavy
                   prompt / system_prompt / response TEXT after
                   settings.TELEMETRY_PAYLOAD_RETENTION_DAYS days.
  - pipeline_trace: rows deleted outright after
                   settings.PIPELINE_TRACE_RETENTION_DAYS days.

Both run through SQL RPCs (migration 037) so the delete/update happens in one
server-side statement, not row-by-row over PostgREST. pg_cron is not installed
on this project — this task is the scheduler.

Registered in celery_app.py beat_schedule (daily, 03:30 UTC). Never raises.
"""

from __future__ import annotations

import logging

from truebrief.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="truebrief.tasks.retention_task.prune_telemetry_task",
    bind=False,
    ignore_result=False,
    max_retries=0,
)
def prune_telemetry_task() -> dict:
    """Prune old LLM payload text and pipeline_trace rows. Returns a summary dict."""
    from config.settings import settings
    from truebrief.ledger.database import get_supabase

    payload_days = int(getattr(settings, "TELEMETRY_PAYLOAD_RETENTION_DAYS", 14))
    trace_days = int(getattr(settings, "PIPELINE_TRACE_RETENTION_DAYS", 14))

    db = get_supabase()
    result = {"llm_payloads_pruned": 0, "trace_rows_deleted": 0, "errors": []}

    try:
        r = db.rpc("prune_llm_call_payloads", {"days_to_keep": payload_days}).execute()
        result["llm_payloads_pruned"] = int(r.data or 0)
    except Exception as exc:
        logger.error("retention: prune_llm_call_payloads failed: %s", exc)
        result["errors"].append(f"llm_payloads: {exc}")

    try:
        r = db.rpc("prune_pipeline_trace", {"days_to_keep": trace_days}).execute()
        result["trace_rows_deleted"] = int(r.data or 0)
    except Exception as exc:
        logger.error("retention: prune_pipeline_trace failed: %s", exc)
        result["errors"].append(f"pipeline_trace: {exc}")

    logger.info(
        "retention: pruned %s llm payloads, deleted %s trace rows (keep %sd / %sd)",
        result["llm_payloads_pruned"], result["trace_rows_deleted"], payload_days, trace_days,
    )
    return result
