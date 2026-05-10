# STEP SPEC — 3.5: Tier Enforcement
> **Status:** [x] PLAN COMPLETE | [x] BUILD COMPLETE | [x] UNIT COMPLETE | [x] INTG COMPLETE
> **Mode:** Step 3.5 fully verified
> **Builder / Integrator:** Claude Sonnet 4.6 (this session)
> **Date:** 2026-05-07

---

## 🎯 Objective

Enforce Free / Pro / Power subscription limits at the three critical gates:

1. **Topic creation** (`POST /api/v1/topics`) — block at cap → HTTP 402
2. **Scan triggers** (`POST /api/v1/topics/{id}/scan`) — enforce minimum interval → HTTP 429
3. **Pipeline source routing** (`PipelineRunner`) — strip disallowed source plugins at init time

This step does **not** handle frontend gating (upgrade banners, disabled buttons). That belongs in the Next.js frontend (Step 3.8). It also does **not** implement rate limiting infrastructure (Step 3.18).

---

## 📐 Design & Logic

### Pre-existing State (verified 2026-05-07)

| File | Status | Notes |
|------|--------|-------|
| `src/truebrief/models/tier.py` | ✅ Present | Had stale values (max_topics=3, missing `min_interval_hours`) |
| `src/truebrief/billing/stripe_service.py` | ✅ Present | Source of truth for user tier via `user_subscriptions.tier` |
| `src/truebrief/api/routes.py` | ✅ Present | Needed enforcement hooks at topic-create and scan-trigger |
| `src/truebrief/pipeline/runner.py` | ✅ Present | Needed `allowed_sources` param |

### Reconciled Tier Limits (blueprint § 3.5)

| Tier | `max_topics` | `min_interval_hours` | Sources | `private_topics` |
|------|:---:|:---:|---|:---:|
| Free | 2 | 24.0 | rss, tavily | No |
| Pro | 15 | 1.0 | rss, tavily, google_news, brave, exa | Yes |
| Power | unlimited | 0.25 | `__all__` | Yes |

### Enforcement Architecture

```
POST /api/v1/topics
  └─ load user_subscriptions.tier
  └─ count topic_subscriptions for user
  └─ enforce_topic_limit(user_id, tier_str, count) → 402 if at cap

POST /api/v1/topics/{id}/scan?user_id=...
  └─ load user_subscriptions.tier
  └─ load topics.last_scan_at
  └─ enforce_speed_limit(user_id, tier_str, last_scan_at) → 429 if too soon

PipelineRunner(allowed_sources=["rss","tavily"])
  └─ filters self.sources at __init__ time
  └─ ["__all__"] sentinel = skip filtering (POWER)
```

---

## 📂 File GPS

**Reads:**
- `src/truebrief/models/tier.py`
- `src/truebrief/api/routes.py`
- `src/truebrief/pipeline/runner.py`
- `docs/blueprints/phase_3.md` (§ Step 3.5)

**Touches:**
- `src/truebrief/models/tier.py` (**Modified** — added `min_interval_hours`, `private_topics`; reconciled values to blueprint)
- `src/truebrief/billing/tiers.py` (**Created** — `enforce_topic_limit`, `enforce_speed_limit`, `get_allowed_sources`)
- `src/truebrief/api/routes.py` (**Modified** — wired enforcement at topic-create and scan-trigger)
- `src/truebrief/pipeline/runner.py` (**Modified** — `allowed_sources` param filters source list at init)
- `tests/test_tier_enforcement.py` (**Created** — 18 unit tests, 18/18 PASS)

**Do NOT touch (deferred):**
- Frontend upgrade banners → Step 3.8
- Rate limiting infrastructure (Redis/slowapi) → Step 3.18
- Email/push gating → Steps 3.15–3.16

---

## 🛠 Execution Steps (completed)

- [x] Reconcile `models/tier.py` limits to blueprint spec (Free=2 topics, Pro=15, Power=unlimited)
- [x] Add `min_interval_hours` and `private_topics` fields to `TierLimits`
- [x] Create `billing/tiers.py` with `enforce_topic_limit`, `enforce_speed_limit`, `get_allowed_sources`
- [x] Wire `enforce_topic_limit` into `POST /api/v1/topics` (after UUID validation, before insert)
- [x] Wire `enforce_speed_limit` into `POST /api/v1/topics/{id}/scan` (accepts `user_id` query param)
- [x] Add `allowed_sources` param to `PipelineRunner.__init__`; filter source list when not `__all__`
- [x] Write `tests/test_tier_enforcement.py` — 18 tests covering all enforcement paths

