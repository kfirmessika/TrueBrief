# TrueBrief — Operations Guide

## Live URLs

| Service | URL |
|---|---|
| **Frontend (UI)** | https://frontend-production-c9fa.up.railway.app |
| **API** | https://api-production-0bd2.up.railway.app |
| **API health check** | https://api-production-0bd2.up.railway.app/health |
| **Railway dashboard** | https://railway.com/project/fde2d977-05d6-4e51-af1c-a783d1985fe9 |
| **Supabase dashboard** | https://supabase.com/dashboard/project/lopsqdnfivdpsvsqzwdc |

---

## Using the App as a User

1. Go to the frontend URL above
2. Click **Sign Up** → creates a Clerk account (email + password, or Google)
3. You land on `/dashboard` → click **Add Topic** to create your first topic
4. The worker picks it up within ~1 minute (Beat fires every 60s) and runs the full pipeline
5. Results appear at `/topics/[id]` — three tabs: **Briefs / Stories / Insights**
6. Brief history at `/history`
7. Settings (account, notifications) at `/settings`

**Sign-in URL directly:** `<frontend-url>/sign-in`

---

## Admin: Cost & Usage

There is a built-in cost endpoint — any logged-in user can call it right now (no role gate yet):

```bash
# Replace YOUR_JWT with the token from browser devtools (Application → Local Storage → clerk token)
curl "https://api-production-0bd2.up.railway.app/admin/cost-summary?days=7" \
  -H "Authorization: Bearer YOUR_JWT"
```

Returns:
```json
{
  "period_days": 7,
  "total_runs": 12,
  "total_cost_usd": 0.003241,
  "avg_cost_per_run_usd": 0.000270,
  "total_input_tokens": 48200,
  "total_output_tokens": 9100,
  "by_stage": [ ... per pipeline stage breakdown ... ],
  "by_day": [ ... cost per day ... ]
}
```

Change `days=7` to `days=30` for a monthly view.

### What's logged automatically
Every pipeline run writes two tables in Supabase:

| Table | What it records |
|---|---|
| `pipeline_run` | One row per scan: topic, duration, status, articles found |
| `llm_call_log` | One row per Gemini call: stage, model, tokens in/out, cost_usd, latency_ms |

**To query directly in Supabase SQL Editor:**
```sql
-- Cost last 7 days
SELECT date(created_at), sum(cost_usd) as daily_cost, count(*) as calls
FROM llm_call_log
WHERE created_at > now() - interval '7 days'
GROUP BY 1 ORDER BY 1 DESC;

-- Runs per topic
SELECT t.raw_query, count(*) as runs, avg(pr.duration_seconds) as avg_sec
FROM pipeline_run pr
JOIN topics t ON t.id = pr.topic_id
GROUP BY 1 ORDER BY 2 DESC;

-- Failures
SELECT topic_id, error_message, started_at
FROM pipeline_run
WHERE status = 'error'
ORDER BY started_at DESC LIMIT 20;
```

---

## Stopping the System

**Stop scheduling (no more automatic scans — cheapest option):**
```powershell
cd "d:/projects/Apps/TrueBrief"
railway.cmd service beat
railway.cmd down
```

**Stop the worker too (no tasks processed at all):**
```powershell
railway.cmd service worker
railway.cmd down
```

**Stop everything (UI goes offline):**
```powershell
foreach ($svc in @("api","worker","beat","frontend")) {
    railway.cmd service $svc
    railway.cmd down
}
```

**Restart a stopped service:**
```powershell
cd "d:/projects/Apps/TrueBrief"
railway.cmd service beat
railway.cmd up --detach

railway.cmd service worker
railway.cmd up --detach
```

---

## Watching Logs in Real Time

```powershell
cd "d:/projects/Apps/TrueBrief"

# What's the pipeline doing right now?
railway.cmd service worker && railway.cmd logs

# Is the scheduler firing?
railway.cmd service beat && railway.cmd logs

# API errors?
railway.cmd service api && railway.cmd logs
```

---

## Supabase: Keeping the Project Alive

Supabase **free tier pauses projects after 7 days of inactivity**.

- Resume: supabase.com/dashboard → your project → **Restore project**
- To prevent pauses: upgrade to Pro ($25/month) or ping the DB at least once a week
- Quick ping to keep it alive: `curl "https://api-production-0bd2.up.railway.app/health"` (the API touches Supabase on startup)

---

## Railway Costs (approx.)

| Service | Idle cost/day | Under load |
|---|---|---|
| API | ~$0.05 | ~$0.10 |
| Worker | ~$0.05 | ~$0.20 |
| Beat | ~$0.02 | ~$0.02 |
| Frontend | ~$0.03 | ~$0.05 |
| Redis | ~$0.05 | ~$0.05 |
| **Total** | **~$0.20/day** | **~$0.40/day** |

Railway charges by CPU/memory usage. Idle services cost almost nothing.
Gemini API (Google): first **1M tokens/day free** on Flash Lite. Current usage is well under that.

---

## API Docs (Swagger)

All endpoints are documented at:
```
https://api-production-0bd2.up.railway.app/docs
```
Interactive — you can paste your JWT and test any endpoint directly in the browser.

---

## What Does NOT Exist Yet (from roadmap)

- No admin UI dashboard (A.6 — not built)
- No per-user usage limits shown in UI (billing enforcement exists in code but Paddle not set up)
- No email digests (Resend not configured — needs a real domain)
- No web push notifications (VAPID keys set but `push_subscriptions` table needs to be created)
