-- Migration 036: past-due grace clock for subscriptions.
--
-- A failed payment used to set user_subscriptions.status = 'past_due' but leave
-- `tier` untouched, and every enforcement site read only `tier` — so a lapsed or
-- refunded customer kept full paid access until Paddle's own dunning finished
-- (days to weeks later). billing/tiers.resolve_effective_tier() now downgrades a
-- past-due subscription to free once this timestamp is older than
-- settings.PADDLE_PAST_DUE_GRACE_DAYS. Enforced on read — no scheduled job.
--
-- Idempotent.

ALTER TABLE public.user_subscriptions
  ADD COLUMN IF NOT EXISTS past_due_since timestamptz;

COMMENT ON COLUMN public.user_subscriptions.past_due_since IS
  'When the current past-due lapse began (first transaction.payment_failed). '
  'NULL when the subscription is in good standing. Grace window is '
  'PADDLE_PAST_DUE_GRACE_DAYS from this instant.';
