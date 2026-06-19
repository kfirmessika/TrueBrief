-- Migration 013: event_class on known_facts (IC1 tally-collapse + IC2 significance ordering)
--
-- Adds event_class to known_facts so the harvester can label each fact's development type
-- (state_change / escalation / development / incremental / tally / routine).
-- Updates match_facts RPC to return it so the arbiter can use it for tally-collapse (IC1).

-- 1. Add column (safe on existing rows — NULL means "unlabelled / pre-migration fact")
ALTER TABLE known_facts
    ADD COLUMN IF NOT EXISTS event_class VARCHAR(20) DEFAULT NULL;

-- 2. Index for the IC1 tally-collapse query (topic + event_class lookup)
CREATE INDEX IF NOT EXISTS known_facts_event_class_idx
    ON known_facts (topic_id, event_class)
    WHERE event_class IS NOT NULL;

-- 3. Replace match_facts to include event_class in results
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
    event_class   varchar,
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
        kf.event_class,
        (1 - (kf.alpha_embedding <=> query_embedding))::float AS similarity
    FROM known_facts kf
    WHERE (filter_topic_id IS NULL OR kf.topic_id = filter_topic_id)
      AND 1 - (kf.alpha_embedding <=> query_embedding) > match_threshold
    ORDER BY kf.alpha_embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
