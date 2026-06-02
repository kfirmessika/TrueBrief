-- =============================================================================
-- Migration 007: Shared Topics — Deduplication & Fastest-Subscriber Interval
-- =============================================================================
-- Run ONCE in Supabase SQL Editor.
--
-- What this does:
--   1. Deduplicates the topics table: keeps one row per raw_query (case-insensitive).
--      All duplicate topic subscriptions, known_facts, briefs, and pipeline_runs
--      are re-pointed to the surviving canonical topic before the dupes are deleted.
--   2. Adds a UNIQUE constraint on topics.raw_query (lowercased) so no future
--      duplicates can be created.
--   3. Adds a helper function refresh_topic_interval(topic_id) that sets
--      poll_interval_seconds = the fastest (minimum) interval among all
--      subscribers' tiers, then re-schedules next_run_at accordingly.
--   4. Adds triggers on topic_subscriptions INSERT/DELETE so the interval
--      is kept up-to-date automatically.
--   5. Makes topics.user_id nullable (it becomes "original creator" metadata).
-- =============================================================================


-- ---------------------------------------------------------------------------
-- Step 1: Deduplicate topics
-- ---------------------------------------------------------------------------
-- For each group of topics sharing the same lowercased raw_query,
-- keep the oldest row (lowest created_at) as the canonical one.
-- Re-point all child rows in topic_subscriptions, known_facts, briefs,
-- pipeline_run to the canonical id, then delete the duplicates.
-- ---------------------------------------------------------------------------

DO $$
DECLARE
    canonical_id   uuid;
    dup_id         uuid;
    dup_rec        RECORD;
BEGIN
    -- Iterate over every raw_query that has more than one topic row
    FOR dup_rec IN
        SELECT lower(raw_query) AS norm_query
        FROM topics
        GROUP BY lower(raw_query)
        HAVING count(*) > 1
    LOOP
        -- Pick the canonical (oldest) topic for this query
        SELECT id INTO canonical_id
        FROM topics
        WHERE lower(raw_query) = dup_rec.norm_query
        ORDER BY created_at ASC
        LIMIT 1;

        -- Process every other row with the same query
        FOR dup_id IN
            SELECT id
            FROM topics
            WHERE lower(raw_query) = dup_rec.norm_query
              AND id <> canonical_id
        LOOP
            RAISE NOTICE 'Merging topic % → canonical %', dup_id, canonical_id;

            -- Re-point topic_subscriptions (skip if canonical already has that user)
            INSERT INTO topic_subscriptions (user_id, topic_id, created_at)
            SELECT user_id, canonical_id, created_at
            FROM topic_subscriptions
            WHERE topic_id = dup_id
            ON CONFLICT (user_id, topic_id) DO NOTHING;

            DELETE FROM topic_subscriptions WHERE topic_id = dup_id;

            -- Re-point known_facts (if table exists)
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'known_facts' AND table_schema = 'public') THEN
                UPDATE known_facts SET topic_id = canonical_id WHERE topic_id = dup_id;
            END IF;

            -- Re-point briefs (if table exists)
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'briefs' AND table_schema = 'public') THEN
                UPDATE briefs SET topic_id = canonical_id WHERE topic_id = dup_id;
            END IF;

            -- Re-point pipeline_run (if table exists)
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'pipeline_run' AND table_schema = 'public') THEN
                UPDATE pipeline_run SET topic_id = canonical_id WHERE topic_id = dup_id;
            END IF;

            -- Delete the duplicate topic row
            DELETE FROM topics WHERE id = dup_id;
        END LOOP;
    END LOOP;
END $$;


-- ---------------------------------------------------------------------------
-- Step 2: Normalise raw_query to lowercase in all surviving rows
-- ---------------------------------------------------------------------------
UPDATE topics SET raw_query = lower(trim(raw_query));


-- ---------------------------------------------------------------------------
-- Step 3: Add UNIQUE constraint so duplicates can never re-appear
-- ---------------------------------------------------------------------------
ALTER TABLE topics
    ADD CONSTRAINT topics_raw_query_unique UNIQUE (raw_query);


