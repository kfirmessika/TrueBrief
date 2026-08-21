-- 033_fix_anon_crud_rls_hole.sql
--
-- SECURITY FIX — PRE-LAUNCH BLOCKER. Verified exploitable against production
-- on 2026-08-20 using only the publishable anon key that ships to every browser.
--
-- THE HOLE
-- Five tables holding user data had RLS *enabled* but neutralized by 13 policies
-- that carry no ownership check at all -- either `USING (true)` or merely
-- `auth.role() IN ('anon','authenticated')` -- combined with anon/authenticated
-- table GRANTs. Net effect: any anonymous visitor could SELECT / UPDATE / DELETE
-- every user's rows straight through PostgREST, no login required.
--
-- Confirmed live before this migration:
--   GET    /rest/v1/topics                -> 200, 7 rows, ALL of them is_public=false
--   GET    /rest/v1/known_facts           -> 200, 200 rows
--   GET    /rest/v1/briefs                -> 200
--   GET    /rest/v1/story_nodes           -> 200, 21 rows
--   PATCH  + DELETE on all five           -> 200 (writes permitted)
-- `users` and `user_subscriptions` were already safe (RLS on, no policy = DENY).
--
-- WHY A FLAT DENY IS THE RIGHT FIX (not owner-scoped policies)
-- Nothing legitimately reaches these tables as anon/authenticated:
--   * the frontend uses supabase-js ONLY for auth (signInWithIdToken, getClaims).
--     `grep -rn "\.from(" frontend/src` returns no table access at all.
--   * the backend talks to Postgres with the service-role key, which bypasses RLS
--     entirely, so none of its queries are affected by this change.
-- That makes RLS-enabled-with-no-policy (default DENY) both sufficient and the
-- lowest-risk option -- and it matches how the other 15 tables are already set up.
-- Owner-scoped policies would add a second, untested authorization surface for
-- a code path that no longer exists.
--
-- ROLLBACK: re-granting is a one-liner, but do NOT restore the old policies --
-- they are the vulnerability. If direct client reads are ever needed, write
-- owner-scoped policies keyed on topic_subscriptions.

DO $$
DECLARE
  t text;
  p text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'topics', 'known_facts', 'briefs', 'story_nodes', 'topic_schedule_times'
  ]
  LOOP
    -- drop every existing policy on the table by name (they are all permissive)
    FOR p IN
      SELECT policyname FROM pg_policies
      WHERE schemaname = 'public' AND tablename = t
    LOOP
      EXECUTE format('DROP POLICY %I ON public.%I', p, t);
    END LOOP;

    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('REVOKE ALL ON public.%I FROM anon, authenticated', t);
  END LOOP;
END $$;

-- VERIFY (expect zero rows from both):
--   SELECT tablename, policyname FROM pg_policies
--    WHERE schemaname='public'
--      AND tablename IN ('topics','known_facts','briefs','story_nodes','topic_schedule_times');
--
--   SELECT table_name, grantee, privilege_type
--     FROM information_schema.role_table_grants
--    WHERE table_schema='public' AND grantee IN ('anon','authenticated')
--      AND table_name IN ('topics','known_facts','briefs','story_nodes','topic_schedule_times');
--
-- Then re-run the external probe -- every one of these must return 401 or an empty set:
--   curl -s "$SUPABASE_URL/rest/v1/topics?select=*" -H "apikey: $ANON" -H "Authorization: Bearer $ANON"
