# STEP SPEC — 3.7: Auth (Clerk + Backend JWT Verification)
> **Status:** [x] PLAN COMPLETE | [x] BUILD | [x] UNIT | [x] INTG COMPLETE
> **Planner / Integrator:** Claude Sonnet 4.6
> **PLAN Date:** 2026-05-07 | **INTG Date:** 2026-05-08
> **Depends on:** Step 3.6 (Next.js skeleton must exist before Clerk wiring)
> **Blocks:** Step 3.8 (Topic Management UI needs an authenticated user)

---

## 🎯 Objective

Replace the current `user_id` query-string convention with verifiable Clerk-issued sessions:

1. Wire **Clerk** into the Next.js frontend (`@clerk/nextjs`) — sign-up, sign-in, session, route protection.
2. On every protected backend call, present a **Clerk JWT** in `Authorization: Bearer <token>`.
3. Backend verifies the JWT via Clerk's **JWKS** endpoint, resolves it to a row in a **new `users` table**, and exposes the result via a `Depends(get_current_user)` FastAPI dependency.
4. Existing tier-enforcement and topic endpoints switch from `user_id: Optional[str]` query/body to `user: User = Depends(get_current_user)`.
5. First-time logins create both a `users` row **and** a `user_subscriptions` row with `tier='free'` (so tier enforcement keeps working out of the box).

This step deliberately scopes **only** authentication and identity. Authorization (per-resource access checks, e.g. "can user A see topic owned by user B") stays where it already lives — at the DB-level filters in `routes.py` (`topic_subscriptions.user_id`).

---

## 🧭 Decision Log — Why Clerk Over NextAuth

