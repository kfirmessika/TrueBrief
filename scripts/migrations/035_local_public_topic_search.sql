-- Migration 035: dedicated local vectors for public-topic autocomplete.
--
-- These vectors intentionally do NOT share a column with topic_embedding. The
-- latter stays in the configurable Gemini/OpenAI pipeline vector space, while
-- autocomplete uses the on-device BGE model for sub-second query embeddings.

ALTER TABLE public.topics
  ADD COLUMN IF NOT EXISTS topic_search_embedding vector(768);

CREATE INDEX IF NOT EXISTS topics_public_search_embedding_hnsw_idx
  ON public.topics USING hnsw (topic_search_embedding vector_cosine_ops)
  WHERE is_public = true AND topic_search_embedding IS NOT NULL;

CREATE OR REPLACE FUNCTION match_public_topics(
  query_embedding vector(768),
  match_count int DEFAULT 5
)
RETURNS TABLE (id uuid, similarity float)
LANGUAGE sql STABLE
AS $$
  SELECT
    id,
    1 - (topic_search_embedding <=> query_embedding) AS similarity
  FROM topics
  WHERE is_public = true
    AND topic_search_embedding IS NOT NULL
  ORDER BY topic_search_embedding <=> query_embedding
  LIMIT match_count;
$$;
