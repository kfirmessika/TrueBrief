# Phase 4: B2B API
> 📍 Read FIRST: [.ai/BOOT.md](file:///d:/projects/Apps/TrueBrief/.ai/BOOT.md)
> 📐 Status: `[ ]` Not Started

## Goal
Revenue from business customers through a public REST API, data licensing, webhook delivery, and usage-based billing. B2B = the real money. Even 5 clients at $2K/mo = $120K/year.

---

## Step Summary
| # | Task | Status | PLAN | BUILD | UNIT | INTG |
|---|------|--------|---|---|---|---|
| 4.1 | Public REST API + API Key Auth | [ ] | [ ] | [ ] | [ ] | [ ] |
| 4.2 | Polished API Docs | [ ] | [ ] | [ ] | [ ] | [ ] |
| 4.3 | GET /delta?since= Endpoint | [ ] | [ ] | [ ] | [ ] | [ ] |
| 4.4 | GET /nodes (Full Story Graph) | [ ] | [ ] | [ ] | [ ] | [ ] |
| 4.5 | POST /webhooks (Registration) | [ ] | [ ] | [ ] | [ ] | [ ] |
| 4.6 | Usage Tracking + Billing Logic | [ ] | [ ] | [ ] | [ ] | [ ] |
| 4.7 | Webhook Delivery Engine | [ ] | [ ] | [ ] | [ ] | [ ] |
| 4.8 | Admin Dashboard | [ ] | [ ] | [ ] | [ ] | [ ] |
| 4.9 | Rate Limits by Tier | [ ] | [ ] | [ ] | [ ] | [ ] |
| 4.10 | API Versioning & Headers | [ ] | [ ] | [ ] | [ ] | [ ] |

---

### Step 4.1: Public REST API + API Key Auth

| Detail | Value |
|--------|-------|
| **What** | Machine-readable API with API key authentication for B2B clients |
| **Files** | `src/truebrief/api/api_keys.py`, `src/truebrief/models/api_key.py` |
| **Status** | `[ ]` |

#### Design

```python
# models/api_key.py
@dataclass
class APIKey:
    key_id: str           # Public prefix: "tb_live_abc123..."
    key_hash: str         # bcrypt hash of full key (never store plaintext)
    user_id: str
    name: str             # Human label: "Production App", "Analytics Integration"
    tier: str             # "business" | "enterprise"
    is_active: bool
    last_used_at: datetime
    created_at: datetime
```

```python
# api/api_keys.py
def generate_api_key() -> tuple[str, str]:
    """Returns (full_key, hashed_key). full_key shown ONCE to user, then discarded."""
    raw = f"tb_live_{secrets.token_urlsafe(32)}"
    return raw, bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode()

async def authenticate_api_key(x_api_key: str = Header(...)) -> APIKeyContext:
    """FastAPI dependency: validate API key, return context with user + tier."""
    # Hash incoming key, lookup in api_keys table, check is_active
    # Log usage: update last_used_at, increment api_keys.request_count
```

#### API Key Management Endpoints
| Method | Path | What |
|--------|------|------|
| `POST` | `/api/v1/keys` | Create new API key (returns plaintext ONCE) |
| `GET` | `/api/v1/keys` | List keys (shows prefix + name, never full key) |
| `DELETE` | `/api/v1/keys/{key_id}` | Revoke key |

#### Acceptance Criteria
- `curl -H "X-API-Key: tb_live_..." /api/v1/topics` returns user's topics
- Invalid/expired key → HTTP 401 with `{"error": "invalid_api_key"}`
- Key creation returns full plaintext key ONLY once (re-fetch → only prefix shown)
- Key revocation takes effect within 5 seconds (no cache lag)
- API keys work alongside Clerk JWT (two auth methods on same endpoints)

---

### Step 4.2: Polished API Docs

| Detail | Value |
|--------|-------|
| **What** | Developer-facing documentation: auto-generated from FastAPI + hand-written guides |
| **Files** | `src/truebrief/api/server.py` (OpenAPI config), `docs/api/` (guides) |
| **Status** | `[ ]` |

#### Design

FastAPI auto-generates an OpenAPI 3.0 spec. Enhance it with:

```python
# api/server.py — enrich FastAPI metadata
app = FastAPI(
    title="TrueBrief API",
    description="Real-time news intelligence. Delta detection. Story evolution tracking.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_tags=[
        {"name": "topics", "description": "Manage monitoring topics"},
        {"name": "briefs", "description": "Retrieve generated briefs"},
        {"name": "delta", "description": "Time-filtered fact streams"},
        {"name": "nodes", "description": "Story graph access"},
        {"name": "webhooks", "description": "Push delivery registration"},
    ],
)
```

Each endpoint must have:
- `summary`: one-line description
- `description`: full markdown explanation
- `response_model`: typed Pydantic response schema
- `responses`: document 400, 401, 402, 429 error shapes

#### Hosted Docs
- `/api/docs` → Swagger UI (interactive, try-it-now)
- `/api/redoc` → ReDoc (read-only, clean, good for sharing)
- `GET /api/openapi.json` → raw spec for SDK generation

#### Acceptance Criteria
- All 15+ endpoints have summary, description, and typed response schema
- Swagger UI "Try it" works end-to-end with a live API key
- Zero `422 Unprocessable Entity` errors from undocumented required fields
- Docs load in < 2s
- API changelog at `/api/docs#changelog` section

---

### Step 4.3: GET /delta?since= Endpoint

| Detail | Value |
|--------|-------|
| **What** | The core B2B query: "give me every new/updated fact since timestamp X" |
| **Files** | `src/truebrief/api/routes.py` |
| **Status** | `[ ]` |

#### Design

```
GET /api/v1/topics/{topic_id}/delta?since=2026-04-01T00:00:00Z
```

```python
@router.get("/api/v1/topics/{topic_id}/delta")
async def get_delta(
    topic_id: str,
    since: datetime = Query(..., description="ISO 8601 UTC timestamp"),
    decision: Optional[str] = Query(None, enum=["NEW", "UPDATE"], description="Filter by decision type"),
    limit: int = Query(100, le=1000),
    cursor: Optional[str] = Query(None, description="Pagination cursor (opaque)"),
    ctx: APIKeyContext = Depends(authenticate_api_key),
) -> DeltaResponse:
    ...
```

```python
class DeltaResponse(BaseModel):
    topic_id: str
    since: datetime
    total_count: int
    next_cursor: Optional[str]   # Opaque cursor for next page
    facts: List[AlphaRecord]

class AlphaRecord(BaseModel):
    alpha_id: str
    alpha_text: str
    decision: str           # "NEW" | "UPDATE"
    delta: Optional[str]    # UPDATE only: what's specifically new
    entities: List[str]
    event_date: Optional[str]
    context: str
    confidence: float
    source_url: str
    source_domain: str
    first_seen_at: datetime
    story_node_id: Optional[str]
```

#### Acceptance Criteria
- `?since=2026-04-01T00:00:00Z` returns only facts ingested after that timestamp
- `?decision=UPDATE` filters to updates only
- Cursor pagination works: fetch 100, use cursor to get next 100
- Empty result (no new facts) → HTTP 200 with `{"total_count": 0, "facts": []}`
- Response time < 500ms for up to 1,000 facts

---

### Step 4.4: GET /nodes (Full Story Graph)

| Detail | Value |
|--------|-------|
| **What** | Return the full Story Node graph for a topic — stories, their summaries, and constituent facts |
| **Files** | `src/truebrief/api/routes.py` |
| **Status** | `[ ]` |

#### Design

```
GET /api/v1/topics/{topic_id}/nodes
GET /api/v1/topics/{topic_id}/nodes/{node_id}        ← single node with all alphas
```

```python
class StoryNodeResponse(BaseModel):
    node_id: str
    topic_id: str
    type: str                   # "root" | "sub_event"
    parent_node_id: Optional[str]
    recursive_summary: str      # Full narrative thread
    entities: List[str]
    earliest_event_date: Optional[str]
    latest_event_date: Optional[str]
    alpha_count: int
    last_updated_at: datetime
    alphas: Optional[List[AlphaRecord]]   # Included only in /nodes/{node_id}
```

Use cases:
- **PR firm:** `GET /nodes` → find story node for client brand → get `recursive_summary` → embed in dashboard
- **Hedge fund:** `GET /nodes?entities=TSMC` → pull all TSMC story threads

#### Query Parameters
| Param | Default | Description |
|-------|---------|-------------|
| `entities` | none | Comma-separated entity filter |
| `since` | none | Only nodes updated after timestamp |
| `include_alphas` | false | Include full alpha list per node (expensive) |
| `limit` | 20 | Max nodes returned |

#### Acceptance Criteria
- Returns story nodes with summary, entity list, date range
- `?entities=TSMC,Apple` filters to nodes containing any of those entities
- `?include_alphas=true` includes full alpha list in each node
- Single node endpoint returns all alphas regardless of `include_alphas`
- Response time < 1s for up to 50 nodes without alphas

---

### Step 4.5: POST /webhooks (Registration)

| Detail | Value |
|--------|-------|
| **What** | B2B clients register an endpoint URL to receive push delivery of new briefs |
| **Files** | `src/truebrief/api/routes.py`, `src/truebrief/models/webhook.py` |
| **Status** | `[ ]` |

#### Design

```python
# models/webhook.py
@dataclass
class Webhook:
    webhook_id: str
    user_id: str
    topic_id: Optional[str]    # None = all topics
    target_url: str            # Client's HTTPS endpoint
    secret: str                # Shared secret for HMAC signature verification
    events: List[str]          # ["brief.ready", "alpha.new", "alpha.update"]
    is_active: bool
    failure_count: int         # Auto-disable after 5 consecutive failures
    created_at: datetime
```

```
POST /api/v1/webhooks
{
  "target_url": "https://client.example.com/truebrief-hook",
  "topic_id": "abc123",          # Optional: omit for all topics
  "events": ["brief.ready"],
  "secret": "my_shared_secret"   # Client provides their own secret
}

→ 201 Created: { "webhook_id": "...", "status": "active" }
```

#### Verification Handshake
On registration, TrueBrief sends a `POST` to `target_url` with:
```json
{"event": "webhook.verify", "challenge": "random_string"}
```
Client must respond with `{"challenge": "random_string"}` within 10s or registration fails.

#### Acceptance Criteria
- Webhook registered → verification handshake succeeds → status `active`
- Webhook verification failure → status `unverified`, no events sent
- `GET /api/v1/webhooks` lists all webhooks with status
- `DELETE /api/v1/webhooks/{id}` deactivates immediately
- HMAC-SHA256 signature in `X-TrueBrief-Signature` header on every delivery

---

### Step 4.6: Usage Tracking + Billing Logic

| Detail | Value |
|--------|-------|
| **What** | Track API call counts per key, per endpoint, per day — feed into Stripe metered billing |
| **Files** | `src/truebrief/billing/usage.py`, `src/truebrief/billing/metered.py` |
| **Status** | `[ ]` |

#### Design

```python
# billing/usage.py
class UsageTracker:
    """Redis-backed usage counter. Flush to Supabase daily for billing."""

    def record_call(self, api_key_id: str, endpoint: str) -> None:
        """Increment Redis counter: usage:{api_key_id}:{endpoint}:{date}"""
        redis.incr(f"usage:{api_key_id}:{endpoint}:{date.today()}")

    def get_daily_usage(self, api_key_id: str, date: str) -> dict:
        """Return {endpoint: count} for given day."""

    def flush_to_db(self) -> None:
        """Daily Celery task: write Redis counters to api_usage table in Supabase."""
```

```python
# billing/metered.py — Stripe metered billing integration
class MeteredBilling:
    def report_usage(self, stripe_subscription_item_id: str, quantity: int) -> None:
        """Push usage to Stripe for metered components (e.g., API calls over limit)."""
        stripe.SubscriptionItem.create_usage_record(
            stripe_subscription_item_id,
            {"quantity": quantity, "timestamp": int(time.time())}
        )
```

#### Business Model: API Tiers
| Tier | Price | Included Calls | Overage |
|------|-------|---------------|---------|
| Business | $99/mo | 1,000 API calls/day | $0.05/call |
| Enterprise | $299/mo | Unlimited | — |

#### Acceptance Criteria
- Every authenticated API call logs to Redis within 5ms (non-blocking)
- Daily Celery task flushes to DB and reports to Stripe by 01:00 UTC
- `/api/v1/usage` endpoint shows current month usage to API key owner
- Business tier key hitting 1,001 calls in a day → Stripe overage recorded
- Usage dashboard shows daily call count by endpoint (sparkline chart in admin)

---

### Step 4.7: Webhook Delivery Engine

| Detail | Value |
|--------|-------|
| **What** | Reliably deliver events to registered webhook endpoints with retry logic |
| **Files** | `src/truebrief/tasks/webhook_delivery.py` |
| **Status** | `[ ]` |

#### Design

```python
# tasks/webhook_delivery.py
@celery_app.task(bind=True, max_retries=5, default_retry_delay=60)
def deliver_webhook(self, webhook_id: str, event_type: str, payload: dict) -> None:
    webhook = get_webhook(webhook_id)
    body = json.dumps({"event": event_type, "data": payload, "timestamp": utcnow()})
    sig = hmac.new(webhook.secret.encode(), body.encode(), hashlib.sha256).hexdigest()

    try:
        response = httpx.post(
            webhook.target_url,
            content=body,
            headers={"X-TrueBrief-Signature": f"sha256={sig}", "Content-Type": "application/json"},
            timeout=10.0,
        )
        response.raise_for_status()
        log_delivery_success(webhook_id, event_type)
    except Exception as exc:
        increment_failure_count(webhook_id)
        if get_failure_count(webhook_id) >= 5:
            disable_webhook(webhook_id)  # Auto-disable after 5 consecutive failures
            notify_user_webhook_disabled(webhook.user_id)
        raise self.retry(exc=exc)
```

#### Retry Schedule
| Attempt | Delay |
|---------|-------|
| 1st retry | 60s |
| 2nd retry | 5 min |
| 3rd retry | 30 min |
| 4th retry | 2 hours |
| 5th retry | 12 hours (final) |

#### Delivery Guarantee
- At-least-once delivery (may deliver twice under rare retry conditions)
- Client must handle idempotency using `event_id` in payload

#### Acceptance Criteria
- Event triggers → delivery within 30s under normal conditions
- Client returns HTTP 500 → retry with exponential backoff
- 5 consecutive failures → webhook auto-disabled + email to webhook owner
- All delivery attempts logged in `webhook_delivery_log` (success/failure + response code)
- Client can replay missed events via `GET /delta?since=` (pull fallback)

---

### Step 4.8: Admin Dashboard

| Detail | Value |
|--------|-------|
| **What** | Internal admin panel: user management, usage monitoring, system health |
| **Files** | `frontend/pages/admin/` (Next.js pages, admin-only routes) |
| **Status** | `[ ]` |

#### Pages
| Page | What It Shows |
|------|---------------|
| `/admin` | System overview: active users, briefs/day, error rate, LLM cost/day |
| `/admin/users` | User list: plan, topic count, last login, MRR contribution |
| `/admin/users/{id}` | User detail: topics, briefs, API keys, Stripe subscription |
| `/admin/api-keys` | All active API keys, usage, last seen |
| `/admin/webhooks` | All webhooks, delivery success rate, disabled count |
| `/admin/costs` | LLM cost breakdown by step/model, today vs yesterday |
| `/admin/sources` | AYR scores per source, recent failure rate |

#### Access Control
```python
# Admin routes gated by user.is_admin flag in DB (manually set)
async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
```

#### Acceptance Criteria
- Admin pages inaccessible to non-admin users (403, not 404)
- User list loads in < 2s for up to 10K users (paginated, server-side)
- Can manually change user's plan from admin (emergency override)
- LLM cost dashboard shows real data from usage logs
- Admin dashboard accessible at `/admin` with no menu entry in main nav

---

### Step 4.9: Rate Limits by Tier

| Detail | Value |
|--------|-------|
| **What** | Enforce API call rate limits based on B2B subscription tier |
| **Files** | `src/truebrief/api/middleware.py` (extend from Phase 3 rate limiter) |
| **Status** | `[ ]` |

#### Rate Limit Table (B2B)
| Endpoint | Business | Enterprise |
|----------|----------|-----------|
| GET /delta | 1,000/day | unlimited |
| GET /nodes | 500/day | unlimited |
| POST /webhooks | 50 total registered | unlimited |
| GET /briefs | 2,000/day | unlimited |
| POST /topics | 100/day | unlimited |

```python
# api/middleware.py — dynamic limits based on API key tier
def get_rate_limit(endpoint: str, tier: str) -> str:
    LIMITS = {
        "business": {"delta": "1000/day", "nodes": "500/day"},
        "enterprise": {"delta": "10000/day", "nodes": "10000/day"},
    }
    return LIMITS.get(tier, {}).get(endpoint, "100/day")
```

#### Acceptance Criteria
- Business key: 1,001st `/delta` call in a day → HTTP 429 with `{"error": "daily_limit_exceeded", "reset_at": "..."}`
- Enterprise key: no 429s under normal load (10K+ calls/day)
- Rate limits in response headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- Rate limit counters reset at midnight UTC (not rolling window)
- Admin can manually raise limit for a specific key without code deploy

---

### Step 4.10: API Versioning & Headers

| Detail | Value |
|--------|-------|
| **What** | URL-based versioning + deprecation headers for long-term API stability |
| **Files** | `src/truebrief/api/server.py`, `src/truebrief/api/routes.py` |
| **Status** | `[ ]` |

#### Versioning Strategy

URL-based versioning: `/api/v1/`, `/api/v2/` when breaking changes land.

```python
# api/server.py
from fastapi import APIRouter

v1_router = APIRouter(prefix="/api/v1", tags=["v1"])
# All current routes registered on v1_router

# When v2 launches:
v2_router = APIRouter(prefix="/api/v2", tags=["v2"])
# v1 kept alive for 12-month support window
```

#### Deprecation Headers
When a v1 endpoint is being phased out:
```python
@v1_router.get("/topics/{id}/delta")
async def get_delta_v1(..., response: Response):
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "2027-04-01"   # RFC 8594
    response.headers["Link"] = '</api/v2/topics/{id}/delta>; rel="successor-version"'
```

#### Standard Response Headers
All API responses include:
```
X-Request-ID: uuid4        # Unique request ID for support tracing
X-API-Version: 1.0.0       # Exact version served
X-RateLimit-Limit: N
X-RateLimit-Remaining: N
X-RateLimit-Reset: Unix timestamp
```

#### Acceptance Criteria
- All routes accessible under `/api/v1/` prefix
- Deprecated endpoints return `Deprecation: true` + `Sunset` date headers
- `X-Request-ID` present in every response (useful for support debugging)
- Breaking changes NEVER made to existing versioned endpoints (add new version instead)
- API changelog maintained at `docs/api/CHANGELOG.md`, linked from API docs

---
