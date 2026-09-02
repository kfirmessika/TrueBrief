-- V5 admin cost aggregation.
--
-- The admin must never sum an unbounded PostgREST response: it silently stops at
-- the API row cap and makes a partial number look complete. This RPC aggregates in
-- Postgres and returns one compact row per UTC day / stage / model.

CREATE OR REPLACE FUNCTION admin_v5_cost_breakdown(days_back integer DEFAULT 30)
RETURNS TABLE (
    occurred_on date,
    stage text,
    model text,
    calls bigint,
    input_tokens bigint,
    output_tokens bigint,
    recorded_cost_usd numeric
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        (created_at AT TIME ZONE 'UTC')::date AS occurred_on,
        stage,
        model,
        COUNT(*)::bigint AS calls,
        COALESCE(SUM(input_tokens), 0)::bigint AS input_tokens,
        COALESCE(SUM(output_tokens), 0)::bigint AS output_tokens,
        COALESCE(SUM(
            CASE
                -- Historical rows predate fixed-cost telemetry. Recalculate these
                -- known request-priced providers from their successful call count.
                WHEN model = 'linkup/sourcedAnswer' THEN 0.006
                WHEN model = 'brave/web-summary' THEN 0.005
                ELSE cost_usd
            END
        ), 0)::numeric AS recorded_cost_usd
    FROM llm_call_log
    WHERE days_back <= 0
       OR created_at >= date_trunc('day', NOW() AT TIME ZONE 'UTC') - make_interval(days => days_back - 1)
    GROUP BY 1, 2, 3
    ORDER BY occurred_on DESC, recorded_cost_usd DESC;
$$;

GRANT EXECUTE ON FUNCTION admin_v5_cost_breakdown(integer) TO authenticated, service_role;
