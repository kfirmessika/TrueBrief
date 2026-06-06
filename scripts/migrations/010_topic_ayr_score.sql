-- Migration 010: Store smoothed AYR score per topic for EMA calculation
--
-- Formula (architecture spec):
--   session_yield  = (NEW + UPDATE decisions) / total decisions
--   ayr_score_new  = (session_yield × 0.3) + (ayr_score × 0.7)   ← EMA
--   poll_interval  = user_interval_seconds / max(ayr_score_new, 0.1)
--
-- Because ayr_score ≤ 1.0, poll_interval is always ≥ user_interval_seconds.
-- The user's chosen frequency is mathematically the fastest it can ever run.
-- AYR can only slow polling down when a topic goes quiet.

ALTER TABLE topics
  ADD COLUMN IF NOT EXISTS ayr_score float NOT NULL DEFAULT 0.5;

COMMENT ON COLUMN topics.ayr_score IS
  'Smoothed Alpha Yield Rate (EMA α=0.3). Range 0.0–1.0. Updated after every pipeline run. poll_interval_seconds = user_interval_seconds / max(ayr_score, 0.1).';
