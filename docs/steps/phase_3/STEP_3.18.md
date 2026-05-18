# Step 3.18 — Rate Limiting & Abuse Prevention

**Complexity:** 18 | **Model:** SONNET

---

## Goal

Add HTTP-layer rate limiting to the FastAPI backend to prevent abuse, protect expensive endpoints (scan, topic creation), and guard against DoS. Use `slowapi` (built on `limits`) with Redis storage in production and in-memory storage in dev.

---

## Architecture

### Library: slowapi

`slowapi` integrates with FastAPI via:
1. A `Limiter` instance with a configurable key function
2. `SlowAPIMiddleware` added to the app
3. `RateLimitExceeded` exception handler returning HTTP 429
4. `@limiter.limit("N/period")` decorators on individual routes

Route handlers that are rate-limited must accept `request: Request` as their **first parameter** (required by slowapi internals).

### Rate Limit Key Function

All limits use **client IP address** as the key (`slowapi.util.get_remote_address`). This reads `X-Forwarded-For` first (for Railway/reverse-proxy deployments) then falls back to the direct connection IP.

User-ID-based limiting on top of tier enforcement (e.g. scan frequency) is already handled by `enforce_speed_limit()` in `billing/tiers.py` — we don't duplicate that.

### Storage

- **Production**: `limits.storage.RedisStorage` via `REDIS_URL` env var
- **Dev / CI** (no Redis): `limits.storage.MemoryStorage` (auto-fallback)

### Rate Limits Applied

| Endpoint | Limit | Rationale |
|---|---|---|
| `POST /api/v1/topics` | 20/hour | Prevents topic spam |
| `POST /api/v1/topics/{id}/scan` | 10/hour | Expensive pipeline operation |
| `DELETE /api/v1/topics/{id}` | 30/hour | Deletion flood guard |
| `POST /api/v1/push/subscribe` | 10/hour | Subscription flood |
| `POST /api/v1/push/test` | 5/hour | Test push abuse |
| `POST /api/v1/billing/checkout` | 10/hour | Stripe API cost |

**Global middleware default**: `200/minute` per IP — catches broad DoS before any route runs.

---

## Files Touched

### New
- `src/truebrief/api/rate_limit.py` — Limiter instance + storage setup + key function

### Modified
- `requirements.txt` — add `slowapi>=0.1.9`
- `src/truebrief/api/server.py` — add `SlowAPIMiddleware`, `RateLimitExceeded` handler, default limit
- `src/truebrief/api/routes.py` — add `request: Request` + `@limiter.limit()` to create_topic, trigger_scan, delete_topic
- `src/truebrief/api/push_routes.py` — add `request: Request` + `@limiter.limit()` to subscribe, test_push
- `src/truebrief/billing/billing_routes.py` — add `request: Request` + `@limiter.limit()` to checkout

### Test
- `tests/test_rate_limiting.py` — 8 unit tests

---

## Tests

1. `test_limiter_created` — limiter object is instantiated correctly
2. `test_below_limit_allowed` — requests within limit return 200
3. `test_above_limit_blocked` — request exceeding limit returns 429
4. `test_429_response_has_retry_after` — 429 response includes `Retry-After` header
5. `test_different_ips_independent` — two IPs have independent counters
6. `test_create_topic_limit_enforced` — POST /topics is rate-limited (mock limiter)
7. `test_scan_limit_enforced` — POST /topics/{id}/scan is rate-limited (mock limiter)
8. `test_global_limit_on_health` — /health is covered by global middleware

---

## Acceptance Criteria

- [ ] `POST /topics` returns 429 after 20 requests/hour from same IP
- [ ] `POST /topics/{id}/scan` returns 429 after 10 requests/hour from same IP
- [ ] 429 responses include `Retry-After` header
- [ ] Dev mode (no Redis) works without errors (memory storage fallback)
- [ ] All existing tests still pass
- [ ] `npm run build` passes