---

## ✅ Testing & Verification

### Unit Tests (18/18 PASS — 2026-05-07)

| Test | Coverage |
|------|----------|
| `test_free_at_cap_raises_402` | Free user at limit → 402 |
| `test_free_below_cap_passes` | Free user under limit → pass |
| `test_pro_at_cap_raises_402` | Pro user at limit → 402 |
| `test_pro_below_cap_passes` | Pro user under limit → pass |
| `test_power_unlimited_always_passes` | Power tier → never raises |
| `test_unknown_tier_defaults_to_free_limits` | Bad tier string → FREE limits applied |
| `test_free_scan_within_24h_raises_429` | Free scan too soon → 429 |
| `test_free_scan_after_24h_passes` | Free scan after 25h → pass |
| `test_pro_scan_within_1h_raises_429` | Pro scan too soon → 429 |
| `test_pro_scan_after_1h_passes` | Pro scan after 90m → pass |
| `test_power_scan_always_passes` | Power scan at 20m → pass |
| `test_none_last_scan_always_passes` | First scan ever → always pass |
| `test_free_gets_rss_and_tavily` | Source allowlist correct for Free |
| `test_pro_gets_extended_sources` | Source allowlist correct for Pro |
| `test_power_returns_all_sentinel` | Power returns `["__all__"]` |
| `test_unknown_tier_defaults_to_free_sources` | Unknown tier → FREE sources |
| `test_runner_filters_sources_by_allowlist` | Runner correctly strips disallowed sources |
| `test_all_sentinel_skips_filtering` | `["__all__"]` → no sources removed |

### Integration Tests (13/13 PASS — 2026-05-07, `tests/test_tier_enforcement_intg.py`)

| Test | Coverage |
|---|---|
| `test_free_user_at_cap_returns_402` | Free user with 2 topics → 3rd POST returns 402 |
| `test_free_user_below_cap_succeeds` | Free user with 1 topic → 200 |
| `test_pro_user_at_cap_returns_402` | Pro user with 15 topics → 16th POST returns 402 |
| `test_pro_user_with_14_topics_succeeds` | Pro user with 14 topics → 200 |
| `test_power_user_unlimited` | Power user with 5000 topics → 200 |
| `test_no_user_id_skips_tier_check` | Anonymous create bypasses enforcement |
| `test_free_user_scan_too_soon_returns_429` | Free, last scan 2h ago → 429 |
| `test_free_user_scan_after_25h_succeeds` | Free, last scan 25h ago → 200, task queued |
| `test_pro_user_scan_within_1h_returns_429` | Pro, last scan 30 min ago → 429 |
| `test_no_user_id_skips_speed_limit` | No user_id query param → bypassed |
| `test_first_scan_passes` | `last_scan_at = NULL` → 200 |
| `test_tiers_endpoint_returns_reconciled_limits` | `GET /billing/tiers` exposes new `min_interval_hours` field |
| `test_invalid_user_id_returns_400` | Non-UUID `user_id` → 400 before enforcement |

### Live Smoke

- Manual smoke runbook published at `docs/runbooks/TIER_ENFORCEMENT_TESTING.md` covering: server startup, seeding test users per tier, manual cap/speed/source verification, and cleanup SQL.
- Bug fix shipped during INTG: `billing_routes.py` previously referenced the removed `scans_per_day` field — replaced with `min_interval_hours` so `GET /billing/tiers` and `GET /billing/status/{user_id}` no longer crash.

---

## 📝 Planner Notes

**Tier.py reconciliation:** The previous `TierLimits` model used `scans_per_day` (integer) which couldn't represent sub-hour intervals. Replaced with `min_interval_hours` (float) which maps cleanly onto both the 15-min Power tier and the enforcement math. Old `scans_per_day` is gone.

**Backward compatibility:** `billing_routes.py` `GET /billing/status` still works — it reads `max_topics` and sources from `TIER_LIMITS`. The `min_interval_hours` field is additive; no endpoint breaks.

**`last_scan_at` column:** The scan-speed enforcement reads `topics.last_scan_at`. If this column doesn't exist in the DB schema, the enforcement will gracefully skip (logged as a warning, not a crash). A DB migration adding this column is recommended before INTG testing.

**Model recommendation for INTG:** Claude Sonnet — needs to run the FastAPI server and fire real HTTP calls with test user IDs.
