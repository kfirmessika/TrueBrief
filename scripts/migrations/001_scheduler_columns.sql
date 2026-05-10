-- =============================================================================
-- Migration 001: Scheduler Columns for Topics Table
-- =============================================================================
-- Run this ONCE in the Supabase SQL Editor:
--   https://supabase.com/dashboard/project/<your-project>/sql/new
--
-- What this adds:
--   poll_interval_seconds  - How often (in seconds) to auto-scan this topic
--                            Default: 3600 (1 hour)
--   next_run_at            - Timestamp of the NEXT scheduled scan
--                            Beat checks: WHERE next_run_at <= now() AND is_active = true
--   last_run_at            - Timestamp of the LAST completed scan (for debugging)
--
-- After running this migration, topics already in the DB will get:
--   poll_interval_seconds = 3600
--   next_run_at           = NOW() (immediately eligible for first scan)
-- =============================================================================

-- Add scheduling columns (safe: IF NOT EXISTS prevents errors on re-run)
ALTER TABLE topics
  ADD COLUMN IF NOT EXISTS poll_interval_seconds integer NOT NULL DEFAULT 3600,
  ADD COLUMN IF NOT EXISTS next_run_at           timestamptz,
  ADD COLUMN IF NOT EXISTS last_run_at           timestamptz;

-- Immediately schedule all existing active topics for a first scan
UPDATE topics
SET next_run_at = NOW()
WHERE is_active = true AND next_run_at IS NULL;

-- Index for the scheduler heartbeat query (topics WHERE next_run_at <= now())
CREATE INDEX IF NOT EXISTS idx_topics_next_run_at
  ON topics (next_run_at)
  WHERE is_active = true;

-- =============================================================================
-- Verify the migration ran correctly:
-- =============================================================================
SELECT
  id,
  raw_query,
  is_active,
  poll_interval_seconds,
  next_run_at,
  last_run_at
FROM topics
ORDER BY created_at DESC
LIMIT 10;
