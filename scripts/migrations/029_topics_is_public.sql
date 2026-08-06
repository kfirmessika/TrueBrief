-- 029_topics_is_public.sql
-- Adds is_public flag to topics. Default false: /shared-topics currently has no
-- auth and no public/private filter, so every topic is effectively enumerable.
-- All 5 existing rows belong to the founder's own account and must stay private —
-- default false already achieves that, no backfill UPDATE needed.

ALTER TABLE topics ADD COLUMN IF NOT EXISTS is_public BOOLEAN NOT NULL DEFAULT false;

-- Verify
SELECT id, raw_query, is_public FROM topics ORDER BY created_at;
