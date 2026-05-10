# Runbook: Stripe Integration Testing

This guide shows how to test the billing flow locally using the Stripe CLI.

## Prerequisites
1. [Stripe CLI installed](https://stripe.com/docs/stripe-cli)
2. `stripe login` executed and authenticated.

## 1. Start Stripe Port Forwarding
Run this in a dedicated terminal to forward Stripe events to your local FastAPI server:
```bash
stripe listen --forward-to localhost:8000/api/v1/billing/webhook
```
**Important:** Look for the "Webhook signing secret" (starts with `whsec_`). Copy this into your `.env` as `STRIPE_WEBHOOK_SECRET`.

## 2. Trigger Events
You can simulate specific lifecycle events to verify DB mirroring:

### Test Subscription Creation
```bash
stripe trigger customer.subscription.created
```
Check Supabase `user_subscriptions` table for a new row (or update to an existing one).

### Test Cancellation
```bash
stripe trigger customer.subscription.deleted
```
Verify the tier flips to `free` and status to `canceled`.

### Test Payment Failure
```bash
stripe trigger invoice.payment_failed
```
Verify status flips to `past_due`.

## 3. Manual E2E Flow
1. Start your FastAPI server: `python src/truebrief/main.py`
2. Create a Checkout Session via curl or Postman:
   ```bash
   curl -X POST http://localhost:8000/api/v1/billing/checkout \
     -H "Content-Type: application/json" \
     -d '{
       "user_id": "YOUR_UUID",
       "email": "test@example.com",
       "tier": "pro",
       "success_url": "http://localhost:8000/success",
       "cancel_url": "http://localhost:8000/cancel"
     }'
   ```
3. Open the `checkout_url` from the response in your browser.
4. Use a test card (e.g., `4242 4242 4242 4242`, any CVC/date).
5. After payment, verify the `user_subscriptions` table in Supabase.

## 4. Idempotency Check
Resend an event via the Stripe Dashboard (Test Mode) or CLI to ensure no duplicate writes:
```bash
stripe events resend <evt_id>
```
Your logs should show: `Stripe event evt_... already processed, skipping.`
