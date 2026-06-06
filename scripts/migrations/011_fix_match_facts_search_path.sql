-- Migration 011: Fix match_facts RPC search_path so pgvector <=> operator resolves
--
-- Root cause: the function was created with search_path=public only.
-- pgvector's <=> operator is registered in the 'extensions' schema.
-- Result: every call silently failed, the Arbiter saw 0 ledger matches,
-- and classified every incoming fact as NEW — producing 0 UPDATE/DUPLICATE decisions.
--
-- Also fixes return type: event_date is timestamptz not date.
-- Both DROP + CREATE steps were applied as migrations 011 and 012 via MCP.

DROP FUNCTION IF EXISTS match_facts(extensions.vector, float, int, uuid);

CREATE FUNCTION match_facts(
    query_embedding extensions.vector(768),
    match_threshold float,
    match_count     int,
    filter_topic_id uuid
)
RETURNS TABLE (
    id            uuid,
    topic_id      uuid,
    alpha_text    text,
    entities      jsonb,
    event_date    timestamptz,
    context       text,
    confidence    double precision,
    source_url    text,
    source_domain text,
    similarity    float
)
LANGUAGE plpgsql
SET search_path = extensions, public, pg_catalog
AS $$
BEGIN
    RETURN QUERY
    SELECT
        kf.id,
        kf.topic_id,
        kf.alpha_text,
        kf.entities,
        kf.event_date,
        kf.context,
        kf.confidence,
        kf.source_url,
        kf.source_domain,
        (1 - (kf.alpha_embedding <=> query_embedding))::float AS similarity
    FROM known_facts kf
    WHERE (filter_topic_id IS NULL OR kf.topic_id = filter_topic_id)
      AND 1 - (kf.alpha_embedding <=> query_embedding) > match_threshold
    ORDER BY kf.alpha_embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
