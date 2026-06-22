-- Migration 019: user_topic_state — the per-user delta engine (architecture §8, §4).
--
-- Enables personalized "what's new since you looked" feeds for FREE on shared topics:
-- the feed is just  facts WHERE first_seen_at > last_seen_at, per (user, topic).
-- Two markers, ONE feed (§8/§13):
--   last_seen_at   → the LIVE window ("● 2 new since you looked")
--   last_digest_at → the DIGEST window ("your daily summary since yesterday")
-- They never contradict because reading always advances last_seen_at.
--
-- muted_thread_ids is reserved for when the story-graph is un-paused (§7); unused now.
--
-- Defaults to NOW() so a brand-new subscription doesn't dump the whole backlog as
-- "new" — the backlog lives in the History timeline (§7.2), the feed shows what
-- arrived after you started watching. Missing rows are treated by the engine as a
-- short look-back window (see delta_engine.DEFAULT_WINDOW_HOURS).

CREATE TABLE IF NOT EXISTS user_topic_state (
    user_id          UUID        NOT NULL,
    topic_id         UUID        NOT NULL,
    last_seen_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_digest_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    muted_thread_ids JSONB       NOT NULL DEFAULT '[]'::jsonb,
    PRIMARY KEY (user_id, topic_id)
);

-- Fast lookup of a user's whole feed state in one query.
CREATE INDEX IF NOT EXISTS idx_user_topic_state_user ON user_topic_state (user_id);
