-- Migration 022: Topic embedding + per-fact relevance score
--
-- topic_embedding: embed raw_query once at topic creation, stored for reuse.
-- relevance: cosine similarity between fact and topic embedding, computed at
--            fact-store time by the pipeline. Zero runtime cost at serve time.

ALTER TABLE public.topics
  ADD COLUMN IF NOT EXISTS topic_embedding vector(768);

ALTER TABLE public.known_facts
  ADD COLUMN IF NOT EXISTS relevance float;
