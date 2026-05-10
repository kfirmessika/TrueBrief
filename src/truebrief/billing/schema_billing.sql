-- ============================================================
-- Step 3.4: user_subscriptions table
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New query)
-- ============================================================

CREATE TABLE IF NOT EXISTS user_subscriptions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL UNIQUE,              -- matches topics.user_id
    stripe_customer_id      TEXT UNIQUE,
    stripe_subscription_id  TEXT UNIQUE,
    tier                    TEXT NOT NULL DEFAULT 'free',      -- 'free' | 'pro' | 'power'
    status                  TEXT NOT NULL DEFAULT 'active',   -- 'active' | 'canceled' | 'past_due' | 'trialing'
    current_period_end      TIMESTAMP WITH TIME ZONE,
    created_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Auto-update updated_at on every write
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER user_subscriptions_updated_at
    BEFORE UPDATE ON user_subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Index for webhook lookups by Stripe customer ID
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_customer
    ON user_subscriptions (stripe_customer_id);

-- ============================================================
-- Webhook Idempotency: Track processed events to avoid double-writes
-- ============================================================
CREATE TABLE IF NOT EXISTS processed_stripe_events (
    event_id        TEXT PRIMARY KEY,
    event_type      TEXT NOT NULL,
    received_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Pruning index for event cleanup
CREATE INDEX IF NOT EXISTS idx_processed_events_time
    ON processed_stripe_events (received_at);
