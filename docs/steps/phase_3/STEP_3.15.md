# STEP 3.15 — Email Digest

**Complexity:** 15 | **Model:** SONNET  
**Phase:** 3 — Frontend + Monetization

---

## Goal

Deliver a daily (or configurable-frequency) email digest to each user summarising their latest briefs across all subscribed topics. Email is sent via **Resend** (transactional email API). The digest is rendered from a Jinja2 HTML template and dispatched as a scheduled Celery Beat task.

---

## Architecture

```
Celery Beat (daily 08:00 UTC)
    └─► send_digest_task (celery task)
            ├─ Query users with digest_enabled = true
            ├─ For each user: fetch their most recent brief per topic (last 24h)
            ├─ If no new briefs → skip user (no empty email)
            ├─ Render HTML via Jinja2 template
            └─ POST to Resend API  →  email delivered
```

---

## New Files

| File | Purpose |
|---|---|
| `src/truebrief/digest/mailer.py` | Resend API client wrapper |
| `src/truebrief/digest/renderer.py` | Jinja2 template renderer |
| `src/truebrief/digest/templates/digest.html` | HTML email template |
| `src/truebrief/tasks/digest_task.py` | Celery task: `send_digest_task` |
| `src/truebrief/api/digest_routes.py` | REST endpoints for digest settings |
| `tests/test_digest.py` | Unit tests |

---

## Modified Files

| File | Change |
|---|---|
| `src/truebrief/tasks/celery_app.py` | Register `digest_task`; add beat schedule entry |
| `src/truebrief/api/server.py` | Mount `digest_routes` router |
| `src/truebrief/ledger/schema.sql` | Add `digest_settings` table |

---

## Schema

### New table: `digest_settings`

```sql
create table if not exists digest_settings (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references users(id) on delete cascade unique,
    enabled boolean default true,
    frequency text default 'daily',   -- 'daily' | 'weekly'
    send_hour_utc int default 8,       -- 0-23
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);
```

> **Note:** This table lives in the same Supabase project. Run via `apply_schema.py` or paste into Supabase SQL editor.

---

## Implementation Details

### `digest/mailer.py`

```python
"""
Resend Email Client — digest/mailer.py
Wraps the Resend API. Reads RESEND_API_KEY from env.
"""
import os
import logging
import resend

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_ADDRESS = os.getenv("DIGEST_FROM_EMAIL", "briefs@truebrief.ai")

def send_digest_email(to_email: str, subject: str, html_body: str) -> bool:
    """
    Send one digest email. Returns True on success, False on error.
    """
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — skipping email send.")
        return False
    resend.api_key = RESEND_API_KEY
    try:
        resend.Emails.send({
            "from": FROM_ADDRESS,
            "to": [to_email],
            "subject": subject,
            "html": html_body,
        })
        logger.info("Digest sent to %s", to_email)
        return True
    except Exception as exc:
        logger.error("Failed to send digest to %s: %s", to_email, exc)
        return False
```

### `digest/renderer.py`

Uses **Jinja2** (already an indirect dependency of FastAPI; add explicitly if needed).

```python
"""
Email Renderer — digest/renderer.py
Renders the Jinja2 HTML digest template.
"""
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)

def render_digest(user_name: str, briefs: list[dict]) -> str:
    """
    briefs: list of dicts with keys:
      topic_name, brief_id, summary_preview, delivered_at
    Returns rendered HTML string.
    """
    template = _env.get_template("digest.html")
    return template.render(user_name=user_name, briefs=briefs)
```

### `digest/templates/digest.html`

Clean responsive HTML email template. Should include:
- TrueBrief logo/wordmark header
- Personalized greeting (`Hi {{ user_name }}`)
- One card per brief: topic name, preview text, "Read Full Brief" CTA button linking to `https://app.truebrief.ai/brief/{{ brief.brief_id }}`
- Footer with unsubscribe link: `https://app.truebrief.ai/settings/digest?unsubscribe=true`
- Inline CSS only (email clients strip `<style>` tags)

### `tasks/digest_task.py`

