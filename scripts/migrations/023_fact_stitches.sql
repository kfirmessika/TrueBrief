-- V4-2: fact_stitches — cached connective sentences for the story view.
-- Each row stores the bridge sentence between two adjacent facts (by event_date).
-- before_fact_id = the chronologically EARLIER fact.
-- after_fact_id  = the chronologically LATER fact.
-- Unique on (topic_id, before_fact_id, after_fact_id) — one stitch per pair.

CREATE TABLE IF NOT EXISTS fact_stitches (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id        uuid NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    before_fact_id  uuid NOT NULL REFERENCES known_facts(id) ON DELETE CASCADE,
    after_fact_id   uuid NOT NULL REFERENCES known_facts(id) ON DELETE CASCADE,
    passage         text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (topic_id, before_fact_id, after_fact_id)
);

CREATE INDEX IF NOT EXISTS fact_stitches_topic_idx ON fact_stitches(topic_id);
