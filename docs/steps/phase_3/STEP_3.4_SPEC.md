# STEP SPEC — 3.4: Stripe Integration
> **Status:** [x] READY FOR BUILD | [ ] IN PROGRESS | [ ] VERIFIED
> **Mode:** BUILD (after this PLAN session)
> **Suggested Builder:** SON-AG (multi-file feature, clear spec, test wiring)
> **Planner:** Opus (this session)
> **Date Planned:** 2026-05-06

---

## 🎯 Objective
Ship a production-grade Stripe subscription flow — Checkout, Customer Portal, webhook-driven tier sync — that is **idempotent, signature-verified, and DB-mirrored**, then prove it end-to-end with the Stripe CLI in test mode and a unit-test suite that isolates the service from network calls.

This step does **not** enforce tier limits in the pipeline (that is Step 3.5). It only delivers the billing surface and the source-of-truth row in `user_subscriptions`.

---

## 📐 Design & Logic

### Pre-existing State (verified by Planner on 2026-05-06)
A previous session already scaffolded the integration. The following files exist and broadly match the blueprint:

| File | Status | Notes |
|------|--------|-------|
| `src/truebrief/billing/stripe_service.py` | ✅ Present | `StripeService` class with `create_checkout_session`, `create_portal_session`, `get_subscription`, `handle_webhook` |
| `src/truebrief/billing/billing_routes.py` | ✅ Present | `/tiers`, `/checkout`, `/portal`, `/webhook`, `/status/{user_id}` |
| `src/truebrief/billing/schema_billing.sql` | ✅ Present | `user_subscriptions` table + `updated_at` trigger |
| `src/truebrief/billing/__init__.py` | ✅ Empty (intentional) | |
| `config/settings.py` | ✅ Present | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_POWER` |
| `src/truebrief/models/tier.py` | ✅ Present | `Tier`, `TierLimits`, `TIER_LIMITS` |
| `src/truebrief/api/server.py` | ✅ Wired | `billing_router` mounted at `/api/v1/billing` |

### Gap List (what BUILD must close)

1. **Schema not yet applied to Supabase.** `schema_billing.sql` lives on disk but no migration step has run it. Builder must apply it via the Supabase SQL editor (manual) or extend `src/truebrief/ledger/apply_schema.py`.
2. **Webhook idempotency missing.** `_sync_subscription` will re-write the same row on duplicate event delivery. Stripe retries. Add a `processed_stripe_events` table (id PK = event.id) and short-circuit on duplicate.
3. **`current_period_end` retrieval is API-version-fragile.** Modern Stripe API moves this onto the line item, not the subscription root. Add a defensive lookup that tries `sub["current_period_end"]` then `sub["items"]["data"][0]["current_period_end"]`.
4. **No unit tests exist.** Required: `tests/test_billing.py` covering `_price_to_tier`, `_sync_subscription`, `_cancel_subscription`, `_mark_past_due`, `handle_webhook` signature failure path, and a `create_checkout_session` happy path with the Stripe SDK fully mocked.
5. **No integration recipe documented.** Builder must add a short runbook (`docs/runbooks/STRIPE_TESTING.md`) showing exactly how to drive `stripe listen` + `stripe trigger` against the local FastAPI server, and how to record the resulting `whsec_…` into `.env`.
6. **`success_url` / `cancel_url` are caller-supplied.** Acceptable now; document that for the eventual frontend integration.
7. **Tier source mismatch (cross-step).** `models/tier.py` says Free has only `["rss"]`; blueprint says `["rss", "tavily"]`. Do **not** change here — flagged for Step 3.5 (Tier Enforcement) to reconcile.

### Webhook Event Coverage
| Event | Action |
|-------|--------|
| `checkout.session.completed` | Log only — subscription event will follow |
| `customer.subscription.created` | Upsert row, set tier from price ID, status from Stripe |
| `customer.subscription.updated` | Upsert (covers plan changes, renewals) |
| `customer.subscription.deleted` | Set tier=free, status=canceled, null subscription_id |
| `invoice.payment_failed` | Status → `past_due` (still active until canceled) |

### Idempotency Pattern (new)
```sql
CREATE TABLE IF NOT EXISTS processed_stripe_events (
    event_id   TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    received_at TIMESTAMPTZ DEFAULT NOW()
);
```
```python
def handle_webhook(self, payload, sig_header):
    event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    if self._already_processed(event["id"]):
        return  # short-circuit, return 200 to Stripe
    self._record_event(event["id"], event["type"])
    # …existing dispatch…
