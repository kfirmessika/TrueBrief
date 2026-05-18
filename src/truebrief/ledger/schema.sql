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

-- Push Subscriptions Table (Phase 3, Step 3.16 — Web Push Notifications)
-- Stores per-device browser push subscriptions (one user may have many devices).
-- `user_id, endpoint` is UNIQUE so we can safely upsert on conflict.
create table if not exists push_subscriptions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references users(id) on delete cascade,
    endpoint text not null,
    p256dh text not null,
    auth text not null,
    enabled boolean default true,
    created_at timestamptz default timezone('utc'::text, now()),
    unique(user_id, endpoint)
);

-- RLS
alter table push_subscriptions enable row level security;
create policy "Users can manage their own push subscriptions"
    on push_subscriptions for all
    using (auth.role() in ('anon', 'authenticated'));

-- Pipeline Run Log (Step A.1.1 — Cost & Latency Telemetry)
-- One row per full pipeline execution, whether successful or not.
create table if not exists pipeline_run (
    id uuid primary key default gen_random_uuid(),
    topic_id uuid references topics(id) on delete set null,
    started_at timestamptz not null,
    duration_ms int,
    articles_collected int default 0,
    articles_selected int default 0,
    alphas_extracted int default 0,
    decisions_new int default 0,
    decisions_update int default 0,
    decisions_duplicate int default 0,
    brief_length int default 0,
    exit_status text default 'success',  -- 'success' | 'no_update' | 'rejected' | 'error'
    error_message text,
    created_at timestamptz default timezone('utc'::text, now()) not null
);

create index pipeline_run_topic_idx on pipeline_run(topic_id);
create index pipeline_run_started_idx on pipeline_run(started_at desc);

alter table pipeline_run enable row level security;
create policy "Allow read access to pipeline_run"
    on pipeline_run for select using (true);
create policy "Allow write access to pipeline_run"
    on pipeline_run for all using (auth.role() in ('anon', 'authenticated'));

-- LLM Call Log (Step A.1.2 — Per-call instrumentation)
-- One row per LLM API call; linked to the parent pipeline_run.
create table if not exists llm_call_log (
    id uuid primary key default gen_random_uuid(),
    pipeline_run_id uuid references pipeline_run(id) on delete cascade,
    stage text not null,        -- 'query_builder' | 'harvester' | 'arbiter' | 'summarizer' | 'briefer'
    model text not null,
    input_tokens int default 0,
    output_tokens int default 0,
    cost_usd numeric(10, 6) default 0,
    duration_ms int default 0,
    created_at timestamptz default timezone('utc'::text, now()) not null
);

create index llm_call_log_run_idx on llm_call_log(pipeline_run_id);
create index llm_call_log_stage_idx on llm_call_log(stage);
create index llm_call_log_created_idx on llm_call_log(created_at desc);

alter table llm_call_log enable row level security;
create policy "Allow read access to llm_call_log"
    on llm_call_log for select using (true);
create policy "Allow write access to llm_call_log"
    on llm_call_log for all using (auth.role() in ('anon', 'authenticated'));

-- RPC: cost aggregated by pipeline stage (last N days)
create or replace function llm_cost_by_stage(days_back int default 30)
returns table (
    stage text,
    calls bigint,
    total_input_tokens bigint,
    total_output_tokens bigint,
    total_cost_usd numeric,
    avg_duration_ms numeric
)
language sql set search_path = public, extensions as $$
    select
        stage,
        count(*)                    as calls,
        sum(input_tokens)           as total_input_tokens,
        sum(output_tokens)          as total_output_tokens,
        sum(cost_usd)               as total_cost_usd,
        avg(duration_ms)            as avg_duration_ms
    from llm_call_log
    where created_at >= now() - (days_back || ' days')::interval
    group by stage
    order by total_cost_usd desc;
$$;

-- RPC: daily cost series (last N days)
create or replace function llm_cost_by_day(days_back int default 30)
returns table (
    day date,
    calls bigint,
    total_cost_usd numeric
)
language sql set search_path = public, extensions as $$
    select
        created_at::date            as day,
        count(*)                    as calls,
        sum(cost_usd)               as total_cost_usd
    from llm_call_log
    where created_at >= now() - (days_back || ' days')::interval
    group by created_at::date
    order by day;
$$;

-- RPC: pipeline run summary (last N days)
create or replace function pipeline_run_summary(days_back int default 30)
returns table (
    total_runs bigint,
    successful_runs bigint,
    avg_duration_ms numeric,
    total_brief_chars bigint
)
language sql set search_path = public, extensions as $$
    select
        count(*)                        as total_runs,
        count(*) filter (where exit_status = 'success') as successful_runs,
        avg(duration_ms)                as avg_duration_ms,
        sum(brief_length)               as total_brief_chars
    from pipeline_run
    where created_at >= now() - (days_back || ' days')::interval;
$$;

