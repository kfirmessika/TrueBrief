-- Migration 021: Enable RLS on internal tables that were missing it.
--
-- All five tables are backend-only: every access goes through FastAPI using
-- the service-role key, which bypasses RLS. Enabling RLS with no policies
-- means the anon/authenticated roles can no longer read or modify these rows
-- directly (e.g. via the Supabase JS client with the anon key).
-- Service-role access is unaffected.
--
-- user_topic_state / history_docs: user-scoped data — must not be world-readable.
-- pipeline_trace / domain_extraction_stats / source_stats: internal telemetry.

ALTER TABLE public.pipeline_trace ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.domain_extraction_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.source_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.history_docs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_topic_state ENABLE ROW LEVEL SECURITY;
