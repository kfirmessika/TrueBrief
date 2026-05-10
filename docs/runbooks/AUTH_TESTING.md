# Runbook: Auth (Clerk) — Live Smoke Test

Use this guide to validate the end-to-end Clerk → JWKS → backend flow against a real Clerk dev instance. Automated coverage in `tests/test_auth.py` (12 unit) and `tests/test_auth_intg.py` (9 integration) covers the wiring; this runbook covers what depends on real network and real Clerk-issued tokens.

## Prerequisites

1. Clerk dev application created at https://dashboard.clerk.com.
2. The following keys captured from Clerk's "API Keys" panel:
   - Publishable Key (starts `pk_test_`)
   - Secret Key (starts `sk_test_`)
   - JWKS URL (under "JWT Templates" → default → look for "JWKS URL"; format `https://<your-app>.clerk.accounts.dev/.well-known/jwks.json`)
   - Issuer (the URL prefix of the JWKS URL, without `/.well-known/jwks.json`)
3. Supabase migration `004_users_table.sql` applied:
   ```sql
   \i scripts/migrations/004_users_table.sql
   ```
4. `python-jose[cryptography]` installed (`pip install -r requirements.txt`).

## 1. Configure environment

`.env` (backend):
```
CLERK_PUBLISHABLE_KEY=pk_test_xxx
CLERK_SECRET_KEY=sk_test_xxx
CLERK_JWKS_URL=https://<your-app>.clerk.accounts.dev/.well-known/jwks.json
CLERK_ISSUER=https://<your-app>.clerk.accounts.dev
CLERK_AUDIENCE=
```

`frontend/.env.local`:
```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_xxx
CLERK_SECRET_KEY=sk_test_xxx
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## 2. Boot servers

```powershell
# Terminal A
uvicorn truebrief.api.server:app --reload --port 8000

# Terminal B
cd frontend
npm install
npm run dev
```

Health check:
```powershell
curl http://localhost:8000/health
# {"status":"ok"}
```

## 3. Verify unauthenticated → 401

```powershell
curl -X POST http://localhost:8000/api/v1/topics `
     -H "Content-Type: application/json" `
     -d '{"raw_query":"x"}' -i
```
**Expected:** `HTTP/1.1 401 Unauthorized`, `{"detail":"Missing Bearer token"}`.

## 4. Sign-up flow → user creation

1. In a browser: open `http://localhost:3000/sign-up`.
2. Sign up with a fresh email (use Clerk's testing emails like `your+clerk_test@example.com` to skip MFA).
3. After redirect to `/dashboard`, confirm in Supabase SQL editor:
   ```sql
   SELECT id, clerk_id, email, created_at FROM users ORDER BY created_at DESC LIMIT 1;
   SELECT user_id, tier, status FROM user_subscriptions
     WHERE user_id = (SELECT id FROM users ORDER BY created_at DESC LIMIT 1);
   ```
   **Expected:** new `users` row with the Clerk `sub` as `clerk_id`. Paired `user_subscriptions` row with `tier='free'`, `status='active'`.

## 5. Authenticated request via UI

From the dashboard, trigger any action that calls `/api/v1/topics` (e.g., the "Add Topic" form once 3.8 ships, or a manual `apiFetch` call from the browser console). Watch the backend log — you should see no 401s and a successful 200/201.

## 6. Authenticated request via curl

Grab a session JWT in the browser console:
```javascript
await window.Clerk.session.getToken()
```

Then:
```powershell
$T = "<paste-jwt-here>"
curl -X POST http://localhost:8000/api/v1/topics `
     -H "Authorization: Bearer $T" `
     -H "Content-Type: application/json" `
     -d '{"raw_query":"AI regulation"}'
```
**Expected:** `200` with the topic body. Backend log shows JWKS fetched on first call, cached on subsequent calls within 1h.

## 7. Returning user → no inserts

Refresh the dashboard (which fires a new request). In Supabase:
```sql
SELECT last_seen_at FROM users WHERE clerk_id = '<your-clerk-sub>';
```
**Expected:** `last_seen_at` is recent (within the last few seconds). No new `users` rows. No new `user_subscriptions` rows.

## 8. Sign-out flow

1. Click "Sign out" in the Clerk UserButton.
2. Try to navigate to `/dashboard`.
3. **Expected:** redirect to `/sign-in` via Clerk middleware.

## 9. Tampered token → 401

```powershell
curl -X POST http://localhost:8000/api/v1/topics `
     -H "Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.tampered.signature" `
     -H "Content-Type: application/json" `
     -d '{"raw_query":"x"}' -i
```
**Expected:** `401 Unauthorized`, detail mentions `Invalid token`.

## Cleanup

Pre-3.7 `topics.user_id` rows referenced anonymous-or-passed-in UUIDs that no longer correspond to real `users.id`. Phase 3 is still pre-launch — drop them:

```sql
DELETE FROM topic_subscriptions
WHERE user_id NOT IN (SELECT id FROM users);

DELETE FROM topics
WHERE user_id IS NOT NULL
  AND user_id NOT IN (SELECT id FROM users);
```

To wipe a test user entirely:
```sql
DELETE FROM topic_subscriptions WHERE user_id = '<users.id>';
DELETE FROM user_subscriptions WHERE user_id = '<users.id>';
DELETE FROM users WHERE id = '<users.id>';
-- Also delete the user from the Clerk dashboard.
```

## Pass Criteria Summary

| Check | Expected |
|---|---|
| Unauthenticated POST `/topics` | 401, "Missing Bearer token" |
| Sign-up via Clerk UI | `users` + `user_subscriptions` (free) rows created |
| Authenticated POST `/topics` (browser) | 200 |
| Authenticated POST `/topics` (curl + JWT) | 200 |
| Returning user dashboard load | `last_seen_at` updated, no new rows |
| Sign-out → `/dashboard` | redirect to `/sign-in` |
| Tampered JWT | 401, "Invalid token" |
