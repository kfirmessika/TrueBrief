# Dev Server Toggle

Start, stop, or restart the local TrueBrief stack (Redis + Celery + FastAPI + Next.js).

## Usage

**Start the server:**
```powershell
.\scripts\start-local.ps1
```

**Stop the server:**
```powershell
.\scripts\stop-local.ps1
```

**Restart (stop + start):**
```powershell
.\scripts\stop-local.ps1; .\scripts\start-local.ps1
```

## What's Running
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Redis: localhost:6379

## Troubleshooting
- **Redis not found:** ensure `C:\Program Files\Redis\redis-server.exe` is installed
- **Ports already in use:** check for existing processes on 3000, 8000, 6379
- **REDIS_URL missing:** must be in `.env` for Celery persistence

