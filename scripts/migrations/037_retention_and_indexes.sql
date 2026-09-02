-- Migration 037: telemetry retention RPCs + missing/duplicate indexes.
--
-- Gate 3 (launch-readiness audit, 2026-08-20):
--   * llm_call_log is the largest table — ~16 MB of rows + ~83 MB of stored
--     prompt/response text. pipeline_trace adds ~26 MB. Neither is ever pruned
--     and pg_cron is not installed. These break first as users arrive.
--   * briefs.topic_id and topic_subscriptions.topic_id are unindexed FKs.
--   * known_facts_alpha_embedding_idx1 duplicates an existing embedding index.
--
-- The prune functions are called daily by truebrief.tasks.retention_task via the
-- Celery beat schedule (no pg_cron needed). They keep every cost/latency column and
-- only shed the heavy free-text payloads (and old trace rows outright).
--
-- All statements are idempotent.

-- 1. Prune stored LLM prompt/response text older than N days (keeps cost telemetry).
create or replace function prune_llm_call_payloads(days_to_keep int default 14)
returns bigint
language sql
as $$
    with pruned as (
        update llm_call_log
           set prompt = null, system_prompt = null, response = null
         where created_at < now() - make_interval(days => days_to_keep)
           and (prompt is not null or system_prompt is not null or response is not null)
        returning 1
    )
    select count(*) from pruned;
$$;

-- 2. Delete pipeline_trace rows older than N days outright (pure observability).
create or replace function prune_pipeline_trace(days_to_keep int default 14)
returns bigint
language sql
as $$
    with pruned as (
        delete from pipeline_trace
         where created_at < now() - make_interval(days => days_to_keep)
        returning 1
    )
    select count(*) from pruned;
$$;

-- 3. Missing FK indexes.
create index if not exists idx_briefs_topic_id
    on public.briefs (topic_id);

create index if not exists idx_topic_subscriptions_topic_id
    on public.topic_subscriptions (topic_id);

-- 4. Duplicate embedding index flagged by the audit.
drop index if exists public.known_facts_alpha_embedding_idx1;
