-- Migration 009: Store user's chosen poll frequency separately from AYR-managed interval
--
-- user_interval_seconds = NULL → "Auto" mode: AYR controls poll_interval_seconds freely
--                                within the tier floor.
-- user_interval_seconds = N   → User locked the frequency. AYR will never set
--                                poll_interval_seconds below N.
--
-- This prevents AYR from overriding a user who chose "Daily" just because the
-- topic had a high alpha-yield rate in one run.

ALTER TABLE topics
  ADD COLUMN IF NOT EXISTS user_interval_seconds integer NULL;

COMMENT ON COLUMN topics.user_interval_seconds IS
  'User-chosen minimum interval in seconds. NULL = Auto (AYR manages freely). AYR will never set poll_interval_seconds below this value.';
