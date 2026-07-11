# TrueBrief — Product & Revenue Plan

*Written 2026-07-10. This is the prototype→product map: what exists, what's missing,
and the order to close the gaps. Update it as things ship.*

## Positioning (locked 2026-07-07)

**Change-monitoring with evidence.** Not "an AI news app" — a system that watches a
topic, checks every article against what you've already seen, and reports only what
actually changed, with sources attached. The marketing metric is the mechanism:
*"we read 47 articles so you read 3."*

---

## Income stream 1 — SaaS subscriptions (primary)

**Model:** Free (2 topics, daily) → Pro $19/mo (15 topics, hourly, private, API 500/day)
→ Power $49/mo (unlimited, 15-min, API 5,000/day). Billing via Paddle (merchant of record
— handles VAT/tax, good for IL-based founder).

| Piece | Status |
|---|---|
| Tier limits enforced (topics, scan speed, sources) | ✅ built + tested |
| Paddle checkout / portal / webhook routes | ✅ built |
| Landing page with honest claims + pricing | ✅ (2026-07-10 rewrite) |
| Settings: live tier badge, working upgrade + manage-billing buttons | ✅ (2026-07-10) |
| Terms + Privacy pages, footer links | ✅ (2026-07-10 — **user should eyeball before launch**) |
| Email digest + web push channels | ✅ built |
| **Paddle account activated with real price IDs** | ❌ **USER ACTION** — create Pro/Power prices in Paddle dashboard, set `PADDLE_PRICE_PRO`/`PADDLE_PRICE_POWER`/`PADDLE_API_KEY`/`PADDLE_WEBHOOK_SECRET` on Railway |
| Pipeline quality trusted enough to charge for | 🔶 close — signal scorer live, needs the "long test" (see Launch gate) |
| Production deploy of everything local | ❌ **USER ACTION** — `git push` to Railway |

## Income stream 2 — Developer API (built 2026-07-10)

**Model:** API access bundled into Pro/Power (adds upgrade pressure), enterprise volume
sold separately. No separate API-only tier yet — keep it simple until there's demand.

| Piece | Status |
|---|---|
| `api_keys` + `api_usage_daily` tables + atomic metering RPC | ✅ migration `026_api_keys.sql` — **needs applying to Supabase prod** |
| Key lifecycle: create (shown once, hashed at rest), list, revoke | ✅ built + tested |
| Public API: `/v1/topics`, `/v1/topics/{id}/facts`, `/v1/topics/{id}/history`, `/v1/usage` | ✅ built |
| Per-user daily quota (free 0 / pro 500 / power 5,000) | ✅ enforced, 402/429 semantics |
| Settings UI: create/copy-once/revoke + usage meter | ✅ built |
| Public docs page `/developers` with curl quickstart | ✅ built |
| Webhooks (push facts to customer URLs) | ❌ later — biggest API upgrade, do after first API users |
| OpenAPI spec / SDKs | ❌ later — FastAPI auto-generates `/docs`; polish when someone asks |

## Income stream 3 — B2B / Enterprise

**Model (for now):** "Contact us" — custom topics, custom volume, feed into their product.
Sell manually first; build multi-tenant features only against a real contract.

| Piece | Status |
|---|---|
| Enterprise strip on landing page + /developers rate-limit table | ✅ mailto CTA (2026-07-10) |
| Architecture supports shared topics / multi-tenant memory | ✅ by design (architecture_v3 §12) |
| Team seats, org accounts, SSO, invoicing | ❌ only if a deal requires it |

## Income stream 4 — later ideas (parked)

- **Slack/Teams digest app** — highest-leverage distribution once core is proven.
- **Vertical packages** (crypto desk, defense analysts, PR crisis monitoring) — same
  engine, niche landing pages, higher price.
- **One-off "state of play" reports** — pay-per-report without subscription.

---

## Launch gate (the "long test")

The product is sellable when, for 7 consecutive days on 3+ live topics:

1. Judge benchmark (`scripts/validate_pipeline.py --compare-gemini`): MISSING ≤ 2, noise ≈ 0.
2. No garbage/duplicate facts stored (spot-check `known_facts`).
3. Scheduler runs unattended (no quota deaths — needs Groq Dev tier, ~$1-3/mo).
4. Story view + dashboard render sanely on real accumulated data.

## Pre-revenue checklist (ordered)

1. **[USER] Deploy**: `git push` → Railway picks up all local commits.
2. **[USER] Apply migration 026** in Supabase SQL editor (api_keys tables + RPC).
3. **[USER] Railway env**: confirm `FOUNDER_EMAIL`, `ADMIN_EMAILS`, `FRONTEND_URL`; add
   Paddle vars when created.
4. **[USER] Groq Dev tier** (~$1-3/mo) — kills the daily quota deaths.
5. **[USER] Paddle**: create product + Pro/Power prices, switch from sandbox, test one
   real checkout end-to-end.
6. Run the 7-day launch gate. Fix what it surfaces.
7. **[USER] Eyeball** Terms/Privacy pages (they describe real behavior but you own them).
8. Soft launch: 10 design partners (personal network), free Pro in exchange for weekly
   feedback. Convert to paid after a month.

## Pricing sanity notes

- $19/$49 undercuts Feedly Pro+ ($12 but no dedup/synthesis) badly? No — Feedly Pro is
  $8-12 for feeds; TrueBrief sells *reading time back*, closer to Feedly Market
  Intelligence (hundreds/mo). $19 is a fine wedge; revisit with real conversion data.
- API-in-Pro (not separate) is deliberate: one decision for the buyer, upgrade pressure
  from quota, no second SKU to explain. Split it out only if API-only demand shows up.