-- ---------------------------------------------------------------------------
-- Step 4: Make user_id nullable (it's now just "original creator" metadata)
-- ---------------------------------------------------------------------------
ALTER TABLE topics
    ALTER COLUMN user_id DROP NOT NULL;


-- ---------------------------------------------------------------------------
-- Step 5: Tier-to-interval mapping table
-- Mirrors src/truebrief/models/tier.py TIER_LIMITS.
-- Seconds = min_interval_hours * 3600.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tier_intervals (
    tier                text PRIMARY KEY,
    poll_interval_seconds integer NOT NULL
);

INSERT INTO tier_intervals (tier, poll_interval_seconds) VALUES
    ('free',  86400),   -- 24 h
    ('pro',    3600),   -- 1 h
    ('power',   900)    -- 15 min
ON CONFLICT (tier) DO UPDATE
    SET poll_interval_seconds = EXCLUDED.poll_interval_seconds;


-- ---------------------------------------------------------------------------
-- Step 6: Function to recompute poll_interval_seconds for a shared topic
-- Uses the MINIMUM (fastest) interval among all subscribed users' tiers.
-- Falls back to 86400 (free/daily) if no subscribers have a known tier.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION refresh_topic_interval(p_topic_id uuid)
RETURNS void
LANGUAGE plpgsql
SET search_path = public, extensions
AS $$
DECLARE
    v_min_interval integer;
BEGIN
    SELECT MIN(COALESCE(ti.poll_interval_seconds, 86400))
    INTO v_min_interval
    FROM topic_subscriptions ts
    LEFT JOIN user_subscriptions us ON us.user_id = ts.user_id
    LEFT JOIN tier_intervals    ti ON ti.tier = COALESCE(us.tier, 'free')
    WHERE ts.topic_id = p_topic_id;

    -- If no subscribers, default to daily
    v_min_interval := COALESCE(v_min_interval, 86400);

    UPDATE topics
    SET poll_interval_seconds = v_min_interval,
        -- Re-schedule: if already overdue just leave next_run_at as-is;
        -- otherwise shorten it if new interval is faster than remaining wait.
        next_run_at = LEAST(
            COALESCE(next_run_at, now()),
            now() + (v_min_interval || ' seconds')::interval
        )
    WHERE id = p_topic_id;
END;
$$;


-- ---------------------------------------------------------------------------
-- Step 7: Trigger — keep interval fresh on subscription changes
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION _trg_refresh_topic_interval()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, extensions
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        PERFORM refresh_topic_interval(OLD.topic_id);
    ELSE
        PERFORM refresh_topic_interval(NEW.topic_id);
    END IF;
    RETURN NULL;  -- AFTER trigger, return value is ignored
END;
$$;

DROP TRIGGER IF EXISTS trg_topic_sub_interval ON topic_subscriptions;
CREATE TRIGGER trg_topic_sub_interval
AFTER INSERT OR DELETE ON topic_subscriptions
FOR EACH ROW EXECUTE FUNCTION _trg_refresh_topic_interval();


-- ---------------------------------------------------------------------------
-- Step 8: Back-fill intervals for all existing topics
-- ---------------------------------------------------------------------------
DO $$
DECLARE r RECORD;
BEGIN
    FOR r IN SELECT id FROM topics WHERE is_active = true LOOP
        PERFORM refresh_topic_interval(r.id);
    END LOOP;
END $$;


-- ---------------------------------------------------------------------------
-- Verify
-- ---------------------------------------------------------------------------
SELECT
    t.id,
    t.raw_query,
    t.poll_interval_seconds,
    t.next_run_at,
    count(ts.user_id) AS subscriber_count
FROM topics t
LEFT JOIN topic_subscriptions ts ON ts.topic_id = t.id
GROUP BY t.id, t.raw_query, t.poll_interval_seconds, t.next_run_at
ORDER BY subscriber_count DESC, t.created_at DESC;
