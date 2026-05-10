# Runbook: Tier Enforcement — Live Smoke Test

Use this guide to validate tier enforcement against a real Supabase instance and a running FastAPI server. The automated TestClient suite (`tests/test_tier_enforcement_intg.py`) covers the wiring; this runbook covers the cases that depend on real DB state (`last_scan_at`, `user_subscriptions`, etc.).

## Prerequisites

1. `.env` populated with valid `SUPABASE_URL` and `SUPABASE_KEY`.
2. The `topics` table has a `last_scan_at` column. If absent, run:
   ```sql
   ALTER TABLE topics ADD COLUMN IF NOT EXISTS last_scan_at TIMESTAMPTZ;
   ```
3. At least one row in `user_subscriptions` per test user (one per tier).
4. Celery worker + Redis available if you intend to verify scan queueing end-to-end. Speed-limit and topic-cap checks themselves do **not** require Celery — they fire before the task is queued.

## 1. Start the API server

```powershell
uvicorn truebrief.api.server:app --reload --port 8000
```

Confirm health:
```powershell
curl http://localhost:8000/health
# {"status":"ok"}
```

## 2. Seed test users

In Supabase SQL editor:

```sql
-- Free tier user
INSERT INTO user_subscriptions (user_id, tier, status)
VALUES ('00000000-0000-0000-0000-0000000000aa', 'free', 'active')
ON CONFLICT (user_id) DO UPDATE SET tier = 'free';

-- Pro tier user
INSERT INTO user_subscriptions (user_id, tier, status)
VALUES ('00000000-0000-0000-0000-0000000000bb', 'pro', 'active')
ON CONFLICT (user_id) DO UPDATE SET tier = 'pro';

-- Power tier user
INSERT INTO user_subscriptions (user_id, tier, status)
VALUES ('00000000-0000-0000-0000-0000000000cc', 'power', 'active')
ON CONFLICT (user_id) DO UPDATE SET tier = 'power';
```

## 3. Verify GET /billing/tiers

```powershell
curl http://localhost:8000/api/v1/billing/tiers | jq
```

Expected: each tier returns `max_topics`, `min_interval_hours`, `sources`, `private_topics`. The `free` row should show `max_topics=2`, `min_interval_hours=24.0`.

## 4. Topic Cap — Free Tier (HTTP 402)

Add the first two topics, then try a third:

```powershell
$U = "00000000-0000-0000-0000-0000000000aa"
curl -X POST http://localhost:8000/api/v1/topics `
     -H "Content-Type: application/json" `
     -d "{`"raw_query`":`"topic-1`",`"user_id`":`"$U`"}"
curl -X POST http://localhost:8000/api/v1/topics `
     -H "Content-Type: application/json" `
     -d "{`"raw_query`":`"topic-2`",`"user_id`":`"$U`"}"
# Third call must fail
curl -X POST http://localhost:8000/api/v1/topics `
     -H "Content-Type: application/json" `
     -d "{`"raw_query`":`"topic-3`",`"user_id`":`"$U`"}" -i
```

**Expected:** Third call returns `HTTP/1.1 402 Payment Required` with body containing `"Upgrade your plan to add more topics."`.

Cleanup:
```sql
DELETE FROM topic_subscriptions WHERE user_id = '00000000-0000-0000-0000-0000000000aa';
DELETE FROM topics WHERE raw_query IN ('topic-1','topic-2','topic-3');
```

## 5. Speed Limit — Free Tier (HTTP 429)

Pick a topic with a recent `last_scan_at`:

```sql
UPDATE topics
SET last_scan_at = NOW() - INTERVAL '2 hours'
WHERE raw_query = 'topic-1'
RETURNING id;
```

Trigger a scan with the user_id:

```powershell
$T = "<topic_id_from_above>"
$U = "00000000-0000-0000-0000-0000000000aa"
curl -X POST "http://localhost:8000/api/v1/topics/$T/scan?user_id=$U" -i
```

**Expected:** `HTTP/1.1 429 Too Many Requests`, detail mentions `Free plan requires 24h between scans`.

Now move the timestamp back further and retry:

```sql
UPDATE topics SET last_scan_at = NOW() - INTERVAL '25 hours' WHERE id = '<T>';
```

```powershell
curl -X POST "http://localhost:8000/api/v1/topics/$T/scan?user_id=$U" -i
```

**Expected:** `HTTP/1.1 200 OK` with `{"status":"queued","task_id":"...","topic_id":"..."}`.

## 6. Pro Tier (HTTP 429 within 1h)

```sql
UPDATE topics SET last_scan_at = NOW() - INTERVAL '20 minutes' WHERE id = '<T>';
```

```powershell
curl -X POST "http://localhost:8000/api/v1/topics/$T/scan?user_id=00000000-0000-0000-0000-0000000000bb" -i
```

**Expected:** `429`. Move timestamp to 90 minutes ago, repeat → `200`.

## 7. Power Tier — Unlimited

Repeat step 4 with the power user, adding 3+ topics. All should succeed with `200`.

```powershell
$U = "00000000-0000-0000-0000-0000000000cc"
1..3 | ForEach-Object {
  curl -X POST http://localhost:8000/api/v1/topics `
       -H "Content-Type: application/json" `
       -d "{`"raw_query`":`"power-topic-$_`",`"user_id`":`"$U`"}" -i
}
```

## 8. Bypass Path (no user_id)

A request **without** `user_id` should bypass tier enforcement entirely. Useful for admin/debug; verify it still works:

```powershell
curl -X POST http://localhost:8000/api/v1/topics `
     -H "Content-Type: application/json" `
     -d '{"raw_query":"anonymous-topic"}'
```

Expected: `200`.

## 9. Cleanup

```sql
DELETE FROM topic_subscriptions
WHERE user_id IN ('00000000-0000-0000-0000-0000000000aa',
                  '00000000-0000-0000-0000-0000000000bb',
                  '00000000-0000-0000-0000-0000000000cc');
DELETE FROM topics WHERE raw_query LIKE 'topic-%' OR raw_query LIKE 'power-topic-%' OR raw_query = 'anonymous-topic';
DELETE FROM user_subscriptions
WHERE user_id IN ('00000000-0000-0000-0000-0000000000aa',
                  '00000000-0000-0000-0000-0000000000bb',
                  '00000000-0000-0000-0000-0000000000cc');
```

## Pass Criteria Summary

| Check | Expected |
|------|----------|
| `GET /billing/tiers` | 200, all tiers show `min_interval_hours` |
| Free user → 3rd topic | 402 + upgrade message |
| Free user → scan within 24h | 429 |
| Free user → scan after 25h | 200, task queued |
| Pro user → scan within 1h | 429 |
| Pro user → 16th topic | 402 |
| Power user → 5+ topics | all 200 |
| Anonymous (no user_id) | 200 (enforcement bypassed) |