```

### Logical Flow (Checkout happy path)
```
[Frontend]                  [API]                            [Stripe]              [Supabase]
   |                           |                                |                       |
   |-- POST /billing/checkout->|                                |                       |
   |                           |-- _get_customer_id ----------->|                       |
   |                           |   (SELECT user_subscriptions)----------------------->[ ]
   |                           |-- stripe.Customer.create ----->|                       |
   |                           |<------- customer_id -----------|                       |
   |                           |-- upsert user_subscriptions ---|---------------------->|
   |                           |-- stripe.checkout.Session.create -------->|            |
   |                           |<------- session.url ------------|                       |
   |<------ checkout_url ------|                                |                       |
   |                                                            |                       |
   |-- (user pays via Stripe page) ---------------------------->|                       |
   |                                                            |-- POST /billing/webhook->|
   |                                                            |   customer.subscription.created
   |                           |<-------- raw payload + sig ---|                       |
   |                           |-- construct_event (verifies signature)                  |
   |                           |-- _already_processed? no                                |
   |                           |-- _record_event                                         |
   |                           |-- _sync_subscription -> upsert tier=pro, status=active->|
   |                           |-- 200 OK ---------------------->|                       |
```

---

## 📂 File GPS

**Reads:**
- `src/truebrief/billing/stripe_service.py` (existing — to extend)
- `src/truebrief/billing/billing_routes.py` (existing — minor edits if any)
- `src/truebrief/billing/schema_billing.sql` (existing — extend)
- `src/truebrief/models/tier.py`
- `config/settings.py`
- `src/truebrief/ledger/database.py`
- `src/truebrief/ledger/apply_schema.py`

**Touches:**
- `src/truebrief/billing/stripe_service.py` (Modify — idempotency, period_end fix)
- `src/truebrief/billing/schema_billing.sql` (Modify — add `processed_stripe_events`)
- `tests/test_billing.py` (Create — full unit suite, all Stripe SDK mocked)
- `docs/runbooks/STRIPE_TESTING.md` (Create — Stripe CLI workflow)
- `src/truebrief/ledger/apply_schema.py` (Modify — include billing schema if it doesn't already)
- `.env.example` (Create or Modify — add `STRIPE_*` placeholders so devs know)

**Do NOT touch this step (deferred to 3.5):**
- `src/truebrief/api/routes.py` (tier enforcement at topic-create lives in 3.5)
- `src/truebrief/pipeline/runner.py` (source-tier filtering in 3.5)
- `src/truebrief/models/tier.py` source list (3.5 reconciles with blueprint)

---

## 🛠 Execution Steps

1. [ ] **Apply DB migration.** Extend `schema_billing.sql` with `processed_stripe_events`. Run it via `apply_schema.py` (or document the manual Supabase-dashboard path if `apply_schema.py` is not wired for billing yet).
2. [ ] **Add idempotency.** In `stripe_service.py`, add `_already_processed(event_id)` and `_record_event(event_id, event_type)` methods. Wire them at the top of `handle_webhook` after signature verification.
3. [ ] **Defensive `current_period_end`.** Add a `_extract_period_end(sub)` helper that checks both root and items[0]; use it in `_sync_subscription`.
4. [ ] **Webhook unit tests.** Mock `stripe.Webhook.construct_event` and `self._db()`. Cover: bad signature → `ValueError`; duplicate event → no DB write; created → upsert pro tier; deleted → row downgraded; payment_failed → status=past_due.
5. [ ] **Service unit tests.** Mock `stripe.Customer.create`, `stripe.checkout.Session.create`, `stripe.billing_portal.Session.create`. Verify customer reuse path (existing `stripe_customer_id`) vs first-time path.
6. [ ] **Stripe CLI runbook.** `docs/runbooks/STRIPE_TESTING.md` — install steps, `stripe login`, `stripe listen --forward-to localhost:8000/api/v1/billing/webhook`, `stripe trigger customer.subscription.created`. Show how to read the `whsec_…` and put it in `.env`.
7. [ ] **`.env.example`.** Add `STRIPE_SECRET_KEY=sk_test_…`, `STRIPE_WEBHOOK_SECRET=whsec_…`, `STRIPE_PRICE_PRO=price_…`, `STRIPE_PRICE_POWER=price_…` placeholders.
8. [ ] **Manual end-to-end smoke (test mode).** Run server, run `stripe listen`, hit `POST /api/v1/billing/checkout` with a real test user_id + email, complete checkout with `4242 4242 4242 4242`, confirm `user_subscriptions.tier='pro'` row appears in Supabase.
9. [ ] **Update blueprint/roadmap status to `[x]`** for 3.4 once smoke passes.

---

## ✅ Testing & Verification

### Unit Tests (`tests/test_billing.py`)
- [ ] `test_price_to_tier_pro` — known PRO price ID maps to `Tier.PRO`
- [ ] `test_price_to_tier_power` — known POWER price ID maps to `Tier.POWER`
- [ ] `test_price_to_tier_unknown_falls_back_to_free`
- [ ] `test_create_checkout_first_time_creates_customer` — `stripe.Customer.create` called once, row upserted
- [ ] `test_create_checkout_reuses_existing_customer` — `stripe.Customer.create` NOT called when row already has `stripe_customer_id`
- [ ] `test_create_portal_raises_when_no_customer`
- [ ] `test_webhook_bad_signature_raises_value_error`
- [ ] `test_webhook_duplicate_event_short_circuits` — second delivery of same event_id triggers no DB write
- [ ] `test_webhook_subscription_created_upserts_row_with_pro_tier`
- [ ] `test_webhook_subscription_deleted_downgrades_to_free`
- [ ] `test_webhook_payment_failed_marks_past_due`
- [ ] `test_extract_period_end_root_path`
- [ ] `test_extract_period_end_item_path`

### Integration Check
- [ ] `stripe listen --forward-to localhost:8000/api/v1/billing/webhook` shows `200 OK` for at least one `customer.subscription.created` event.
- [ ] After completing a test-mode Stripe Checkout with the test card `4242 4242 4242 4242`, query Supabase: `SELECT tier, status FROM user_subscriptions WHERE user_id = '<test_user_id>'` returns `pro / active`.
- [ ] `GET /api/v1/billing/status/<test_user_id>` returns matching tier and limits.
- [ ] `stripe trigger customer.subscription.deleted` flips the row to `tier=free, status=canceled` within 5 s.
- [ ] Replay the same `customer.subscription.created` event a second time via `stripe events resend <evt_…>` → no second row write (idempotency proven).

### Acceptance Criteria (from blueprint, restated)
- [ ] User clicks "Upgrade" → Stripe Checkout opens (verified via curl + browser)
- [ ] Successful payment → `users.plan` (i.e. `user_subscriptions.tier`) updated to `pro` within 30 s
- [ ] Cancellation → user downgraded to `free` at period end
- [ ] Billing portal link works

---

## 📝 Planner Notes

**Why partial-build was found:** A previous session shipped most of the surface but did not write tests, did not apply the schema, and did not handle webhook duplicates. That is the realistic shape of "code exists, but nothing proves it works in production." The BUILD session must close those three gaps before it can claim 3.4 is done.

**Stripe API-version drift risk:** Stripe periodically restructures `Subscription` payloads. The `_extract_period_end` helper is the cheap insurance. If a smoke test ever sees `period_end` come back `None`, that helper is the first place to look.

**Webhook security note:** The route already uses `request.body()` (raw bytes) before signature verification — correct. Do **not** let any framework middleware parse JSON ahead of `construct_event`, or signatures will silently break.

**Idempotency implementation hint:** Use `INSERT … ON CONFLICT (event_id) DO NOTHING` returning the row count to atomically detect duplicates without a separate SELECT.

**Out of scope reminders:**
- Tier enforcement at API surface → Step 3.5
- Frontend buy-button → Step 3.6+
- Email receipts customization → not planned (Stripe defaults are fine)

**Model recommendation for BUILD:** Sonnet Agent (SON-AG). The spec is concrete, the surface is well-defined, and the work is mostly mechanical: schema add, helper add, test file. No design judgment required.

**Estimated BUILD time:** 60–90 minutes (with Stripe CLI smoke).
