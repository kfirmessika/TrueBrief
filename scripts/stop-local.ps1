# TrueBrief — Local Dev Teardown
# Usage: .\scripts\stop-local.ps1
# Kills: Redis, FastAPI (port 8000), Celery worker+beat, Next.js (port 3000)

Write-Host "`n=== Stopping TrueBrief Local Dev ===" -ForegroundColor Cyan

# Kill processes on port 8000 (FastAPI / uvicorn)
$apiPids = netstat -ano | Select-String ":8000 " | ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique
foreach ($p in $apiPids) {
    if ($p -match '^\d+$') {
        Write-Host "  Killing FastAPI (port 8000) PID $p" -ForegroundColor Yellow
        Stop-Process -Id ([int]$p) -Force -ErrorAction SilentlyContinue
    }
}

# Kill processes on port 3000 (Next.js)
$fePids = netstat -ano | Select-String ":3000 " | ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique
foreach ($p in $fePids) {
    if ($p -match '^\d+$') {
        Write-Host "  Killing Next.js (port 3000) PID $p" -ForegroundColor Yellow
        Stop-Process -Id ([int]$p) -Force -ErrorAction SilentlyContinue
    }
}

# Kill Celery worker and beat
$celeryProcs = Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -match "celery" }
foreach ($proc in $celeryProcs) {
    Write-Host "  Killing Celery PID $($proc.ProcessId)" -ForegroundColor Yellow
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
}

# Kill uvicorn if not caught by port scan
$uvicornProcs = Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -match "uvicorn" }
foreach ($proc in $uvicornProcs) {
    Write-Host "  Killing uvicorn PID $($proc.ProcessId)" -ForegroundColor Yellow
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
}

# Kill Redis
$redisProcs = Get-WmiObject Win32_Process | Where-Object { $_.Name -match "redis-server" }
foreach ($proc in $redisProcs) {
    Write-Host "  Killing Redis PID $($proc.ProcessId)" -ForegroundColor Yellow
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
}

Write-Host "`n=== All services stopped ===`n" -ForegroundColor Green
