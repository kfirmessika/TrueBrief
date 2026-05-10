# Phase 3: Frontend + Monetization
> 📍 Read FIRST: [.ai/BOOT.md](file:///d:/projects/Apps/TrueBrief/.ai/BOOT.md)
> 📐 Status: `[/]` In Progress

## Goal
A product people can use and will pay for. Story intelligence (3.1-3.3) is already done. This phase ships the frontend, payments, and delivery channels.

---

## Step Summary
| # | Task | Status | PLAN | BUILD | UNIT | INTG |
|---|------|--------|---|---|---|---|
| 3.1 | Story Nodes | [x] | [x] | [x] | [x] | [x] |
| 3.2 | Dual Vectors | [x] | [x] | [x] | [x] | [x] |
| 3.3 | Recursive Summary Updates | [x] | [x] | [x] | [x] | [x] |
| 3.4 | Stripe Integration | [/] | [x] | [x] | [x] | [x] |
| 3.5 | Tier Enforcement | [x] | [x] | [x] | [x] | [x] |
| 3.6 | Next.js Frontend Skeleton | [x] | [x] | [x] | [x] | [x] |
| 3.7 | Auth (Clerk/NextAuth) | [x] | [x] | [x] | [x] | [x] |
| 3.8 | Topic Management UI | [x] | [x] | [x] | [x] | [ ] |
| 3.9 | Brief Display Page | [ ] | [ ] | [ ] | [ ] | [ ] |
| 3.10 | Brief History Page | [ ] | [ ] | [ ] | [ ] | [ ] |
| 3.11 | Landing Page | [ ] | [ ] | [ ] | [ ] | [ ] |
| 3.12 | Onboarding Flow | [ ] | [ ] | [ ] | [ ] | [ ] |
| 3.13 | "Time Saved" Metric | [ ] | [ ] | [ ] | [ ] | [ ] |
| 3.14 | Public Sharing Pages | [ ] | [ ] | [ ] | [ ] | [ ] |
| 3.15 | Email Digest | [ ] | [ ] | [ ] | [ ] | [ ] |
| 3.16 | Web Push Notifications | [ ] | [ ] | [ ] | [ ] | [ ] |
| 3.17 | Mobile-Responsive Design | [ ] | [ ] | [ ] | [ ] | [ ] |
| 3.18 | Rate Limiting & Abuse | [ ] | [ ] | [ ] | [ ] | [ ] |
| 3.19 | Brave Search + Exa Plugins | [ ] | [ ] | [ ] | [ ] | [ ] |
| 3.20 | Deployment (Vercel + Railway) | [ ] | [ ] | [ ] | [ ] | [ ] |

---

### Step 3.1–3.3: Story Intelligence (DONE)

Story Nodes, dual vectors, and recursive summaries are complete. These live in:
- `src/truebrief/ledger/story_manager.py`
- `src/truebrief/ledger/story_summarizer.py`
- `src/truebrief/ledger/vector_store.py` (dual-column pgvector)

---

### Step 3.4: Stripe Integration

| Detail | Value |
|--------|-------|
| **What** | Subscription management — checkout, webhooks, plan changes, cancellations |
| **Files** | `src/truebrief/billing/stripe_service.py`, `src/truebrief/billing/billing_routes.py` |
| **Status** | `[/]` BUILD & UNIT DONE |

#### Design

```python
# billing/stripe_client.py
class StripeClient:
    def create_checkout_session(self, user_id: str, plan: str) -> str:
        """Returns Stripe Checkout URL for redirect."""

    def create_portal_session(self, stripe_customer_id: str) -> str:
        """Returns billing portal URL for plan/payment management."""

    def get_subscription_status(self, stripe_customer_id: str) -> dict:
        """Returns {plan, status, current_period_end}."""
```

```python
# billing/webhooks.py  — FastAPI route, registered at /stripe/webhook
@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    event = stripe.Webhook.construct_event(
        await request.body(), sig_header, settings.STRIPE_WEBHOOK_SECRET
    )
    if event["type"] == "checkout.session.completed":
        # activate subscription, update users.plan in DB
    elif event["type"] == "customer.subscription.deleted":
        # downgrade user to free tier
```

#### Stripe Products to Create
| Plan | Price | Stripe Price ID |
|------|-------|----------------|
| Pro | $8/mo | `price_pro_monthly` |
| Power | $20/mo | `price_power_monthly` |

#### Acceptance Criteria
- User clicks "Upgrade" → Stripe Checkout opens in new tab
- Successful payment → user.plan updated to `pro` in DB within 30s (webhook)
- Cancellation → user downgraded to `free` at period end
- Billing portal link works: user can change card, view invoices, cancel

---

### Step 3.5: Tier Enforcement

| Detail | Value |
|--------|-------|
| **What** | Enforce Free/Pro/Power limits on topics, scan frequency, and source access |
| **Files** | `src/truebrief/billing/tiers.py`, integrated into `api/routes.py` |
| **Status** | `[ ]` |

#### Design

```python
# billing/tiers.py
TIER_LIMITS = {
    "free":  {"max_topics": 2, "min_interval_hours": 24, "sources": ["rss", "tavily"], "private_topics": False},
    "pro":   {"max_topics": 15, "min_interval_hours": 1,  "sources": ["rss", "tavily", "google_news", "brave", "exa"], "private_topics": True},
    "power": {"max_topics": None, "min_interval_hours": 0.25, "sources": "__all__", "private_topics": True},
}

def enforce_topic_limit(user: User) -> None:
    """Raises HTTP 402 if user is at their topic cap."""

def enforce_speed_limit(user: User, requested_interval: int) -> int:
    """Returns the clamped interval in seconds for this tier."""

def enforce_source_access(user: User, source: str) -> bool:
    """Returns True if this user's tier can access this source plugin."""
```

#### Enforcement Points
| Where | What is checked |
|-------|----------------|
| `POST /api/v1/topics` | `enforce_topic_limit` before insert |
| `POST /api/v1/topics/{id}/scan` | `enforce_speed_limit` against last scan time |
| `pipeline/runner.py` | `enforce_source_access` filters source plugins |
| Brief delivery | Free tier: mark as "delayed" if < 24h since last |

#### Acceptance Criteria
- Free user adding 3rd topic → HTTP 402 with upgrade prompt
- Free user triggering scan within 24h → 429 with "upgrade for real-time"
- Pro user with 16 topics → rejected at topic 16
- Tier check adds < 5ms to request latency (pure in-memory lookup)

---

### Step 3.6: Next.js Frontend Skeleton

| Detail | Value |
|--------|-------|
| **What** | Init Next.js app with routing, Tailwind, React Query, shared layout |
| **Files** | `frontend/` directory (new) |
| **Status** | `[x]` DONE |

#### Design

```
frontend/
├── pages/
│   ├── _app.tsx          # Global layout, QueryClientProvider
│   ├── index.tsx         # Landing page
│   ├── dashboard.tsx     # Authenticated home (topic list)
│   ├── onboarding.tsx    # New user flow
│   └── topics/
│       └── [id]/
│           ├── index.tsx       # Topic detail + scan button
│           └── briefs/
│               ├── index.tsx   # Brief history
│               └── [briefId].tsx  # Full brief
├── components/
│   ├── Layout.tsx        # Nav + footer wrapper
│   ├── TopicCard.tsx     # Topic summary card
│   └── BriefBlock.tsx    # NEW/UPDATE section renderer
├── lib/
│   ├── api.ts            # Typed fetch wrappers for backend
│   └── auth.ts           # Auth helpers
└── tailwind.config.js
```

```bash
npx create-next-app@latest frontend --typescript --tailwind --app
cd frontend && npm install @tanstack/react-query axios
```

#### Acceptance Criteria
- `npm run dev` starts with no errors
- `/` route renders (placeholder landing page)
- `/dashboard` route renders (placeholder topic list)
- Tailwind classes apply correctly
- TypeScript strict mode enabled, zero type errors

---

### Step 3.7: Auth (Clerk)

| Detail | Value |
|--------|-------|
| **What** | User sign-up, login, session management — never build auth yourself |
| **Files** | `frontend/pages/_app.tsx`, `frontend/middleware.ts`, `frontend/lib/auth.ts` |
| **Status** | `[ ]` |

#### Why Clerk over NextAuth
Clerk handles email verification, OAuth providers, session tokens, and user management UI out of the box. NextAuth requires more wiring. At this scale, Clerk free tier is zero cost.

#### Design

```typescript
// pages/_app.tsx
import { ClerkProvider } from "@clerk/nextjs";

export default function App({ Component, pageProps }) {
  return (
    <ClerkProvider>
      <QueryClientProvider client={queryClient}>
        <Component {...pageProps} />
      </QueryClientProvider>
    </ClerkProvider>
  );
}
```

```typescript
// middleware.ts — protect all /dashboard/* routes
import { authMiddleware } from "@clerk/nextjs";
export default authMiddleware({ publicRoutes: ["/", "/share/:briefId"] });
```

```python
# backend: verify Clerk JWT on protected routes
# api/auth.py
async def get_current_user(authorization: str = Header(...)) -> User:
    """Verify Clerk JWT, return user from DB (create on first login)."""
    payload = verify_clerk_jwt(authorization)
    return await get_or_create_user(clerk_user_id=payload["sub"], email=payload["email"])
```

#### Acceptance Criteria
- New user signs up → account created in `users` table
- Protected routes redirect to sign-in if unauthenticated
- Clerk JWT passed as Bearer token to backend, validated correctly
- User profile (name, email) visible in nav after login

---

### Step 3.8: Topic Management UI

| Detail | Value |
|--------|-------|
| **What** | Create, view, delete topics. Trigger manual scans. See topic status. |
| **Files** | `frontend/pages/dashboard.tsx`, `frontend/components/TopicCard.tsx`, `frontend/pages/topics/[id]/index.tsx` |
| **Status** | `[ ]` |

#### Design

```typescript
// components/TopicCard.tsx
interface TopicCardProps {
  topic: Topic;
  onScan: (id: string) => void;
  onDelete: (id: string) => void;
}
// Shows: topic query, last scan time, brief count, scan button, delete button
// Free tier: shows "Upgrade for real-time" if daily delay applies
```

```typescript
// pages/dashboard.tsx
// React Query: useQuery("topics", fetchTopics) — polls every 30s
// Mutation: useMutation(createTopic) — POST /api/v1/topics
// Renders: TopicCard list + "Add Topic" form + upgrade banner (if free at limit)
```

#### Acceptance Criteria
- User can create a topic with a free-text query
- Topic appears in list within 2 seconds (optimistic update)
- Scan button triggers pipeline; button shows spinner during scan
- Topic can be deleted (confirmation modal before delete)
- Free user at 2-topic limit sees "Upgrade" prompt instead of "Add Topic"

---

### Step 3.9: Brief Display Page

| Detail | Value |
|--------|-------|
| **What** | Full brief with NEW / UPDATE sections, source links, story context |
| **Files** | `frontend/pages/topics/[id]/briefs/[briefId].tsx`, `frontend/components/BriefBlock.tsx` |
| **Status** | `[ ]` |

#### Design

```typescript
// BriefBlock.tsx — renders one section of a brief
interface BriefBlockProps {
  type: "new" | "update" | "no_change";
  alphaText: string;
  delta?: string;          // UPDATE only: "what's new"
  fullContext?: string;    // UPDATE only: story so far
  sources: Source[];
  entityTags: string[];
}
```

Brief structure on screen:
```
🆕 NEW STORIES
━━━━━━━━━━━━━━
[alpha_text]
→ Reuters · Bloomberg

📈 UPDATES
━━━━━━━━━━
[Story Headline]
WHAT'S NEW: [delta]
FULL CONTEXT: [recursive_summary from Story Node]
→ CNBC · TechCrunch

⏸️ No changes: [comma-separated unchanged story names]
```

#### Acceptance Criteria
- Brief renders correctly with NEW and UPDATE sections separated
- Each source is a clickable external link (opens in new tab)
- Entity tags shown as pills (clickable → future topic creation)
- Brief loads in < 2s from server
- Share button present (links to public sharing page, Step 3.14)

---

### Step 3.10: Brief History Page

| Detail | Value |
|--------|-------|
| **What** | Paginated list of past briefs for a topic, newest first |
| **Files** | `frontend/pages/topics/[id]/briefs/index.tsx` |
| **Status** | `[ ]` |

#### Design

```typescript
// Fetch: GET /api/v1/topics/{id}/briefs?page=1&limit=10
// Each entry shows: date, brief preview (first 100 chars), unread badge
// Click → navigates to full brief page
// Pagination: simple next/previous buttons (no infinite scroll, overkill)
```

#### Acceptance Criteria
- Shows briefs sorted newest → oldest
- Brief card shows: date, preview text, source count
- Unread briefs visually distinct (bold title, colored left border)
- Marking a brief read updates `is_read = true` in DB (PATCH endpoint)
- Empty state: "No briefs yet. Trigger a scan to get started."

---

### Step 3.11: Landing Page

| Detail | Value |
|--------|-------|
| **What** | Conversion-focused homepage: value prop, how it works, pricing, CTA |
| **Files** | `frontend/pages/index.tsx` |
| **Status** | `[ ]` |

#### Sections (in order)
1. **Hero** — "Stop reading the news. Get the brief." + email sign-up CTA
2. **Problem** — "50 articles saying the same thing. You read all of them for one new sentence."
3. **How It Works** — 3-step visual: Enter topic → System watches → You get only what's new
4. **Live Demo Brief** — Embedded real brief (pre-rendered static, auto-updated daily)
5. **Pricing Table** — Free / Pro / Power with feature comparison
6. **FAQ** — "Is this just a summarizer?" / "What sources?" / "How fresh is it?"
7. **Footer** — Links, legal

#### Acceptance Criteria
- Page scores 90+ on Lighthouse (performance, SEO, accessibility)
- CTA email form captures email → added to waitlist or triggers Clerk sign-up
- Pricing table links to Stripe Checkout for Pro/Power
- Mobile layout tested at 375px, 768px, 1280px widths

---

### Step 3.12: Onboarding Flow

| Detail | Value |
|--------|-------|
| **What** | Guide new users from sign-up to their first brief result |
| **Files** | `frontend/pages/onboarding.tsx` |
| **Status** | `[ ]` |

#### Flow (3 steps, skip available)
1. **Welcome** — "TrueBrief watches the internet so you don't have to. Add your first topic."
2. **Add Topic** — Free-text input with suggested examples by category (Finance, Tech, Geopolitics)
3. **First Scan** — Trigger scan inline, show progress indicator, display brief preview when done

#### Acceptance Criteria
- New user redirected to `/onboarding` on first login (check `topics.count == 0`)
- Completing step 3 marks `user.onboarding_complete = true`
- Skipping works (goes to dashboard)
- Suggested topics are real, varied examples (not lorem ipsum)

---

### Step 3.13: "Time Saved" Metric

| Detail | Value |
|--------|-------|
| **What** | Track and display how many minutes of news-reading TrueBrief saved the user |
| **Files** | `src/truebrief/ledger/metrics.py`, surfaced in dashboard header |
| **Status** | `[ ]` |

#### Design

```python
# metrics.py
MINUTES_PER_ARTICLE_READ = 4.5   # average adult reading time for a news article
ALPHA_TO_ARTICLE_RATIO = 3.2     # empirical: ~3 articles processed per Alpha delivered

def calculate_time_saved(user_id: str) -> float:
    """Returns total minutes saved = alphas_delivered * ALPHA_TO_ARTICLE_RATIO * MINUTES_PER_ARTICLE_READ."""
    alphas_delivered = count_delivered_alphas(user_id)
    return alphas_delivered * ALPHA_TO_ARTICLE_RATIO * MINUTES_PER_ARTICLE_READ
```

Dashboard display: `"This week: saved you 2h 14m of news-reading"`

After 7 days of use, trigger: `"You've saved 3 hours this week → [Upgrade for hourly updates]"`

#### Acceptance Criteria
- Time saved shown in dashboard as "Xh Ym saved this week" (or "Xm" if < 1h)
- Recalculated on each dashboard load (not cached — it's fast, just a count)
- Upgrade CTA shown after 7 days of use on same widget

---

### Step 3.14: Public Sharing Pages

| Detail | Value |
|--------|-------|
| **What** | Shareable read-only brief URL for viral growth and SEO |
| **Files** | `frontend/pages/share/[shareId].tsx`, `src/truebrief/api/routes.py` (share endpoint) |
| **Status** | `[ ]` |

#### Design

```python
# Backend: POST /api/v1/briefs/{id}/share -> {share_url: "https://truebrief.io/share/abc123"}
# Generates share_token (8-char random slug), stored in briefs.share_token column
# GET /api/v1/share/{share_token} -> returns brief content (no auth required)
```

```typescript
// pages/share/[shareId].tsx
// - Server-side rendered (SSR) for SEO + social card metadata
// - Shows full brief with watermark: "Powered by TrueBrief — Get your own brief →"
// - CTA: "Track [topic] yourself → Sign up free"
// - Open Graph tags: title, description, brief preview for link previews
```

#### Acceptance Criteria
- Share link works without authentication
- Social preview (og:image) generated with brief title and topic
- "Powered by TrueBrief" watermark with sign-up CTA visible
- Share links never expire (persist in DB)
- User can revoke share token (regenerates new token)

---

### Step 3.15: Email Digest

| Detail | Value |
|--------|-------|
| **What** | Send formatted brief via email on user-configured schedule |
| **Files** | `src/truebrief/tasks/email.py`, `src/truebrief/tasks/email_templates/brief_digest.html` |
| **Status** | `[ ]` |

#### Design

```python
# tasks/email.py
class EmailDigestTask:
    """Celery task: render and send brief digest email."""
    provider = "resend"   # resend.com — 3K free emails/month, simple API

    def send_digest(self, user_id: str, brief_ids: List[str]) -> None:
        briefs = [get_brief(id) for id in brief_ids]
        html = render_email_template("brief_digest.html", briefs=briefs, user=get_user(user_id))
        resend.Emails.send({
            "from": "brief@truebrief.io",
            "to": user.email,
            "subject": f"Your TrueBrief — {date.today().strftime('%b %d')}",
            "html": html,
        })
```

Email template structure mirrors the brief display page: NEW section → UPDATE section → "No changes" footer.

#### User Settings
- `email_digest_frequency`: `"daily"` | `"weekly"` | `"off"` (Pro/Power only, free = off)
- `email_digest_time`: HH:MM UTC (default 07:00)

#### Acceptance Criteria
- Pro user receives email at configured time with all topic briefs for that day
- Email renders correctly in Gmail, Outlook, Apple Mail (test with Litmus or Email on Acid)
- Unsubscribe link works and sets `email_digest_frequency = "off"`
- Free users who try to enable email digest see "Upgrade to Pro"

---

### Step 3.16: Web Push Notifications

| Detail | Value |
|--------|-------|
| **What** | Browser push when a new brief is ready (PWA feature, Pro/Power only) |
| **Files** | `frontend/public/sw.js` (service worker), `src/truebrief/tasks/push.py` |
| **Status** | `[ ]` |

#### Design

```python
# tasks/push.py — send Web Push Notification
from pywebpush import webpush, WebPushException

def send_push(subscription_info: dict, brief_summary: str, brief_url: str) -> None:
    webpush(
        subscription_info=subscription_info,
        data=json.dumps({"title": "TrueBrief Ready", "body": brief_summary, "url": brief_url}),
        vapid_private_key=settings.VAPID_PRIVATE_KEY,
        vapid_claims={"sub": "mailto:support@truebrief.io"},
    )
```

```javascript
// public/sw.js — service worker handles push events
self.addEventListener("push", (event) => {
  const data = event.data.json();
  event.waitUntil(
    self.registration.showNotification(data.title, { body: data.body, data: { url: data.url } })
  );
});
```

#### Acceptance Criteria
- User opts in to push → browser permission prompt appears
- Subscription stored in `user_push_subscriptions` table
- Push fires within 60s of brief being written to DB
- Clicking notification opens the brief page
- Push does not fire for "no new information" runs

---

### Step 3.17: Mobile-Responsive Design

| Detail | Value |
|--------|-------|
| **What** | Ensure full usability on mobile (375px+) without a native app |
| **Files** | All frontend pages + `frontend/public/manifest.json` (PWA manifest) |
| **Status** | `[ ]` |

#### Key Mobile Concerns
- Topic card list → single column on mobile, 2-column on tablet, 3 on desktop
- Brief display → full-width, no horizontal scroll, font size 16px minimum
- Navigation → hamburger menu on mobile (`<768px`)
- PWA: `manifest.json` with icons, `theme_color`, `display: standalone`

#### Acceptance Criteria
- All pages pass Chrome DevTools mobile emulation at 375px (iPhone SE) and 768px (iPad)
- No horizontal scroll at any breakpoint
- Lighthouse PWA score ≥ 80
- "Add to Home Screen" works on iOS (Safari) and Android (Chrome)

---

### Step 3.18: Rate Limiting & Abuse Prevention

| Detail | Value |
|--------|-------|
| **What** | Protect API from scraping, runaway clients, and free tier abuse |
| **Files** | `src/truebrief/api/middleware.py` |
| **Status** | `[ ]` |

#### Design

```python
# middleware.py — uses slowapi (FastAPI rate limiter built on limits)
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, storage_uri=settings.REDIS_URL)

# Applied per-route:
@router.post("/api/v1/topics/{id}/scan")
@limiter.limit("10/hour")   # free; overridden to 60/hour for Pro in tier check
async def trigger_scan(id: str, request: Request, user: User = Depends(get_current_user)):
    ...
```

#### Rate Limit Table
| Endpoint | Free | Pro | Power |
|----------|------|-----|-------|
| POST /topics | 5/day | 50/day | 200/day |
| POST /topics/{id}/scan | 2/day | 24/hour | 96/hour |
| GET /briefs | 100/hour | 500/hour | unlimited |
| POST /stripe/webhook | no limit (validated by signature) | — | — |

#### Acceptance Criteria
- Exceeding limit → HTTP 429 with `Retry-After` header
- Rate limit counters stored in Redis (not in-memory — survives restarts)
- IP-based limiting for unauthenticated; user-id-based for authenticated
- Limits visible in response headers: `X-RateLimit-Remaining`, `X-RateLimit-Reset`

---

### Step 3.19: Brave Search + Exa Source Plugins

| Detail | Value |
|--------|-------|
| **What** | Add Phase 3+ source plugins for broader and deeper article coverage |
| **Files** | `src/truebrief/collector/brave_layer.py`, `src/truebrief/collector/exa_layer.py` |
| **Status** | `[ ]` |

#### Brave Search Layer

```python
# collector/brave_layer.py
class BraveLayer(SourceLayer):
    """Brave Search API — broad web search, ~$5/mo for 1K requests."""
    API_URL = "https://api.search.brave.com/res/v1/news/search"

    def search(self, query: SearchQuery) -> List[RawArticle]:
        # Returns news results; full text requires extractor (no Tavily-style pre-extraction)
        # Route through Article Extractor (Step 1.4) for full text
```

#### Exa Layer

```python
# collector/exa_layer.py
class ExaLayer(SourceLayer):
    """Exa API — semantic deep search, finds PDFs, research, non-indexed content."""
    # $7/1,000 requests. Use for Pro/Power topics in tech, finance, science domains.
    # Returns full text highlights — partial extraction built-in.
```

#### Routing Configuration

```yaml
# config/routing_rules.yaml
defaults:
  layers: [rss_layer, tavily_layer]         # Free tier

overrides:
  - tier: pro
    add_layers: [google_news_layer, brave_layer]
  - tier: power
    add_layers: [google_news_layer, brave_layer, exa_layer]
  - domain: finance
    add_layers: [exa_layer]                  # SEC/earnings PDFs
  - domain: medical
    add_layers: [exa_layer]                  # PubMed, clinical trials
```

#### Acceptance Criteria
- `BraveLayer().search(query)` returns `List[RawArticle]` (URLs extracted via extractor)
- `ExaLayer().search(query)` returns `List[RawArticle]` with text highlights
- Missing API key → graceful skip, logged as warning, not crash
- Only enabled for correct tiers per routing config

---

### Step 3.20: Deployment (Vercel + Railway)

| Detail | Value |
|--------|-------|
| **What** | Production-ready deployment: frontend on Vercel, backend on Railway, DB on Supabase |
| **Files** | `railway.toml`, `frontend/vercel.json`, `Dockerfile` (backend) |
| **Status** | `[ ]` |

#### Architecture

```
[Vercel]              [Railway]              [Supabase]
Next.js Frontend  →   FastAPI Backend    →   PostgreSQL + pgvector
(CDN, global)         + Celery Worker        (cloud, managed)
                      + Celery Beat
                      + Redis
```

#### Railway Setup
```toml
# railway.toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile"

[[services]]
name = "api"
startCommand = "uvicorn src.truebrief.api.server:app --host 0.0.0.0 --port $PORT"

[[services]]
name = "worker"
startCommand = "celery -A src.truebrief.tasks worker --loglevel=info"

[[services]]
name = "beat"
startCommand = "celery -A src.truebrief.tasks beat --loglevel=info"
```

#### Environment Variables (production)
```
DATABASE_URL=           # Supabase connection string
REDIS_URL=              # Railway Redis
GOOGLE_API_KEY=
TAVILY_API_KEY=
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
CLERK_SECRET_KEY=
VAPID_PRIVATE_KEY=
RESEND_API_KEY=
```

#### Acceptance Criteria
- `git push` to `main` triggers auto-deploy via Railway + Vercel GitHub integrations
- Frontend at `truebrief.io` (Vercel), API at `api.truebrief.io` (Railway custom domain)
- All env vars loaded from Railway/Vercel environment (not `.env` files)
- Health check endpoint `GET /health` returns `{"status": "ok"}` within 2s
- Celery worker and beat confirmed running in Railway dashboard
- Sentry error tracking active in both frontend and backend

---
