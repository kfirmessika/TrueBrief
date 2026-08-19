-- Migration 031: llm_cost_for_topics RPC for the admin per-user data view.
--
-- Needed because PostgREST silently caps an unfiltered/large select at 1000 rows
-- (documented at src/truebrief/api/routes.py:1700-1706). An admin/founder's own topics
-- can produce more than 1000 llm_call_log rows, so a naive Python-side sum over a
-- paginated select would silently undercount. This RPC sums server-side instead,
-- joining llm_call_log -> pipeline_run and filtering on pipeline_run.topic_id = any(topic_ids).
--
-- Mirrors the style of llm_cost_by_stage / llm_cost_by_day / pipeline_run_summary
-- introduced in 027_llm_cost_rpcs.sql.
--
-- `create or replace function` is idempotent -- safe to re-run.

create or replace function llm_cost_for_topics(topic_ids uuid[])
returns table (
    total_cost_usd numeric,
    total_tokens bigint,
    run_count bigint
)
language sql set search_path = public, extensions as $$
    select
        coalesce(sum(l.cost_usd), 0)                       as total_cost_usd,
        coalesce(sum(l.input_tokens + l.output_tokens), 0)  as total_tokens,
        count(distinct l.pipeline_run_id)                   as run_count
    from llm_call_log l
    join pipeline_run pr on pr.id = l.pipeline_run_id
    where pr.topic_id = any(topic_ids);
$$;

-- Verify
select * from llm_cost_for_topics(array[]::uuid[]);