```python
"""
Digest Task — tasks/digest_task.py

Celery Beat task: sends daily email digests to eligible users.

Schedule: daily at 08:00 UTC (configured in celery_app.py beat_schedule).

Logic:
  1. Query digest_settings where enabled = true
  2. For each user_id, fetch their user email from `users` table
  3. Fetch their subscribed topic_ids from topic_subscriptions
  4. For each topic, get the most recent brief delivered in the last
     `lookback_hours` window (default 25h to allow for drift)
  5. If no briefs found → skip this user
  6. Render HTML and send via mailer
  7. Log success/failure per user
"""
```

**Key rules for `digest_task.py`:**
- Import `mailer` and `renderer` locally (avoid circular imports at module level)
- `lookback_hours = 25` for daily, `169` for weekly (7 days + 1h buffer)
- Never raise — catch all exceptions per-user and continue to the next
- Return a summary dict: `{"sent": N, "skipped": M, "errors": K}`

### `api/digest_routes.py`

```python
router = APIRouter(prefix="/digest", tags=["digest"])

GET  /digest/settings      → return user's digest_settings row (or default)
PUT  /digest/settings      → upsert digest_settings (enabled, frequency, send_hour_utc)
POST /digest/preview       → trigger digest for the requesting user right now (dev tool)
```

All endpoints require `get_current_user` auth.

`PUT /digest/settings` body:
```json
{ "enabled": true, "frequency": "daily", "send_hour_utc": 8 }
```

---

## Celery Beat Schedule Entry

Add to `celery_app.py → beat_schedule`:

```python
"daily-digest": {
    "task": "truebrief.tasks.digest_task.send_digest_task",
    "schedule": crontab(hour=8, minute=0),
    "options": {"queue": "celery"},
},
```

Also add `"truebrief.tasks.digest_task"` to the `include` list.

---

## New Dependency

```
resend
jinja2
```

Add to `requirements.txt`. Jinja2 is likely already installed as a FastAPI transitive dep; add it explicitly for clarity.

---

## Environment Variables

Add to `.env.example`:

```
RESEND_API_KEY=re_xxxxxxxxxxxx
DIGEST_FROM_EMAIL=briefs@truebrief.ai
```

---

## Tests (`tests/test_digest.py`)

### Unit tests (no external calls)

1. **`test_render_digest_html`** — call `render_digest(user_name="Alice", briefs=[...])`, assert output contains "Alice", "Read Full Brief", topic name.
2. **`test_render_digest_empty`** — `briefs=[]` should not raise; output should still be valid HTML.
3. **`test_send_email_no_key`** — with `RESEND_API_KEY=""`, `send_digest_email(...)` returns `False` without raising.
4. **`test_send_email_api_error`** — mock `resend.Emails.send` to raise, assert returns `False`.
5. **`test_digest_task_skip_no_briefs`** — mock DB to return a user with no recent briefs; assert task returns `{"sent": 0, "skipped": 1, "errors": 0}`.
6. **`test_digest_task_sends`** — mock DB with one user + one brief; mock `send_digest_email` to return True; assert `{"sent": 1, "skipped": 0, "errors": 0}`.
7. **`test_digest_settings_upsert`** — unit test the PUT logic in isolation.

### Integration (smoke) test

8. **`test_digest_preview_endpoint`** — POST to `/api/v1/digest/preview` with a valid Clerk JWT; assert HTTP 200 and `{"status": "sent"}` or `{"status": "skipped"}`. Requires live backend + Resend key in env.

---

## Acceptance Criteria

- [ ] `pytest tests/test_digest.py` → 7/7 unit tests pass
- [ ] `POST /digest/preview` returns 200 with status field
- [ ] `GET /digest/settings` returns correct defaults for new user
- [ ] `PUT /digest/settings` persists changes (verify via GET)
- [ ] Beat schedule entry is correctly registered (visible in `celery inspect scheduled`)
- [ ] `npm run build` from `frontend/` passes (no frontend changes required, but ensure no regressions)
- [ ] `pytest tests/` → all existing tests still pass

---

## Commit

```
p3-s15: email digest via Resend + Celery Beat daily schedule
```
