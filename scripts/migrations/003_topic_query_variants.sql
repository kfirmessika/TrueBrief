-- =============================================================================
-- Migration 003: Topic Query Variants (Dynamic Keyword Rotation)
-- =============================================================================
-- Run this ONCE in the Supabase SQL Editor.
--
-- What this creates:
--   topic_query_variants - Stores candidate search queries per topic.
--   Each scan picks the highest-performing variant as the primary_query.
--   Variants that consistently underperform are replaced by LLM-generated ones.
--
-- Performance tracking:
--   scans_used:      How many times this variant was used as the primary query.
--   alphas_yielded:  How many NEW/UPDATE decisions were produced during those scans.
--   ayr:             alphas_yielded / scans_used - computed each time a scan finishes.
--
-- Rotation logic (in query_rotator.py):
--   1. On first run for a topic → initialise variants from QueryBuilder output.
--   2. Before each scan → pick the variant with highest AYR (or least-used if tied).
--   3. After ROTATION_AFTER_SCANS uses with low AYR → mark as inactive,
--      generate a fresh replacement via LLM.
-- =============================================================================

CREATE TABLE IF NOT EXISTS topic_query_variants (
    id              uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
    topic_id        uuid        NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    query_text      text        NOT NULL,
    scans_used      integer     NOT NULL DEFAULT 0,
    alphas_yielded  integer     NOT NULL DEFAULT 0,
    ayr             float       NOT NULL DEFAULT 0.0,     -- Updated each scan
    is_active       boolean     NOT NULL DEFAULT true,
    generation      integer     NOT NULL DEFAULT 0,       -- 0 = original, 1 = first rotation, etc.
    created_at      timestamptz DEFAULT now(),
    last_used_at    timestamptz,
    UNIQUE(topic_id, query_text)                          -- No duplicate queries per topic
);

-- Index for the per-topic variant lookup (used before every scan)
CREATE INDEX IF NOT EXISTS idx_tqv_topic_active
    ON topic_query_variants (topic_id, is_active, ayr DESC);

-- =============================================================================
-- Verify:
-- =============================================================================
SELECT COUNT(*) AS total_rows FROM topic_query_variants;
