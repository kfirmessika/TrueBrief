-- Migration 030: quota_alerts table + persist RPC-free direct-insert support.
--
-- Real-time Gemini quota-exhaustion alerting (2026-08-12). Founder was blind to quota
-- exhaustion until a downstream symptom surfaced (live incident: primary key hit its
-- 20/day grounding cap, backup key permanently 404s "model no longer available" for the
-- same model — both keys dead, pipeline silently degrading/failing). This table is the
-- audit trail: every flag event persists here even if the accompanying push notification
-- fails to deliver. See src/truebrief/ledger/quota_alerts.py for the write path and
-- GET /admin/quota-alerts for the read path.
--
-- severity: 'yellow' = primary key quota-exhausted, falling back to backup key.
--           'red'    = backup key ALSO failed right after a primary quota failure (both
--                      exhausted, or backup errored for any reason, or fell through to
--                      an expensive last-resort like Groq) — this call is now degraded
--                      or failing entirely.
-- key_type: which key the *this row's* failure happened on ('primary' | 'backup').

create table if not exists quota_alerts (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default timezone('utc'::text, now()),
    severity text not null check (severity in ('yellow', 'red')),
    step_name text not null,
    model text not null,
    key_type text not null check (key_type in ('primary', 'backup')),
    error_detail text,
    notified boolean not null default false
);

create index if not exists idx_quota_alerts_created_at on quota_alerts (created_at desc);
create index if not exists idx_quota_alerts_severity on quota_alerts (severity);

-- RLS: internal telemetry table, no end-user access — same pattern as llm_call_log /
-- pipeline_run (server uses the service-role key via get_supabase(), which bypasses RLS).
alter table quota_alerts enable row level security;

-- Verify
select id, created_at, severity, step_name, model, key_type, notified
from quota_alerts
order by created_at desc
limit 10;
