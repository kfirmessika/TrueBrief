# TrueBrief — Local Dev Teardown
# Usage: .\scripts\stop-local.ps1
# Kills: Redis, FastAPI (port 8000), Celery worker+beat, Next.js (port 3000)
#
# Uses `taskkill /T` (tree-kill) instead of Stop-Process everywhere: Stop-Process only
# kills the exact PID, not its children, and Windows never cascade-kills a process tree
# on its own. numpy/OpenBLAS spawns its CPU thread pool as real child python.exe
# processes (see start-local.ps1's OPENBLAS_NUM_THREADS comment) — those were left
# orphaned by every prior stop, accumulating silently until they ate enough RAM to crash
# a real pipeline run (found 2026-07-31). start-local.ps1 now prevents new ones; the
# sweep below cleans up anything already orphaned from before that fix, or from a crash
# that skipped teardown entirely.

Write-Host "`n=== Stopping TrueBrief Local Dev ===" -ForegroundColor Cyan

function Stop-Tree($p) {
    # /T kills the whole process tree, not just this PID — that's the actual fix.
    taskkill /T /F /PID $p 2>&1 | Out-Null
}

# Kill processes on port 8000 (FastAPI / uvicorn)
$apiPids = netstat -ano | Select-String ":8000 " | ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique
foreach ($p in $apiPids) {
    if ($p -match '^\d+$') {
        Write-Host "  Killing FastAPI tree (port 8000) PID $p" -ForegroundColor Yellow
        Stop-Tree $p
    }
}

# Kill processes on port 3000 (Next.js)
$fePids = netstat -ano | Select-String ":3000 " | ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique
foreach ($p in $fePids) {
    if ($p -match '^\d+$') {
        Write-Host "  Killing Next.js tree (port 3000) PID $p" -ForegroundColor Yellow
        Stop-Tree $p
    }
}

# Kill Celery worker and beat
$celeryProcs = Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -match "celery" }
foreach ($proc in $celeryProcs) {
    Write-Host "  Killing Celery tree PID $($proc.ProcessId)" -ForegroundColor Yellow
    Stop-Tree $proc.ProcessId
}

# Kill uvicorn if not caught by port scan
$uvicornProcs = Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -match "uvicorn" }
foreach ($proc in $uvicornProcs) {
    Write-Host "  Killing uvicorn tree PID $($proc.ProcessId)" -ForegroundColor Yellow
    Stop-Tree $proc.ProcessId
}

# Kill Redis
$redisProcs = Get-WmiObject Win32_Process | Where-Object { $_.Name -match "redis-server" }
foreach ($proc in $redisProcs) {
    Write-Host "  Killing Redis PID $($proc.ProcessId)" -ForegroundColor Yellow
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
}

# Sweep: orphaned OpenBLAS/multiprocessing worker children whose parent is already
# gone (from before this fix existed, or a crash that skipped teardown). A living
# parent's children are already caught by the tree-kills above.
$orphans = Get-WmiObject Win32_Process | Where-Object {
    $_.CommandLine -match "multiprocessing-fork" -and
    -not (Get-Process -Id $_.ParentProcessId -ErrorAction SilentlyContinue)
}
foreach ($proc in $orphans) {
    Write-Host "  Killing orphaned worker PID $($proc.ProcessId) (parent $($proc.ParentProcessId) already dead)" -ForegroundColor Yellow
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
}

Write-Host "`n=== All services stopped ===`n" -ForegroundColor Green
