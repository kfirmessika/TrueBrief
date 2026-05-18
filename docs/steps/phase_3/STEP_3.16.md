# STEP 3.16 — Web Push Notifications

**Complexity:** 15 | **Model:** SONNET  
**Phase:** 3 — Frontend + Monetization

---

## Goal

Deliver browser-native Web Push Notifications to subscribed users when a new brief is ready for any of their topics. Uses the **Web Push Protocol** (VAPID) on the backend (`pywebpush`) and a **Service Worker** on the frontend. Notifications are opt-in per user and stored in Supabase.

---

## Architecture

```
User grants permission (frontend)
    └─► JS creates PushSubscription (endpoint + keys)
            └─► POST /api/v1/push/subscribe  → stored in push_subscriptions table

Pipeline completes brief delivery
    └─► send_push_notifications_task (Celery task)
            ├─ Query push_subscriptions where user_id = user_id, enabled = true
            ├─ For each subscription → POST via VAPID (pywebpush)
            └─ Browser service worker (sw.js) receives push → shows Notification
```

---

## New Files

| File | Purpose |
|---|---|
| `src/truebrief/push/client.py` | pywebpush wrapper: sends one push message |
| `src/truebrief/tasks/push_task.py` | Celery task: `send_push_notifications_task` |
| `src/truebrief/api/push_routes.py` | REST endpoints for subscription management |
| `frontend/public/sw.js` | Service worker: handles `push` event → shows Notification |
| `frontend/src/hooks/usePushNotifications.ts` | Hook: subscribe / unsubscribe logic |
| `frontend/src/components/PushNotificationToggle.tsx` | UI toggle for settings page |
| `tests/test_push.py` | Unit tests |

---

## Modified Files

| File | Change |
|---|---|
| `src/truebrief/tasks/celery_app.py` | Add `push_task` to `include` list |
| `src/truebrief/api/server.py` | Mount `push_routes` router |
| `src/truebrief/ledger/schema.sql` | Add `push_subscriptions` table |
| `src/truebrief/tasks/pipeline_task.py` | After brief delivery, enqueue `send_push_notifications_task` |
| `frontend/src/app/settings/page.tsx` | Add `PushNotificationToggle` component |

---

## Schema

### New table: `push_subscriptions`

```sql
create table if not exists push_subscriptions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references users(id) on delete cascade,
    endpoint text not null,
    p256dh text not null,
    auth text not null,
    enabled boolean default true,
    created_at timestamptz default now(),
    unique(user_id, endpoint)
);
```

---

## Implementation Details

### `push/client.py`

```python
"""
Web Push Client — push/client.py
Wraps pywebpush. Reads VAPID keys from env.
"""
import os, logging, json
from pywebpush import webpush, WebPushException

logger = logging.getLogger(__name__)

VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY  = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_SUBJECT     = os.getenv("VAPID_SUBJECT", "mailto:admin@truebrief.ai")

def send_push(subscription_info: dict, title: str, body: str, url: str = "/") -> bool:
    """
    subscription_info: {"endpoint": ..., "keys": {"p256dh": ..., "auth": ...}}
    Returns True on success, False on error (expired/invalid subscription).
    """
    if not VAPID_PRIVATE_KEY:
        logger.warning("VAPID_PRIVATE_KEY not set — skipping push.")
        return False
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps({"title": title, "body": body, "url": url}),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_SUBJECT},
        )
        return True
    except WebPushException as exc:
        logger.warning("Push failed (endpoint may be expired): %s", exc)
        return False
    except Exception as exc:
        logger.error("Unexpected push error: %s", exc)
        return False
```

### `tasks/push_task.py`

```python
"""
Push Notification Task — tasks/push_task.py

Celery task: sends Web Push to all enabled subscriptions for a given user.

Called by pipeline_task after brief delivery:
    send_push_notifications_task.delay(user_id=..., topic_name=..., brief_id=...)

Logic:
  1. Query push_subscriptions where user_id = user_id AND enabled = true
  2. For each row: build subscription_info dict, call push client
  3. If WebPush returns 404/410 (expired) → set enabled=false in DB
  4. Return summary dict: {"sent": N, "failed": M}
"""
```

