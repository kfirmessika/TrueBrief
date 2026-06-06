# TrueBrief -- Local Dev Startup
# Mirrors production Railway services as closely as possible.
# Usage: .\scripts\start-local.ps1
#
# Services started (each in its own cmd window):
#   [1] Redis         -- broker + result backend (port 6379)
#   [2] FastAPI       -- uvicorn truebrief.api.server:app (port 8000, --reload)
#   [3] Celery Worker -- same command as railway.worker.toml (-P solo for Windows)
#   [4] Celery Beat   -- same command as railway.beat.toml
#   [5] Next.js       -- npm run dev (port 3000)
#
# Production parity notes:
#   - PYTHONPATH set to $ROOT\src, matching PYTHONPATH=/app/src on Railway
#   - Celery app: truebrief.tasks.celery_app (matches railway.worker.toml)
#   - Worker uses -P solo instead of -c 2 (Windows has no fork; same task logic)
#   - uvicorn uses --reload for hot reload; prod does not (intentional dev convenience)

$ROOT     = Split-Path $PSScriptRoot -Parent
$PYTHON   = "$ROOT\.venv\Scripts\python.exe"
$FRONTEND = "$ROOT\frontend"
$SRC      = "$ROOT\src"
$REDIS    = "C:\Program Files\Redis\redis-server.exe"

Write-Host ""
Write-Host "=== TrueBrief Local Dev ===" -ForegroundColor Cyan
Write-Host "  Mirrors: railway.toml + railway.worker.toml + railway.beat.toml" -ForegroundColor DarkGray

# [1] Redis
Write-Host ""
Write-Host "[1/5] Starting Redis on port 6379 ..." -ForegroundColor Yellow
if (Test-Path $REDIS) {
    Start-Process -FilePath "cmd.exe" -ArgumentList '/k', "title TrueBrief-Redis && `"$REDIS`"" -WindowStyle Normal
} else {
    Start-Process -FilePath "cmd.exe" -ArgumentList '/k', 'title TrueBrief-Redis && redis-server' -WindowStyle Normal
}
Start-Sleep -Seconds 2

# [2] FastAPI  (prod: uvicorn truebrief.api.server:app --host 0.0.0.0 --port $PORT)
Write-Host "[2/5] Starting FastAPI on http://localhost:8000 ..." -ForegroundColor Yellow
Start-Process -FilePath "cmd.exe" -ArgumentList '/k', "title TrueBrief-API && cd /d `"$ROOT`" && set PYTHONPATH=$SRC && `"$PYTHON`" -m uvicorn truebrief.api.server:app --host 0.0.0.0 --port 8000 --reload" -WindowStyle Normal
Start-Sleep -Seconds 3

# [3] Celery Worker  (prod: PYTHONPATH=/app/src celery -A truebrief.tasks.celery_app worker --loglevel=info -c 2)
Write-Host "[3/5] Starting Celery worker ..." -ForegroundColor Yellow
Start-Process -FilePath "cmd.exe" -ArgumentList '/k', "title TrueBrief-Worker && cd /d `"$ROOT`" && set PYTHONPATH=$SRC && `"$PYTHON`" -m celery -A truebrief.tasks.celery_app worker --loglevel=info -P solo" -WindowStyle Normal
Start-Sleep -Seconds 2

# [4] Celery Beat  (prod: PYTHONPATH=/app/src celery -A truebrief.tasks.celery_app beat --loglevel=info)
Write-Host "[4/5] Starting Celery Beat scheduler ..." -ForegroundColor Yellow
Start-Process -FilePath "cmd.exe" -ArgumentList '/k', "title TrueBrief-Beat && cd /d `"$ROOT`" && set PYTHONPATH=$SRC && `"$PYTHON`" -m celery -A truebrief.tasks.celery_app beat --loglevel=info" -WindowStyle Normal
Start-Sleep -Seconds 1

# [5] Next.js  (prod: npm start / local: npm run dev with hot reload)
Write-Host "[5/5] Starting Next.js on http://localhost:3000 ..." -ForegroundColor Yellow
Start-Process -FilePath "cmd.exe" -ArgumentList '/k', "title TrueBrief-Frontend && cd /d `"$FRONTEND`" && npm run dev" -WindowStyle Normal

Start-Sleep -Seconds 4
Write-Host ""
Write-Host "=== All 5 services started ===" -ForegroundColor Green
Write-Host "  Frontend : http://localhost:3000" -ForegroundColor White
Write-Host "  API      : http://localhost:8000" -ForegroundColor White
Write-Host "  API docs : http://localhost:8000/docs" -ForegroundColor White
Write-Host "  Redis    : localhost:6379" -ForegroundColor White
Write-Host ""
Write-Host "To stop everything: .\scripts\stop-local.ps1" -ForegroundColor DarkGray
Write-Host ""
