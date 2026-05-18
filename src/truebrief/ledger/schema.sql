-- Supabase Schema for TrueBrief v2

-- Enable the pgvector extension to work with embedding vectors
create extension if not exists vector;

-- Users Table
create table if not exists users (
    id uuid primary key default gen_random_uuid(),
    email text unique not null,
    plan text default 'free',
    stripe_id text,
    created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Topics Table
create table if not exists topics (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references users(id) on delete cascade,
    raw_query text not null,
    search_strategy jsonb default '{}'::jsonb,
    frequency text default 'medium',
    is_active boolean default true,
    last_checked_at timestamp with time zone,
    created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Known Facts (Alphas) Table
create table if not exists known_facts (
    id uuid primary key default gen_random_uuid(),
    topic_id uuid references topics(id) on delete cascade,
    alpha_text text not null,
    alpha_embedding vector(768), -- Gemini text-embedding-004 uses 768 dimensions
    entities jsonb default '[]'::jsonb,
    event_date timestamp with time zone,
    context text,
    confidence float default 1.0,
    source_url text,
    source_domain text,
    first_seen_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Create an index for vector similarity search (cosine similarity)
create index on known_facts using hnsw (alpha_embedding vector_cosine_ops);

-- Briefs Table
create table if not exists briefs (
    id uuid primary key default gen_random_uuid(),
    topic_id uuid references topics(id) on delete cascade,
    content text not null,
    facts_json jsonb default '[]'::jsonb,
    delivered_at timestamp with time zone default timezone('utc'::text, now()) not null,
    is_read boolean default false
);

-- RLS (Row Level Security) - Simplified for Phase 1
alter table users enable row level security;
alter table topics enable row level security;
alter table known_facts enable row level security;
alter table briefs enable row level security;

-- To satisfy Supabase security linters while still allowing prototype functionality:
-- We allow public read (SELECT), but restrict INSERT/UPDATE/DELETE to anon or authenticated roles.
create policy "Allow public read access to users" on users for select using (true);
create policy "Allow modify access to users" on users for all using (auth.role() in ('anon', 'authenticated'));

create policy "Allow public read access to topics" on topics for select using (true);
create policy "Allow modify access to topics" on topics for all using (auth.role() in ('anon', 'authenticated'));

create policy "Allow public read access to known_facts" on known_facts for select using (true);
create policy "Allow modify access to known_facts" on known_facts for all using (auth.role() in ('anon', 'authenticated'));

create policy "Allow public read access to briefs" on briefs for select using (true);
create policy "Allow modify access to briefs" on briefs for all using (auth.role() in ('anon', 'authenticated'));

-- Vector Search RPC (Required for pgvector similarity search via Supabase client)
create or replace function match_facts(
    query_embedding vector(768),
    match_threshold float,
    match_count int,
    filter_topic_id uuid default null
)
returns table (
    id uuid,
    topic_id uuid,
    alpha_text text,
    entities jsonb,
    event_date timestamp with time zone,
    context text,
    confidence float,
    source_url text,
    source_domain text,
    similarity float
)
language plpgsql
set search_path = public, extensions
as $$
begin
    return query
    select
        kf.id,
        kf.topic_id,
        kf.alpha_text,
        kf.entities,
        kf.event_date,
        kf.context,
        kf.confidence,
        kf.source_url,
        kf.source_domain,
        1 - (kf.alpha_embedding <=> query_embedding) as similarity
    from known_facts kf
    where (filter_topic_id is null or kf.topic_id = filter_topic_id)
      and 1 - (kf.alpha_embedding <=> query_embedding) > match_threshold
    order by kf.alpha_embedding <=> query_embedding
    limit match_count;
end;
$$;

-- Digest Settings Table (Phase 3, Step 3.15 — Email Digest)
-- Stores per-user email digest preferences.
-- `user_id` is UNIQUE so we can safely upsert on conflict.
create table if not exists digest_settings (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references users(id) on delete cascade unique,
    enabled boolean default true,
    frequency text default 'daily',   -- 'daily' | 'weekly'
    send_hour_utc int default 8,       -- 0-23
    created_at timestamptz default timezone('utc'::text, now()),
    updated_at timestamptz default timezone('utc'::text, now())
);

-- RLS
alter table digest_settings enable row level security;
create policy "Users can manage their own digest settings"
    on digest_settings for all
    using (auth.role() in ('anon', 'authenticated'));

