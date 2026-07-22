-- Migration 027: create the 3 cost-aggregation RPCs that /admin/cost-summary depends on.
--
-- Root cause of "cost always shows 0" (diagnosed 2026-07-22, verified against the live DB):
-- llm_call_log and pipeline_run ALREADY EXIST and already contain real data (11,537 rows,
-- 6,918 with non-zero cost_usd — pricing.py has been computing correctly for a while; the
-- remaining zero-cost rows are historical, from before that was true, and are not fixable
-- retroactively). The tables were never the problem.
--
-- The actual bug: llm_cost_by_stage, llm_cost_by_day, and pipeline_run_summary were only ever
-- defined in ledger/schema.sql, never added to this migration chain, so they don't exist live.
-- /admin/cost-summary calls them via db.rpc(...), gets a PGRST202 "function not found" error,
-- and its try/except silently swallows it and returns zeros — indistinguishable from "no cost."
--
-- Also fixes a real bug in schema.sql's own pipeline_run_summary definition: it filters on
-- pipeline_run.created_at, but the live table's column is `started_at` (confirmed via direct
-- query) — as originally written, this RPC would have errored even after being created.
--
-- `create or replace function` is idempotent — safe to re-run.

create or replace function llm_cost_by_stage(days_back int default 30)
returns table (
    stage text,
    calls bigint,
    total_input_tokens bigint,
    total_output_tokens bigint,
    total_cost_usd numeric,
    avg_duration_ms numeric
)
language sql set search_path = public, extensions as $$
    select
        stage,
        count(*)                    as calls,
        sum(input_tokens)           as total_input_tokens,
        sum(output_tokens)          as total_output_tokens,
        sum(cost_usd)               as total_cost_usd,
        avg(duration_ms)            as avg_duration_ms
    from llm_call_log
    where created_at >= now() - (days_back || ' days')::interval
    group by stage
    order by total_cost_usd desc;
$$;

create or replace function llm_cost_by_day(days_back int default 30)
returns table (
    day date,
    calls bigint,
    total_cost_usd numeric
)
language sql set search_path = public, extensions as $$
    select
        created_at::date            as day,
        count(*)                    as calls,
        sum(cost_usd)               as total_cost_usd
    from llm_call_log
    where created_at >= now() - (days_back || ' days')::interval
    group by created_at::date
    order by day;
$$;

-- Uses started_at, not created_at (schema.sql's version used the wrong column name).
create or replace function pipeline_run_summary(days_back int default 30)
returns table (
    total_runs bigint,
    successful_runs bigint,
    avg_duration_ms numeric,
    total_brief_chars bigint
)
language sql set search_path = public, extensions as $$
    select
        count(*)                        as total_runs,
        count(*) filter (where exit_status = 'success') as successful_runs,
        avg(duration_ms)                as avg_duration_ms,
        sum(brief_length)               as total_brief_chars
    from pipeline_run
    where started_at >= now() - (days_back || ' days')::interval;
$$;
