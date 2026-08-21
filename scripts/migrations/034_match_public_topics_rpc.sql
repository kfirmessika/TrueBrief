-- RPC used by /shared-topics semantic search.
-- Returns public topics ordered by cosine similarity to the query embedding.
create or replace function match_public_topics(
  query_embedding vector(768),
  match_count int default 5
)
returns table (id uuid, similarity float)
language sql stable
as $$
  select
    id,
    1 - (topic_embedding <=> query_embedding) as similarity
  from topics
  where is_public = true
    and topic_embedding is not null
  order by topic_embedding <=> query_embedding
  limit match_count;
$$;