**Key rules:**
- Import `push.client` locally (avoid circular imports)
- Never raise — catch per-subscription, log and continue
- Expired endpoints (410) → set `enabled = false` in DB, don't retry
- Return `{"sent": N, "failed": M}`

### `api/push_routes.py`

```python
router = APIRouter(prefix="/push", tags=["push"])

GET  /push/vapid-public-key   → {"public_key": VAPID_PUBLIC_KEY}  (no auth required)
POST /push/subscribe           → upsert subscription row for current user
DELETE /push/subscribe         → set enabled=false for matching endpoint
POST /push/test                → send a test push to current user (dev tool)
```

`POST /push/subscribe` body:
```json
{
  "endpoint": "https://...",
  "p256dh": "...",
  "auth": "..."
}
```

All endpoints except `GET /push/vapid-public-key` require `get_current_user` auth.

### `frontend/public/sw.js`

```js
self.addEventListener('push', event => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'TrueBrief';
  const options = {
    body: data.body || 'A new brief is ready.',
    icon: '/icon-192.png',
    badge: '/badge-72.png',
    data: { url: data.url || '/' },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.url));
});
```

### `hooks/usePushNotifications.ts`

```ts
// Returns { isSupported, isSubscribed, isLoading, subscribe, unsubscribe }
// subscribe(): registers SW, creates PushSubscription, POSTs to /api/v1/push/subscribe
// unsubscribe(): calls DELETE /api/v1/push/subscribe, unregisters browser subscription
```

### `components/PushNotificationToggle.tsx`

Simple toggle button that calls `subscribe()` / `unsubscribe()` from the hook. Shows:
- "Enable Notifications" when not subscribed
- "Disable Notifications" when subscribed
- Disabled state when browser doesn't support push or permission is denied

---

## Pipeline Integration

In `tasks/pipeline_task.py`, after a brief is successfully stored/delivered, add:

```python
from truebrief.tasks.push_task import send_push_notifications_task
send_push_notifications_task.delay(
    user_id=str(user_id),
    topic_name=topic_name,
    brief_id=str(brief_id),
)
```

---

## New Dependency

```
pywebpush>=2.0.0
```

Add to `requirements.txt`.

---

## Environment Variables

Add to `.env.example`:

```
VAPID_PRIVATE_KEY=<base64url-encoded private key>
VAPID_PUBLIC_KEY=<base64url-encoded public key>
VAPID_SUBJECT=mailto:admin@truebrief.ai
```

Generate VAPID keys with:
```python
from pywebpush import Vapid
vapid = Vapid()
vapid.generate_keys()
# vapid.private_key, vapid.public_key
```

---

## Tests (`tests/test_push.py`)

### Unit tests (no external calls)

1. **`test_send_push_no_key`** — with `VAPID_PRIVATE_KEY=""`, `send_push(...)` returns `False` without raising.
2. **`test_send_push_webpush_exception`** — mock `webpush` to raise `WebPushException`; assert returns `False`.
3. **`test_push_task_no_subscriptions`** — mock DB returns empty list; assert returns `{"sent": 0, "failed": 0}`.
4. **`test_push_task_sends`** — mock DB with one subscription; mock `send_push` to return True; assert `{"sent": 1, "failed": 0}`.
5. **`test_push_task_failed`** — mock `send_push` to return False; assert `{"sent": 0, "failed": 1}`.
6. **`test_subscribe_endpoint_upserts`** — unit test the upsert logic in push_routes.
7. **`test_vapid_public_key_endpoint`** — GET `/push/vapid-public-key` returns `{"public_key": ...}` (no auth).

---

## Acceptance Criteria

- [ ] `pytest tests/test_push.py` → 7/7 unit tests pass
- [ ] `GET /push/vapid-public-key` returns 200 with public_key field
- [ ] `POST /push/subscribe` stores subscription row in DB
- [ ] `DELETE /push/subscribe` disables subscription
- [ ] `POST /push/test` returns 200 with status field
- [ ] Service worker (`/sw.js`) is accessible at the root
- [ ] `PushNotificationToggle` renders in settings page
- [ ] `npm run build` from `frontend/` passes
- [ ] `pytest tests/` → all existing tests still pass

---

## Commit

```
p3-s16: web push notifications via VAPID + service worker
```
