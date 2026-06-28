---
name: run-truebrief-locally
description: Run TrueBrief on this machine — start the local stack (Redis + Celery worker + beat + FastAPI + Next.js), run a manual pipeline for one topic, or audit stored data. Use when asked to run, start, smoke-test, or reproduce something in the real app rather than just unit tests. Covers REDIS_URL and the Windows Redis requirement.
---

# Run TrueBrief Locally (Windows)

## Prerequisites
- **`REDIS_URL=redis://localhost:6379/0` must be in `.env`.** Without it Celery uses an in-memory broker — tasks don't persist and **beat won't run scheduled scans**. Redis binary: `C:\Program Files\Redis\redis-server.exe`.
- Backend Python: use the venv → `.venv/Scripts/python.exe`. Frontend: Node + `npm` in `frontend/`.
- API keys in `.env`: Supabase, Clerk, Tavily/Brave/Exa, `GOOGLE_API_KEY`/`GEMINI_API_KEY`, VAPID, SMTP, Paddle.

## Full stack (Redis + Celery worker + beat + FastAPI)
```powershell
.\scripts\start-local.ps1     # starts everything
.\scripts\stop-local.ps1      # stops everything
```
Individual pieces also exist: `scripts/start_worker.py`, `scripts/start_beat.py`. FastAPI serves the API; the frontend talks to `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`) + `/api/v1`.

## Frontend dev server (from `frontend/`)
```bash
npm run dev      # http://localhost:3000
```

## Run a single pipeline without Celery (fastest for iterating)
```bash
python scripts/run_pipeline.py "Iran War ceasefire deal"          # synchronous, prints the brief
python scripts/run_pipeline.py "your topic" --debug               # verbose logging
```

## Inspect / audit stored data
```bash
python scripts/audit_topic.py "iran"        # → reports/audit_iran_YYYYMMDD_HHMMSS.md
python scripts/test_connections.py          # check DB + API connectivity
python scripts/test_ayr.py                  # inspect AYR engine state
python scripts/smoke_scan.py                # quick end-to-end scan smoke
```
`audit_topic.py` dumps every fact (with event_date, source, story), all story nodes + summaries, all delivered briefs, and signal stats (% with event_date, source diversity) — the first place to look when quality is off.

## Quality benchmark (needs running DB + Gemini key)
```bash
python scripts/quality_benchmark.py "Iran War ceasefire deal"
```
See [[accuracy-eval]] for interpreting the output. Backend conventions: [[truebrief-backend]]. Frontend: [[truebrief-frontend]].
