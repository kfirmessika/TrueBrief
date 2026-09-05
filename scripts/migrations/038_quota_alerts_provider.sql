-- Migration 038: generalize quota_alerts beyond Gemini.
--
-- quota_alerts (migration 030) was built for Gemini's dual-key (primary/backup) rotation
-- only, and flag_quota_event() was only ever called from Gemini-429-shaped catch blocks in
-- llm/client.py. Once SEARCH_PROVIDER moved off "gemini" (Linkup live in production), every
-- OTHER provider's failure inside the same fallback chains (Linkup/Brave in
-- collector_search(), Groq's own fallback-of-last-resort in call(), OpenAI embeddings) stayed
-- completely silent -- a logger.warning with no persisted row and no push, so a break in the
-- actually-configured provider was invisible until every fallback also failed. This migration
-- adds a `provider` column and loosens the Gemini-only `key_type` check so the same
-- table/alert/push path can record and notify on a failure from any provider. Additive only:
-- no columns dropped, no rows lost, existing Gemini rows backfilled as provider='gemini'.
--
-- provider: which provider this event is about ('gemini' | 'linkup' | 'brave' | 'groq' |
--           'openai' | 'local'). Rows created before this migration predate the column and
--           are all Gemini events (backfilled below).
-- key_type: unchanged meaning for gemini ('primary' | 'backup' | 'rpm'); 'single' for a
--           one-key provider's own failure (Linkup/Brave/Groq/OpenAI have no primary/backup
--           rotation) or for a summary "every provider failed" event.

alter table quota_alerts add column if not exists provider text;
update quota_alerts set provider = 'gemini' where provider is null;
alter table quota_alerts alter column provider set default 'gemini';
alter table quota_alerts alter column provider set not null;

alter table quota_alerts drop constraint if exists quota_alerts_key_type_check;
alter table quota_alerts add constraint quota_alerts_key_type_check
    check (key_type in ('primary', 'backup', 'rpm', 'single'));

create index if not exists idx_quota_alerts_provider on quota_alerts (provider);

-- Verify
select id, created_at, severity, step_name, provider, model, key_type, notified
from quota_alerts
order by created_at desc
limit 10;
