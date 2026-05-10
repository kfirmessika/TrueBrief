-- =============================================================================
-- Migration 004: Shared Topic Infrastructure
-- =============================================================================
-- Run this ONCE in the Supabase SQL Editor.
--
-- What this creates:
--   topic_subscriptions - Maps users to topics for a many-to-many relationship.
--   This allows multiple users to subscribe to the same topic ("TSMC"),
--   meaning the pipeline only runs once and fans out the brief to all subscribers.
--
-- Migration logic:
--   Automatically copies existing user_id <-> topic_id links from the topics
--   table into the new subscriptions table.
-- =============================================================================

CREATE TABLE IF NOT EXISTS topic_subscriptions (
    id              uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id         uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic_id        uuid        NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    created_at      timestamptz DEFAULT now(),
    UNIQUE(user_id, topic_id)
);

-- Index for fast lookup of a user's subscriptions
CREATE INDEX IF NOT EXISTS idx_topic_subs_user_id
    ON topic_subscriptions (user_id);

-- Migrate existing topic owners to subscribers
INSERT INTO topic_subscriptions (user_id, topic_id)
SELECT user_id, id 
FROM topics 
WHERE user_id IS NOT NULL
ON CONFLICT (user_id, topic_id) DO NOTHING;

-- Note: We intentionally DO NOT drop the user_id column from the topics table
-- right now. It can serve as "original_creator_id" to prevent breaking older 
-- code that might still depend on it during the transition.
