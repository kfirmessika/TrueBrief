-- Migration 024: Add signal_prototype column to topics table.
-- This vector stores the learned "what high-signal looks like" for each topic.
-- Starts NULL (no pre-filtering on first scan). After each scan, facts scoring
-- >= 7 from the SignalScorer LLM update this prototype via EMA.
-- Dimension matches the current embedding provider (768 for BAAI/bge-base-en-v1.5
-- or Gemini text-embedding-004).

ALTER TABLE topics ADD COLUMN IF NOT EXISTS signal_prototype vector(768);
