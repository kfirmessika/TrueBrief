-- Migration 015: contradiction flag on known_facts (IC4 — architecture §5/§8B)
--
-- When a NEW fact contradicts an existing fact (same actors + overlapping time,
-- incompatible value — e.g. Strait of Hormuz "closed" vs "open", death toll
-- 3,912 vs 3,468), we store the new fact but flag the pair rather than letting
-- two contradictory facts sit side-by-side as if both were settled truth.
--
--   contradicts_id    → the known_facts.id this fact contradicts
--   contradiction_note→ short human-readable reason ("status conflict: 'closed' vs 'open'")
--
-- Safe on existing rows: NULL means "no contradiction". The arbiter write degrades
-- to a no-op if this migration hasn't been applied.

ALTER TABLE known_facts
    ADD COLUMN IF NOT EXISTS contradicts_id     uuid DEFAULT NULL REFERENCES known_facts(id) ON DELETE SET NULL;

ALTER TABLE known_facts
    ADD COLUMN IF NOT EXISTS contradiction_note text DEFAULT NULL;

CREATE INDEX IF NOT EXISTS known_facts_contradicts_idx
    ON known_facts (topic_id)
    WHERE contradicts_id IS NOT NULL;
