-- =============================================================================
-- Migration 005: Story Nodes (Phase 3, Task 3.1 + 3.2)
-- =============================================================================
-- Run this ONCE in the Supabase SQL Editor.
--
-- What this creates:
--   story_nodes         - Clusters of related Alphas that form evolving narratives.
--   known_facts.story_node_id - Links each fact to its parent story.
--   match_stories()     - RPC for semantic story matching (dual-vector, Task 3.2).
--
-- Dependencies: Requires schema.sql (base tables) to already exist.
-- =============================================================================

-- ─── 1. Story Nodes Table ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS story_nodes (
    id                  uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
    topic_id            uuid        NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    title               text        NOT NULL,
    summary             text        NOT NULL DEFAULT '',

    -- Task 3.2: Dual vectors
    -- alpha_embedding   → stored per-fact in known_facts (unchanged)
    -- summary_embedding → stored per-story here (story-level semantic fingerprint)
    summary_embedding   vector(768),

    status              text        NOT NULL DEFAULT 'active',  -- active / resolved / stale
    fact_count          int         NOT NULL DEFAULT 0,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- Index: fetch all stories for a topic efficiently
CREATE INDEX IF NOT EXISTS idx_story_nodes_topic_id
    ON story_nodes (topic_id);

-- Index: filter by lifecycle status
CREATE INDEX IF NOT EXISTS idx_story_nodes_status
    ON story_nodes (status);

-- HNSW index on summary_embedding for fast cosine similarity search
CREATE INDEX IF NOT EXISTS idx_story_nodes_summary_embedding
    ON story_nodes USING hnsw (summary_embedding vector_cosine_ops);

-- ─── 2. Link Facts → Stories ──────────────────────────────────────────────────

ALTER TABLE known_facts
    ADD COLUMN IF NOT EXISTS story_node_id uuid REFERENCES story_nodes(id);

CREATE INDEX IF NOT EXISTS idx_known_facts_story_node_id
    ON known_facts (story_node_id);

-- ─── 3. RLS Policies ──────────────────────────────────────────────────────────

ALTER TABLE story_nodes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read access to story_nodes" ON story_nodes
    FOR SELECT USING (true);

CREATE POLICY "Allow modify access to story_nodes" ON story_nodes
    FOR ALL USING (auth.role() IN ('anon', 'authenticated'));

-- ─── 4. match_stories RPC ─────────────────────────────────────────────────────
-- Finds StoryNodes whose summary_embedding is semantically close to a query.
-- Called by StoryManager._find_similar_stories() to assign incoming facts.

CREATE OR REPLACE FUNCTION match_stories(
    query_embedding     vector(768),
    match_threshold     float,
    match_count         int,
    filter_topic_id     uuid DEFAULT NULL
)
RETURNS TABLE (
    id          uuid,
    topic_id    uuid,
    title       text,
    summary     text,
    status      text,
    fact_count  int,
    created_at  timestamptz,
    updated_at  timestamptz,
    similarity  float
)
LANGUAGE plpgsql
SET search_path = public, extensions
AS $$
BEGIN
    RETURN QUERY
    SELECT
        sn.id,
        sn.topic_id,
        sn.title,
        sn.summary,
        sn.status,
        sn.fact_count,
        sn.created_at,
        sn.updated_at,
        1 - (sn.summary_embedding <=> query_embedding) AS similarity
    FROM story_nodes sn
    WHERE (filter_topic_id IS NULL OR sn.topic_id = filter_topic_id)
      AND sn.status = 'active'
      AND sn.summary_embedding IS NOT NULL
      AND 1 - (sn.summary_embedding <=> query_embedding) > match_threshold
    ORDER BY sn.summary_embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
