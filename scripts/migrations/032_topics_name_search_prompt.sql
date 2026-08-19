-- 032_topics_name_search_prompt.sql
-- Adds name and search_prompt columns to topics, backfilled from raw_query.
-- raw_query stays untouched (used for exact-match dedup on topic creation).

ALTER TABLE topics ADD COLUMN IF NOT EXISTS name TEXT;
ALTER TABLE topics ADD COLUMN IF NOT EXISTS search_prompt TEXT;

UPDATE topics
SET name = raw_query
WHERE name IS NULL;

UPDATE topics
SET search_prompt = raw_query
WHERE search_prompt IS NULL;

-- Verify
SELECT id, raw_query, name, search_prompt FROM topics ORDER BY created_at;
