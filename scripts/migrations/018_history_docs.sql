-- Migration 018: history_docs — the V3 context layer (architecture §7.2, §4).
--
-- The "story so far": the topic's full timeline, assembled with ZERO LLM by placing
-- the already-clean fact-sentences in chronological order. This replaces the paused
-- story-graph as the context layer (§7) and powers the in-app History view.
--
--   doc shape (structured, no-LLM-first):
--   {
--     "built_at": "2026-06-22T...",
--     "fact_count": 42,
--     "timeline": [
--       { "date": "2026-06-21",
--         "facts": [ { "text","context","event_class","source_domain","source_url",
--                      "verified_count","contradiction_note","event_date","first_seen_at" }, ... ] },
--       ...
--     ]
--   }
--
-- One row per topic. Rebuilt by the pipeline after facts land (fire-and-forget) and/or
-- on-read by the API. Safe to leave unapplied: the API falls back to a live build and
-- the pipeline write degrades to a no-op.

CREATE TABLE IF NOT EXISTS history_docs (
    topic_id      UUID PRIMARY KEY,
    doc           JSONB       NOT NULL DEFAULT '{}'::jsonb,
    fact_count    INT         NOT NULL DEFAULT 0,
    last_built_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
