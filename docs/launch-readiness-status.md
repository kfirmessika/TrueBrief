# Launch Readiness — live status

Tracks the plan in the "TrueBrief Launch Readiness" artifact (audit 2026-08-20).
Updated 2026-09-02.

## Deploy state
- **Backend (api / Worker / Beat):** deploying fine from `main`.
- **Frontend:** deploy pipeline was broken Aug 28 – Sep 2 (root cause: `frontend/railway.toml`
  hardcoded `healthcheckPath = "/"`, which returns a 307). Fixed in `bd76207` → `/api/health`.
  First green frontend deploy since Aug 27.

## Commits waiting to be pushed
`git push origin main` deploys these:
- `bd76207` — frontend healthcheck fix (already pushed / deployed)
- `5ee7826` — per-account scan cap + global spend circuit-breaker + admin section gate
- `6f813d3` — API-docs switch, past-due grace + refund webhooks, `/pricing`, telemetry retention, auth fan-out cache

## Migrations to apply (Supabase SQL editor, in order)
- `026_api_keys.sql` — pre-existing, never applied. Developer API 500s without it.
- `035_local_public_topic_search.sql`
- `036_billing_past_due_grace.sql`
- `037_retention_and_indexes.sql`

## Gate 0 — Stop the bleeding
- [x] RLS migration `033` applied + re-tested
- [x] Backend security fixes deployed
- [x] Frontend deploy fixed & green
- [ ] **YOU: rotate the Supabase service-role key** (anon key had write access for an unknown window)

## Gate 1 — Free-tier launch
- [x] Public API docs — code now gated on `ENABLE_API_DOCS` (default off). **YOU: after deploy,
      confirm `/docs` on the api service returns 404.** (No longer needs the `ENV` flip.)
- [x] Logging split
- [x] Per-account daily scan cap (Redis counter; free 25 / pro 200 / power ∞) + global daily
      spend circuit-breaker (`GLOBAL_DAILY_SPEND_CEILING_USD`, default $25)
- [x] Dead `/history` nav link + `/admin/compare` — already removed; `/admin/*` now client-gated too
- [ ] **YOU: set `GLOBAL_DAILY_SPEND_CEILING_USD`** on Railway (api + Worker) to your real budget, or leave the $25 default
- [ ] **YOU: walk the whole product on a real phone** (checklist in the artifact)
- [ ] **YOU: landing-page decision** — seed 2-3 public topics via `/admin/topics`, or build a real landing page

## Gate 2 — Switch on payments
- [x] Webhook fail-closed on empty secret (already in prod)
- [x] Past-due grace policy (`PADDLE_PAST_DUE_GRACE_DAYS`, default 3) enforced via `resolve_effective_tier`
- [x] Refund / chargeback handling (`adjustment.created` → downgrade + error-log)
- [x] `/pricing` page + prices on upgrade buttons + past-due banner in settings
- [x] Developer API degrades gracefully until migration 026 is applied
- [x] Resend added to the privacy policy processor list
- [ ] **YOU: set all four Paddle vars in one pass** on the Railway api service:
      `PADDLE_API_KEY`, `PADDLE_WEBHOOK_SECRET`, `PADDLE_PRICE_PRO`, `PADDLE_PRICE_POWER`
- [ ] **YOU: set `PRICE_PRO_USD` / `PRICE_POWER_USD`** to match the real Paddle amounts (else no price shows)
- [ ] **YOU: apply migration `026`** (or leave the Developer API showing "being set up")
- [ ] **YOU: add `RESEND_API_KEY`** to the api service
- [ ] **YOU: with `ENV=production`, Paddle hits the LIVE API** — for sandbox testing either
      set `ENV=development` temporarily or do a small real purchase
- [ ] **YOU: run one real sandbox purchase + one cancellation**, verify tier flips both ways

## Gate 3 — Survive growth
- [x] Retention on `llm_call_log` payloads + `pipeline_trace` (Celery beat, migration 037 RPCs)
- [x] Missing FK indexes + duplicate embedding index drop (migration 037)
- [x] Request fan-out — `get_or_create_user` Redis cache + throttled `last_seen_at`
- [ ] **Backend dependency upgrade** (`pyjwt`, `cryptography`, `aiohttp`, `starlette`) — deferred,
      needs its own session with a full test pass (sits under token verification)
- [ ] **YOU: add uptime monitoring + error alerting** (e.g. UptimeRobot on `/health` + Sentry;
      `SENTRY_DSN` wiring not yet added)
- [ ] **YOU: confirm the Supabase backup retention window** in the dashboard
- [ ] **YOU: delete the dead Stripe Railway service + remove leftover `CLERK_*` vars** from api +
      frontend services. `src/truebrief/billing/stripe_service.py` is also dead (imported nowhere).
