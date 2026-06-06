-- Migration 008: Add Verifier trust-layer columns to known_facts
--
-- verified_count: number of independent source domains that reported a
--   fact sharing ≥1 entity within 7 days of this fact's event_date.
--   1 = only the original source (unconfirmed). ≥2 = cross-source confirmed.
--
-- verifier_flags: array of string labels from the Verifier stage:
--   "cross_source_confirmed" — ≥2 independent sources confirm this fact
--   "retrospective"          — event_date > 90 days before ingestion
--   "future_date"            — event_date > 7 days after ingestion
--   "ungrounded"             — LLM named entities that don't appear in source text

ALTER TABLE known_facts
  ADD COLUMN IF NOT EXISTS verified_count integer NOT NULL DEFAULT 0;

ALTER TABLE known_facts
  ADD COLUMN IF NOT EXISTS verifier_flags jsonb NOT NULL DEFAULT '[]'::jsonb;

-- Index to quickly find cross-source-confirmed facts per topic
CREATE INDEX IF NOT EXISTS idx_known_facts_verified_count
  ON known_facts (topic_id, verified_count DESC);

-- Verify
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name   = 'known_facts'
  AND column_name  IN ('verified_count', 'verifier_flags')
ORDER BY column_name;
