-- =============================================================================
-- Migration 012: Pipeline Trace (Full Observability / Admin Debug Panel)
-- =============================================================================
-- Run this ONCE in the Supabase SQL Editor.
--
-- Purpose:
--   Make every pipeline run fully inspectable for the founder. Together with the
--   existing pipeline_run + llm_call_log tables, this captures the WHOLE story of
--   a scan so a bad/odd update can be pinpointed to the exact stage it came from.
--
-- Two changes:
--   1. pipeline_trace      - ordered, structured events for the NON-LLM stages
--                            (query+tools chosen & why, what each tool returned,
--                             MMR selection, URL-dedup skips, relevance-gate drops,
--                             per-fact judge decisions, final brief).
--   2. llm_call_log columns - the actual prompt / system_prompt / response text for
--                            every LLM call (harvester, arbiter, briefer, query
--                            builder, rotator). This is "what we sent the AI and
--                            got back", captured automatically in LLMClient.
--
-- The admin run-detail view merges pipeline_trace + llm_call_log by created_at into
-- one timeline. Capture is gated app-side by settings.TRACE_PIPELINE and truncated to
-- settings.TRACE_MAX_CHARS, so it can be turned off / bounded without a schema change.
-- =============================================================================

-- 1. Per-run structured trace events --------------------------------------------------
CREATE TABLE IF NOT EXISTS pipeline_trace (
    id              bigserial   PRIMARY KEY,
    pipeline_run_id uuid        REFERENCES pipeline_run(id) ON DELETE CASCADE,
    seq             integer     NOT NULL DEFAULT 0,     -- monotonic order within a run
    stage           text        NOT NULL,               -- query|collect|dedup|mmr|harvest|relevance|judge|brief|error
    label           text,                               -- short human-readable summary
    data            jsonb,                              -- structured payload for this event
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- Fast lookup of a single run's full trace, in order.
CREATE INDEX IF NOT EXISTS idx_pipeline_trace_run
    ON pipeline_trace (pipeline_run_id, seq);

-- 2. Capture the actual prompt/response on every LLM call ------------------------------
ALTER TABLE llm_call_log ADD COLUMN IF NOT EXISTS system_prompt text;
ALTER TABLE llm_call_log ADD COLUMN IF NOT EXISTS prompt        text;
ALTER TABLE llm_call_log ADD COLUMN IF NOT EXISTS response      text;

-- =============================================================================
-- Verify:
-- =============================================================================
SELECT COUNT(*) AS trace_rows FROM pipeline_trace;
SELECT column_name FROM information_schema.columns
 WHERE table_name = 'llm_call_log' AND column_name IN ('system_prompt','prompt','response');
