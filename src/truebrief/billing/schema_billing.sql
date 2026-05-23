-- ============================================================
-- Billing schema — uses Paddle (not Stripe)
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New query)
-- ============================================================

CREATE TABLE IF NOT EXISTS user_subscriptions (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                  UUID NOT NULL UNIQUE,
    paddle_customer_id       TEXT UNIQUE,
    paddle_subscription_id   TEXT UNIQUE,
    tier                     TEXT NOT NULL DEFAULT 'free',     -- 'free' | 'pro' | 'power'
    status                   TEXT NOT NULL DEFAULT 'active',  -- 'active' | 'canceled' | 'past_due' | 'trialing'
    current_period_end       TIMESTAMP WITH TIME ZONE,
    created_at               TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at               TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

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

CREATE INDEX IF NOT EXISTS idx_user_subscriptions_paddle_customer
    ON user_subscriptions (paddle_customer_id);

-- ============================================================
-- Webhook idempotency
-- ============================================================
CREATE TABLE IF NOT EXISTS processed_paddle_events (
    event_id        TEXT PRIMARY KEY,
    event_type      TEXT NOT NULL,
    received_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_processed_paddle_events_time
    ON processed_paddle_events (received_at);
