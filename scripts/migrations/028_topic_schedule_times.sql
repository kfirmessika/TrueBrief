-- Migration 028: manual alarm-clock scheduling (docs/core/architecture_v5.md §7)
--
-- Replaces AYR's adaptive poll_interval_seconds with explicit, user-set daily run
-- times (UTC hour:minute). A topic with zero rows here defaults to one run/day at a
-- fixed default time (handled in code — ledger/alarm_schedule.py — so the default can
-- change without a data migration). Users add as many times as their tier's minimum
-- spacing (models/tier.py TIER_LIMITS.min_interval_hours) allows.

create table if not exists topic_schedule_times (
    id uuid primary key default gen_random_uuid(),
    topic_id uuid not null references topics(id) on delete cascade,
    hour smallint not null check (hour >= 0 and hour <= 23),
    minute smallint not null default 0 check (minute >= 0 and minute <= 59),
    created_at timestamptz default timezone('utc'::text, now()) not null,
    unique (topic_id, hour, minute)
);

create index if not exists topic_schedule_times_topic_idx on topic_schedule_times(topic_id);

alter table topic_schedule_times enable row level security;

drop policy if exists "Allow read access to topic_schedule_times" on topic_schedule_times;
create policy "Allow read access to topic_schedule_times"
    on topic_schedule_times for select using (true);

drop policy if exists "Allow write access to topic_schedule_times" on topic_schedule_times;
create policy "Allow write access to topic_schedule_times"
    on topic_schedule_times for all using (auth.role() in ('anon', 'authenticated'));
