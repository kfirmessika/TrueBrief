-- Migrate auth from Clerk to Supabase Auth.
--
-- users.id (UUID) is this app's OWN identity and is what every other table
-- references (topic_subscriptions.user_id, user_subscriptions.user_id, ...),
-- so nothing downstream changes. clerk_id was only ever the external-provider
-- handle; auth_uid replaces it with the Supabase auth.users.id.
--
-- clerk_id is kept and made nullable so a rollback is possible without
-- restoring a backup.

ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_uid UUID;
ALTER TABLE users ALTER COLUMN clerk_id DROP NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_auth_uid ON users(auth_uid);

-- Adoption path: on first Supabase login, an existing row with a matching
-- email and a NULL auth_uid is claimed rather than duplicated, so the
-- pre-migration account keeps its topics. See auth/user_repo.py.
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
