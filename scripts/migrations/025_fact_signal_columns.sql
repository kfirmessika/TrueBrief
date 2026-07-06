-- Migration 025: Add signal scorer output columns to known_facts.
-- signal_score: 0-10 quality score from the SignalScorer LLM (NULL for pre-025 facts).
-- signal_class: STATE_CHANGE | ANNOUNCEMENT | REACTION | NOISE (NULL for pre-025 facts).
-- These let you query "why did this fact pass the gate?" directly from the DB
-- and spot patterns in what scores low but still passes (or scores high but is noise).

ALTER TABLE known_facts
  ADD COLUMN IF NOT EXISTS signal_score INTEGER,
  ADD COLUMN IF NOT EXISTS signal_class TEXT;