| Concern | Clerk | NextAuth |
|---|---|---|
| Email verification, OAuth, MFA | ✅ Built-in | ❌ Hand-wire each provider |
| Hosted user-management UI | ✅ Free | ❌ N/A |
| JWT verification cost on Python side | JWKS endpoint, ~100 lines | Same (you'd still need JWKS) |
| Session storage | Hosted | You manage |
| Free-tier ceiling | 10K MAUs | Unlimited (self-host) |
| Frontend lock-in risk | Medium (`@clerk/nextjs` SDK) | None |

**Decision:** Clerk. Blueprint § 3.7 already calls Clerk out by name; this spec confirms it. The lock-in risk is bounded — only `frontend/middleware.ts`, `frontend/app/layout.tsx`, and `frontend/lib/auth.ts` would need a rewrite to swap providers. Backend JWT verification is provider-agnostic JWKS code that survives a swap.

---

## 📐 Design & Logic

### Identity Flow

```
┌─────────┐   sign in   ┌──────────────┐   JWT   ┌──────────────────┐
│ Browser │ ──────────▶ │ Clerk hosted │ ──────▶ │ Next.js (cookie) │
└─────────┘             └──────────────┘         └──────────────────┘
                                                         │
                                                  fetch with
                                                  Authorization: Bearer <jwt>
                                                         │
                                                         ▼
                              ┌─────────────────────────────────────────┐
                              │ FastAPI middleware/dep:                  │
                              │  1. extract Bearer token                 │
                              │  2. fetch Clerk JWKS (cached 1h)         │
                              │  3. verify signature + iss + aud + exp   │
                              │  4. lookup users.clerk_id                │
                              │  5. if not found → INSERT users +         │
                              │     INSERT user_subscriptions (free)     │
                              │  6. return User (dataclass) to handler   │
                              └─────────────────────────────────────────┘
```

### `users` Table (new)

```sql
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clerk_id TEXT UNIQUE NOT NULL,
    email TEXT NOT NULL,
    display_name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_users_clerk_id ON users(clerk_id);
```

`users.id` is the canonical UUID used everywhere else (`topics.user_id`, `topic_subscriptions.user_id`, `user_subscriptions.user_id`). `clerk_id` is the lookup key from the JWT `sub` claim.

### Backend Module Layout

```
src/truebrief/auth/
├── __init__.py
├── clerk.py        # JWKS fetch, token verification (httpx + python-jose)
├── dependencies.py # FastAPI Depends(get_current_user) + Optional variant
└── user_repo.py    # get_or_create_user(clerk_id, email) → User
```

### Pseudocode — `auth/clerk.py`

```python
_JWKS_CACHE: tuple[float, dict] = (0.0, {})   # (expires_at, keys)
JWKS_TTL_SECONDS = 3600

def _get_jwks() -> dict:
    now = time.time()
    expires_at, cached = _JWKS_CACHE
    if now < expires_at and cached:
        return cached
    resp = httpx.get(settings.CLERK_JWKS_URL, timeout=5.0)
    resp.raise_for_status()
    keys = resp.json()
    _JWKS_CACHE = (now + JWKS_TTL_SECONDS, keys)
    return keys

def verify_clerk_jwt(token: str) -> dict:
    jwks = _get_jwks()
    header = jwt.get_unverified_header(token)
    key = next(k for k in jwks["keys"] if k["kid"] == header["kid"])
    return jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        audience=settings.CLERK_AUDIENCE,        # optional in dev
        issuer=settings.CLERK_ISSUER,
    )
```

### Pseudocode — `auth/dependencies.py`

```python
class User(BaseModel):
    id: str            # internal UUID
    clerk_id: str
    email: str
    display_name: str | None = None

async def get_current_user(
    authorization: str = Header(..., alias="Authorization"),
) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Bearer token")
    token = authorization[7:]
    try:
        payload = verify_clerk_jwt(token)
    except jwt.JWTError as e:
        raise HTTPException(401, f"Invalid token: {e}")
    return get_or_create_user(
        clerk_id=payload["sub"],
        email=payload.get("email", ""),
    )

async def get_optional_user(
    authorization: str | None = Header(None, alias="Authorization"),
) -> User | None:
    if not authorization:
        return None
    return await get_current_user(authorization)
```

### Pseudocode — `auth/user_repo.py`

```python
def get_or_create_user(clerk_id: str, email: str) -> User:
    db = get_supabase()
    res = db.table("users").select("*").eq("clerk_id", clerk_id).execute()
    if res.data:
        row = res.data[0]
        db.table("users").update({"last_seen_at": "now()"}).eq("id", row["id"]).execute()
        return User(**row)

    # First login — create paired rows
    new_id = str(uuid4())
    db.table("users").insert({
        "id": new_id, "clerk_id": clerk_id, "email": email,
    }).execute()
    db.table("user_subscriptions").insert({
        "user_id": new_id, "tier": "free", "status": "active",
    }).execute()
    return User(id=new_id, clerk_id=clerk_id, email=email)
```

### Route Migration

Each protected handler in `api/routes.py` switches signature:

```python
# BEFORE (Step 3.5)
@router.post("/topics")
def create_topic(topic: TopicCreate):
    val_uuid = topic.user_id ...

# AFTER (Step 3.7)
@router.post("/topics")
def create_topic(topic: TopicCreate, user: User = Depends(get_current_user)):
    val_uuid = user.id   # always present, always trustworthy
```

`TopicCreate.user_id` field is **removed**. `POST /scan` drops the `user_id` query param. The "anonymous bypass" path that exists today is removed for protected endpoints — admin/debug can hit a separate `/admin/...` namespace if needed (out of scope here).

### Frontend Wiring

```
frontend/
├── app/
│   ├── layout.tsx            # ⬅ wrap children with <ClerkProvider>
│   ├── sign-in/[[...sign-in]]/page.tsx
│   └── sign-up/[[...sign-up]]/page.tsx
├── middleware.ts             # ⬅ clerkMiddleware + protected matcher
├── lib/
│   └── api.ts                # ⬅ fetch wrapper attaches Bearer token
└── .env.local
    NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=...
    CLERK_SECRET_KEY=...
    NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

`lib/api.ts` snippet:

```typescript
import { auth } from "@clerk/nextjs/server";

export async function apiFetch(path: string, init: RequestInit = {}) {
  const { getToken } = auth();
  const token = await getToken();           // server-side: Clerk session token
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  headers.set("Content-Type", "application/json");
  return fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}${path}`, { ...init, headers });
}
```

`middleware.ts`:

```typescript
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

const isProtectedRoute = createRouteMatcher([
  "/dashboard(.*)",
  "/topics(.*)",
  "/onboarding(.*)",
]);

export default clerkMiddleware((auth, req) => {
  if (isProtectedRoute(req)) auth().protect();
});

export const config = {
  matcher: ["/((?!_next|.*\\..*).*)", "/(api|trpc)(.*)"],
};
```

---

## 📂 File GPS

**Reads (BUILD session):**
- `src/truebrief/api/routes.py` — to migrate `user_id` query/body params
- `src/truebrief/billing/billing_routes.py` — to migrate `/billing/checkout` & `/billing/portal` (currently take `user_id` in body)
- `config/settings.py` — to add `CLERK_*` settings
- `requirements.txt` — to add `python-jose[cryptography]`, `httpx` (already present)

**Touches (BUILD will create or modify):**
- `src/truebrief/auth/__init__.py` — **Create**
- `src/truebrief/auth/clerk.py` — **Create** (JWKS + verify)
- `src/truebrief/auth/dependencies.py` — **Create** (`get_current_user`, `get_optional_user`, `User`)
- `src/truebrief/auth/user_repo.py` — **Create** (`get_or_create_user`)
- `src/truebrief/api/routes.py` — **Modify** (replace `user_id` plumbing with `Depends`)
- `src/truebrief/billing/billing_routes.py` — **Modify** (same)
- `config/settings.py` — **Modify** (add `CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `CLERK_JWKS_URL`, `CLERK_ISSUER`, `CLERK_AUDIENCE`)
- `.env.example` — **Modify** (document the new vars)
- `requirements.txt` — **Modify** (add `python-jose[cryptography]>=3.3.0`)
- `scripts/migrations/004_users_table.sql` — **Create** (users table + index)
- `frontend/app/layout.tsx` — **Modify** (wrap with `<ClerkProvider>`) — assumes 3.6 already created the Next.js skeleton
- `frontend/middleware.ts` — **Create**
- `frontend/app/sign-in/[[...sign-in]]/page.tsx` — **Create**
- `frontend/app/sign-up/[[...sign-up]]/page.tsx` — **Create**
- `frontend/lib/api.ts` — **Modify** (Bearer token injection)
- `frontend/.env.example` — **Create** (Clerk publishable + secret keys)
- `tests/test_auth.py` — **Create** (UNIT — JWT verify, get_or_create_user paths)
- `tests/test_auth_intg.py` — **Create** (INTG — TestClient with mocked verify_clerk_jwt)
- `docs/runbooks/AUTH_TESTING.md` — **Create** (manual smoke against Clerk dev instance)

**Do NOT touch (deferred):**
- Per-resource authorization (topic ownership checks beyond what already exists) → Step 3.8
- Team/org accounts → Step 5.7
- Public share endpoints (`/share/:id`) — those stay unauthenticated → Step 3.14

---

## 🛠 Execution Steps (for the BUILD session — RUN 08)

1. [ ] Add `python-jose[cryptography]` to `requirements.txt`; `pip install -r requirements.txt`.
2. [ ] Extend `config/settings.py` with `CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `CLERK_JWKS_URL`, `CLERK_ISSUER`, `CLERK_AUDIENCE` (all `str` with sensible defaults: empty string).
3. [ ] Create `scripts/migrations/004_users_table.sql` and apply it to Supabase.
4. [ ] Write `src/truebrief/auth/clerk.py` with cached JWKS fetch + `verify_clerk_jwt`.
5. [ ] Write `src/truebrief/auth/user_repo.py` with `get_or_create_user`.
6. [ ] Write `src/truebrief/auth/dependencies.py` exposing `User`, `get_current_user`, `get_optional_user`.
7. [ ] Modify `api/routes.py`:
   - Drop `user_id` from `TopicCreate`.
   - Drop `user_id` query param from `POST /topics/{id}/scan`.
   - Add `user: User = Depends(get_current_user)` to `POST /topics`, `GET /topics`, `POST /topics/{id}/scan`, `DELETE /topics/{id}`.
   - Replace `val_uuid` references with `user.id`.
8. [ ] Modify `billing/billing_routes.py`:
   - `CheckoutRequest` & `PortalRequest` lose `user_id` and `email`; resolved from `user`.
   - `GET /status/{user_id}` becomes `GET /status` (uses current user).
9. [ ] Bootstrap Next.js Clerk wiring: `app/layout.tsx`, `middleware.ts`, sign-in/sign-up pages, `lib/api.ts`.
10. [ ] Update `.env.example` (root + `frontend/.env.example`).

---

## ✅ Testing & Verification

### Unit Tests — `tests/test_auth.py` (target: 12 tests, all green)

- [ ] `test_verify_clerk_jwt_valid_token_returns_payload` — patch JWKS + `jwt.decode`, assert payload returned.
- [ ] `test_verify_clerk_jwt_invalid_signature_raises` — `jwt.decode` raises `JWTError`, dependency surfaces 401.
- [ ] `test_verify_clerk_jwt_expired_token_raises_401`.
- [ ] `test_verify_clerk_jwt_missing_kid_raises`.
- [ ] `test_jwks_cache_hits_within_ttl` — second call doesn't hit network (mock counter == 1).
- [ ] `test_jwks_cache_refreshes_after_ttl` — advance time, mock counter == 2.
- [ ] `test_get_or_create_user_existing_returns_row` — DB returns 1 row, no insert called.
- [ ] `test_get_or_create_user_first_login_inserts_user_and_subscription` — DB returns 0 rows, two `.insert(...)` calls fired.
- [ ] `test_get_or_create_user_updates_last_seen_at` — existing path triggers `update({"last_seen_at": ...})`.
- [ ] `test_get_current_user_missing_authorization_raises_401`.
- [ ] `test_get_current_user_malformed_bearer_raises_401`.
- [ ] `test_get_optional_user_returns_none_when_no_header`.

### Integration Tests — `tests/test_auth_intg.py` (target: 8 tests)

Drive the real FastAPI app with `TestClient`. `verify_clerk_jwt` is monkeypatched to a stub returning `{"sub": "clerk_test_1", "email": "a@b.com"}`. Supabase is mocked exactly as in `test_tier_enforcement_intg.py`.

- [ ] `test_post_topics_without_token_returns_401`.
- [ ] `test_post_topics_with_invalid_token_returns_401`.
- [ ] `test_post_topics_with_valid_token_uses_resolved_user_id` — assert `topics.insert` was called with the `users.id` from `get_or_create_user`, NOT the Clerk sub.
- [ ] `test_first_login_creates_users_row_and_user_subscriptions_row`.
- [ ] `test_returning_user_skips_inserts` — only updates `last_seen_at`.
- [ ] `test_billing_status_uses_current_user_not_path_param`.
- [ ] `test_tier_enforcement_still_fires_on_authenticated_path` — Free user with 2 topics → `POST /topics` → 402 (proves 3.5 wiring still holds after migration).
- [ ] `test_scan_endpoint_speed_limit_with_authenticated_user` — Free user, last scan 2h ago → 429.

### Live Smoke (RUN 09 — INTG)

Documented in `docs/runbooks/AUTH_TESTING.md`:

1. Boot Clerk dev instance + paste keys into `.env.local` and `.env`.
2. `npm run dev` (frontend) + `uvicorn` (backend).
3. Sign up via Clerk-hosted UI → verify `users` row appears with new `id` + `clerk_id`.
4. Verify `user_subscriptions` row created with `tier='free'`.
5. Hit `/api/v1/topics` from the dashboard (UI) → confirm 200 with the cookie-derived JWT.
6. Hit `/api/v1/topics` directly with `curl -H "Authorization: Bearer <copied-jwt>"` → confirm 200.
7. Sign out → `/dashboard` redirects to `/sign-in`.

---

## 📝 Planner Notes

**Why insert `user_subscriptions` at first login.** Step 3.5 enforcement reads `user_subscriptions.tier`; if a brand-new user has no row, the code falls through to `tier_str = "free"` (current behavior) but `topic_subscriptions` writes still need a valid `user_id` FK — and we want a single source of truth for tier. Making `user_subscriptions` insert atomic with `users` insert means tier enforcement and Stripe sync (Step 3.4) share one row keyed by `users.id`.

**JWT library choice.** `python-jose[cryptography]` over `pyjwt` because Clerk's docs and most published examples use it, and the JWKS RS256 path is well-trodden. Either works; this is preference, not a hard requirement.

**JWKS cache.** Keep it simple: an in-process tuple with TTL. Multi-worker uvicorn → each worker has its own cache; this is fine because JWKS rotates rarely and Clerk publishes the rotation in advance.

**Why no token refresh logic on the backend.** Clerk handles refresh on the frontend (cookie + `getToken()` returns a fresh JWT each call). Backend is stateless — verify, use, discard.

**Test client strategy for INTG.** Patching `verify_clerk_jwt` (the lowest-level function) avoids depending on Clerk's network in tests, keeps the rest of the dependency chain (`get_current_user` → `get_or_create_user` → DB) real, and matches the pattern already used in `test_tier_enforcement_intg.py`.

**Migration risk.** Existing `topics.user_id` rows reference the **old** anonymous-or-passed-in UUIDs. Either (a) drop those rows in dev (preferred — Phase 3 still pre-launch), or (b) write a script that maps old `user_id` → newly-created `users.id`. Recommend (a). Document this in `AUTH_TESTING.md` cleanup section.

**Scope guard.** This step does not introduce row-level security policies in Postgres. Authorization stays application-level. RLS is a Phase 4 hardening task once the API is public.

**Model recommendation for BUILD (RUN 08):** Flash. Mechanical translation work, no architectural decisions left to make.

**Model recommendation for INTG (RUN 09):** Sonnet. Real Clerk dev setup + cross-stack debugging benefits from heavier reasoning.
