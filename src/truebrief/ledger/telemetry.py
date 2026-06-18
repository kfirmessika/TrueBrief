"""
Telemetry Logger - ledger/telemetry.py

Fire-and-forget DB logging for cost & latency telemetry.
Writes to `pipeline_run` and `llm_call_log` tables.
All methods catch their own exceptions — telemetry must NEVER crash the pipeline.

Usage:
    tel = TelemetryLogger()
    run_id = tel.start_run(topic_id="uuid")
    ...
    tel.log_llm_call(run_id, stage="harvester", model="gemini-2.0-flash-lite", ...)
    ...
    tel.finish_run(run_id, exit_status="success", ...)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class TelemetryLogger:
    """Thin wrapper around Supabase for cost & latency telemetry rows."""

    def __init__(self) -> None:
        from truebrief.ledger.database import get_supabase
        self._db = get_supabase()

    # -------------------------------------------------------------------------
    # pipeline_run
    # -------------------------------------------------------------------------

    def start_run(self, topic_id: Optional[str] = None) -> Optional[str]:
        """
        Insert a pipeline_run row and return its UUID.
        Returns None on failure (telemetry is non-blocking).
        """
        try:
            row = {
                "topic_id": topic_id,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "exit_status": "running",
            }
            res = self._db.table("pipeline_run").insert(row).execute()
            if res.data:
                run_id = res.data[0]["id"]
                logger.debug("Telemetry: pipeline_run started id=%s", run_id)
                return run_id
        except Exception as exc:
            logger.warning("Telemetry: start_run failed: %s", exc)
        return None

    def finish_run(
        self,
        run_id: Optional[str],
        *,
        duration_ms: int,
        articles_collected: int = 0,
        articles_selected: int = 0,
        alphas_extracted: int = 0,
        decisions_new: int = 0,
        decisions_update: int = 0,
        decisions_duplicate: int = 0,
        brief_length: int = 0,
        exit_status: str = "success",
        error_message: Optional[str] = None,
    ) -> None:
        """Update an existing pipeline_run row with final metrics."""
        if not run_id:
            return
        try:
            update = {
                "duration_ms": duration_ms,
                "articles_collected": articles_collected,
                "articles_selected": articles_selected,
                "alphas_extracted": alphas_extracted,
                "decisions_new": decisions_new,
                "decisions_update": decisions_update,
                "decisions_duplicate": decisions_duplicate,
                "brief_length": brief_length,
                "exit_status": exit_status,
                "error_message": error_message,
            }
            self._db.table("pipeline_run").update(update).eq("id", run_id).execute()
            logger.debug("Telemetry: pipeline_run finished id=%s status=%s", run_id, exit_status)
        except Exception as exc:
            logger.warning("Telemetry: finish_run failed: %s", exc)

    # -------------------------------------------------------------------------
    # llm_call_log
    # -------------------------------------------------------------------------

    def log_llm_call(
        self,
        run_id: Optional[str],
        *,
        stage: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        duration_ms: int,
        prompt: Optional[str] = None,
        system_prompt: Optional[str] = None,
        response: Optional[str] = None,
    ) -> None:
        """Insert one row into llm_call_log. Fire-and-forget.

        When prompt/response are provided (TRACE_PIPELINE on), they are stored so the
        admin panel can show exactly what was sent to the model and what came back.
        """
        try:
            row = {
                "pipeline_run_id": run_id,
                "stage": stage,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": float(round(cost_usd, 8)),
                "duration_ms": duration_ms,
            }
            # Only attach payload columns when present — keeps old behaviour if the
            # 012 migration hasn't run yet (Supabase ignores unknown keys → would error,
            # so we add them conditionally and swallow the error to retry without them).
            if prompt is not None:
                row["prompt"] = prompt
            if system_prompt is not None:
                row["system_prompt"] = system_prompt
            if response is not None:
                row["response"] = response
            try:
                self._db.table("llm_call_log").insert(row).execute()
            except Exception:
                # Most likely the payload columns don't exist yet (pre-012). Retry
                # with just the core metrics so cost/latency telemetry still lands.
                for k in ("prompt", "system_prompt", "response"):
                    row.pop(k, None)
                self._db.table("llm_call_log").insert(row).execute()
        except Exception as exc:
            logger.warning("Telemetry: log_llm_call failed: %s", exc)

    # -------------------------------------------------------------------------
    # pipeline_trace  (full per-run observability — non-LLM stages)
    # -------------------------------------------------------------------------

    def log_trace(
        self,
        run_id: Optional[str],
        *,
        seq: int,
        stage: str,
        label: Optional[str] = None,
        data: Optional[dict] = None,
    ) -> None:
        """Insert one structured trace event for a run. Fire-and-forget.

        Used by the pipeline runner to record what happened at each stage
        (query/tool selection, collected articles, MMR picks, judge decisions, ...).
        No-ops silently if run_id is None or the pipeline_trace table is missing.
        """
        if not run_id:
            return
        try:
            self._db.table("pipeline_trace").insert({
                "pipeline_run_id": run_id,
                "seq": seq,
                "stage": stage,
                "label": label,
                "data": data or {},
            }).execute()
        except Exception as exc:
            logger.debug("Telemetry: log_trace failed (non-fatal): %s", exc)


# Module-level singleton — instantiated lazily so imports don't fail without DB.
_instance: Optional[TelemetryLogger] = None


def get_telemetry() -> Optional[TelemetryLogger]:
    """Return the singleton TelemetryLogger, or None if DB is unavailable."""
    global _instance
    if _instance is None:
        try:
            _instance = TelemetryLogger()
        except Exception as exc:
            logger.warning("Telemetry: could not initialize: %s", exc)
            return None
    return _instance
