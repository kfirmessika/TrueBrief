-- Migration 021: known_facts two-clock fields (architecture §4 / §8B).
--
-- V3 tracks two timestamps per fact:
--   event_date   — when the DEVELOPMENT happened (already present, extracted by LLM)
--   published_at — when the SOURCE ARTICLE was published (the reliable clock; can gate
--                  "new to us" vs "new to the world" checks in the delta engine)
--
-- date_basis records how trustworthy event_date is:
--   explicit  — the article stated an absolute date for this event
--   relative  — resolved from "yesterday / last week / Tuesday" against published_at
--   inferred  — weak guess; the article does not clearly date this event
--
-- importance is a 0-1 per-fact significance score emitted free by the harvester LLM
-- while it is already reading the article. Used to rank facts in the delta feed and
-- history timeline when event_class and verified_count are equal.
--
-- All three columns are nullable — rows inserted before this migration simply carry
-- NULL, which the application handles gracefully.

ALTER TABLE known_facts
    ADD COLUMN IF NOT EXISTS date_basis  VARCHAR(20)  DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS importance  FLOAT        DEFAULT NULL;
