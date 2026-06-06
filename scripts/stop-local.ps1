# TrueBrief — Local Dev Teardown
# Usage: .\scripts\stop-local.ps1
# Kills: Redis, FastAPI (port 8000), Celery worker+beat, Next.js (port 3000)

Write-Host "`n=== Stopping TrueBrief Local Dev ===" -ForegroundColor Cyan

# Kill processes on port 8000 (FastAPI)
$api = netstat -ano | Select-String ":8000 " | ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique
foreach ($pid in $api) {
    if ($pid -match '^\d+$') {
        Write-Host "  Killing FastAPI (port 8000) PID $pid" -ForegroundColor Yellow
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    }
}

# Kill processes on port 3000 (Next.js)
$fe = netstat -ano | Select-String ":3000 " | ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique
foreach ($pid in $fe) {
    if ($pid -match '^\d+$') {
        Write-Host "  Killing Next.js (port 3000) PID $pid" -ForegroundColor Yellow
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    }
}

# Kill Celery worker and beat
$celery = Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -match "celery" }
foreach ($proc in $celery) {
    Write-Host "  Killing Celery PID $($proc.ProcessId)" -ForegroundColor Yellow
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
}

# Kill Redis
$redis = Get-WmiObject Win32_Process | Where-Object { $_.Name -match "redis-server" }
foreach ($proc in $redis) {
    Write-Host "  Killing Redis PID $($proc.ProcessId)" -ForegroundColor Yellow
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
}

Write-Host "`n=== All services stopped ===`n" -ForegroundColor Green
