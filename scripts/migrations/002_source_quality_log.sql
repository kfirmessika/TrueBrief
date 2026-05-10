-- =============================================================================
-- Migration 002: Source Quality Log Table (AYR Foundation)
-- =============================================================================
-- Run this ONCE in the Supabase SQL Editor.
--
-- What this creates:
--   source_quality_log - One row per Alpha that passes through the Arbiter.
--   Tracks which SOURCE domain produced it and what the DECISION was.
--
-- Used by Task 2.10 (AYR calculation) to compute:
--   Alpha Yield Rate = (NEW + UPDATE) / total per source domain
--   → High AYR sources get polled more often
--   → Low AYR sources get polled less often
--
-- Schema design decisions:
--   - source_domain is extracted from source_url in Python (not a FK), so we
--     don't need a sources table for Phase 2. AYR will GROUP BY source_domain.
--   - alpha_id is nullable (not a FK to facts table) to avoid cascade deletes
--     wiping quality history when facts are removed.
--   - No UPDATE on this table - append-only log.
-- =============================================================================

CREATE TABLE IF NOT EXISTS source_quality_log (
    id              uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
    topic_id        uuid        REFERENCES topics(id) ON DELETE CASCADE,
    alpha_id        uuid,                          -- The fact ID (nullable, not a FK)
    source_url      text        NOT NULL,
    source_name     text        NOT NULL,
    source_domain   text        NOT NULL,          -- Extracted: "reuters.com", "bloomberg.com"
    decision        text        NOT NULL           -- "NEW" | "UPDATE" | "DUPLICATE"
                    CHECK (decision IN ('NEW', 'UPDATE', 'DUPLICATE')),
    similarity_score float      DEFAULT 0.0,       -- Top adjusted score from Arbiter
    created_at      timestamptz DEFAULT now()
);

-- Index for AYR aggregation: GROUP BY source_domain WHERE topic_id = ?
CREATE INDEX IF NOT EXISTS idx_sql_topic_domain
    ON source_quality_log (topic_id, source_domain);

-- Index for time-windowed AYR (last 7 days, last 30 days)
CREATE INDEX IF NOT EXISTS idx_sql_created_at
    ON source_quality_log (created_at);

-- =============================================================================
-- Verify:
-- =============================================================================
SELECT COUNT(*) as total_rows FROM source_quality_log;
