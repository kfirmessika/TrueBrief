-- Migration 026: Developer API product — API keys + daily usage metering.
--
-- api_keys: one row per issued key. Only the SHA-256 hash is stored; the full
--   key (tb_live_...) is shown to the user exactly once at creation time.
--   key_prefix keeps the first characters for display ("tb_live_Ab3d…").
--   Revocation is soft (revoked_at) so usage history survives.
--
-- api_usage_daily: one row per (key, day). Incremented atomically via the
--   increment_api_usage() function — supabase-py can't do count = count + 1.

CREATE TABLE IF NOT EXISTS api_keys (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name         TEXT NOT NULL DEFAULT 'default',
    key_hash     TEXT NOT NULL UNIQUE,          -- sha256 hex of the full key
    key_prefix   TEXT NOT NULL,                 -- e.g. 'tb_live_Ab3d' (display only)
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at TIMESTAMPTZ,
    revoked_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);

CREATE TABLE IF NOT EXISTS api_usage_daily (
    key_id     UUID NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
    user_id    UUID NOT NULL,
    day        DATE NOT NULL,
    count      INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (key_id, day)
);

CREATE INDEX IF NOT EXISTS idx_api_usage_user_day ON api_usage_daily(user_id, day);

-- Atomic increment of this key's daily counter; returns the USER's total
-- across all their keys for the day, so the tier quota is per-user (5 keys
-- must not mean 5x quota) and enforceable without a second round-trip.
CREATE OR REPLACE FUNCTION increment_api_usage(p_key_id UUID, p_user_id UUID, p_day DATE)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    user_total INTEGER;
BEGIN
    INSERT INTO api_usage_daily (key_id, user_id, day, count, updated_at)
    VALUES (p_key_id, p_user_id, p_day, 1, now())
    ON CONFLICT (key_id, day)
    DO UPDATE SET count = api_usage_daily.count + 1, updated_at = now();

    SELECT COALESCE(SUM(count), 0) INTO user_total
    FROM api_usage_daily
    WHERE user_id = p_user_id AND day = p_day;

    RETURN user_total;
END;
$$;

-- Internal tables: RLS on, no anon policies (service role bypasses RLS).
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_usage_daily ENABLE ROW LEVEL SECURITY;
