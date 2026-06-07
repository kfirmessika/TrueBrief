# TrueBrief Dev Manager
# Usage:
#   .\dev.ps1          -- kill everything then start fresh
#   .\dev.ps1 start    -- same as above
#   .\dev.ps1 stop     -- kill everything only
#   .\dev.ps1 status   -- show what is running

param([string]$Command = "start")

$ROOT     = $PSScriptRoot
$PYTHON   = "$ROOT\.venv\Scripts\python.exe"
$SRC      = "$ROOT\src"
$FRONTEND = "$ROOT\frontend"
$REDIS    = "C:\Program Files\Redis\redis-server.exe"

# ---------------------------------------------------------------------------
# Kill all TrueBrief processes aggressively by command-line pattern
# ---------------------------------------------------------------------------
function Stop-All {
    $killed = 0
    # Match any python process running celery or uvicorn for this app
    $patterns = @(
        "uvicorn truebrief",
        "celery.*truebrief",
        "truebrief.*celery",
        "celery_app",
        "-m celery -A",
        "-m uvicorn truebrief"
    )

    $allProcs = Get-WmiObject Win32_Process -ErrorAction SilentlyContinue
    foreach ($proc in $allProcs) {
        $cmd = $proc.CommandLine
        if (-not $cmd) { continue }
        $match = $false
        foreach ($pat in $patterns) { if ($cmd -match $pat) { $match = $true; break } }
        if ($match) {
            $r = taskkill /F /T /PID $proc.ProcessId 2>&1
            if ($r -match "SUCCESS") {
                $short = $cmd.Substring(0, [Math]::Min(55, $cmd.Length))
                Write-Host "  killed [$($proc.ProcessId)] $short..." -ForegroundColor DarkGray
                $killed++
            }
        }
    }

    # Also nuke by port to catch anything missed
    foreach ($port in @(8000, 3000)) {
        $pids = netstat -ano 2>$null | Select-String ":$port " | ForEach-Object {
            ($_ -split '\s+')[-1]
        } | Where-Object { $_ -match '^\d+$' } | Sort-Object -Unique
        foreach ($p in $pids) {
            $r = taskkill /F /T /PID $p 2>&1
            if ($r -match "SUCCESS") { $killed++ }
        }
    }

    # Next.js node processes for this project
    $nodes = Get-WmiObject Win32_Process -ErrorAction SilentlyContinue |
             Where-Object { $_.Name -eq "node.exe" -and $_.CommandLine -match "TrueBrief" }
    foreach ($proc in $nodes) {
        $r = taskkill /F /PID $proc.ProcessId 2>&1
        if ($r -match "SUCCESS") { $killed++ }
    }

    return $killed
}

# ---------------------------------------------------------------------------
# Wait for a TCP port to open (returns $true / $false)
# ---------------------------------------------------------------------------
function Wait-Port([int]$Port, [int]$Sec = 20) {
    $deadline = (Get-Date).AddSeconds($Sec)
    while ((Get-Date) -lt $deadline) {
        try {
            $t = New-Object System.Net.Sockets.TcpClient
            $t.Connect("127.0.0.1", $Port)
            $t.Close()
            return $true
        } catch { Start-Sleep -Milliseconds 400 }
    }
    return $false
}

# ---------------------------------------------------------------------------
# Check if a port is open right now
# ---------------------------------------------------------------------------
function Test-Port([int]$Port) {
    try {
        $t = New-Object System.Net.Sockets.TcpClient
        $t.Connect("127.0.0.1", $Port)
        $t.Close()
        return $true
    } catch { return $false }
}

# ---------------------------------------------------------------------------
# Print service status table
# ---------------------------------------------------------------------------
function Show-Status {
    Write-Host ""
    $svcs = @(
        @{Name="Redis   "; Port=6379},
        @{Name="FastAPI "; Port=8000},
        @{Name="Next.js "; Port=3000}
    )
    foreach ($s in $svcs) {
        $up = Test-Port $s.Port
        Write-Host "  $($s.Name)  $($s.Port)   " -NoNewline
        if ($up) { Write-Host "UP" -ForegroundColor Green } else { Write-Host "DOWN" -ForegroundColor Red }
    }

    # Count top-level python.exe celery processes (children of cmd.exe, not of another python)
    # Note: Celery on Windows spawns 1 child python per worker/beat -- count only parents (ParentProcessId = cmd.exe)
    $allProcs = Get-WmiObject Win32_Process -ErrorAction SilentlyContinue
    $cmdPids  = ($allProcs | Where-Object { $_.Name -eq "cmd.exe" }).ProcessId

    $wc = @($allProcs | Where-Object {
        $_.Name -eq "python.exe" -and
        $cmdPids -contains $_.ParentProcessId -and
        ($_.CommandLine -match "celery_app worker" -or $_.CommandLine -match "celery -A.*worker")
    }).Count
    $bc = @($allProcs | Where-Object {
        $_.Name -eq "python.exe" -and
        $cmdPids -contains $_.ParentProcessId -and
        ($_.CommandLine -match "celery_app beat" -or $_.CommandLine -match "celery -A.*beat")
    }).Count

    Write-Host "  Worker      -    " -NoNewline
    if ($wc -gt 0) { Write-Host "UP" -ForegroundColor Green } else { Write-Host "DOWN" -ForegroundColor Red }
    Write-Host "  Beat        -    " -NoNewline
    if ($bc -gt 0) { Write-Host "UP" -ForegroundColor Green } else { Write-Host "DOWN" -ForegroundColor Red }
    Write-Host ""
}

# ===========================================================================
# STATUS
# ===========================================================================
if ($Command -eq "status") {
    Write-Host "`n=== TrueBrief Status ===" -ForegroundColor Cyan
    Show-Status
    exit 0
}

# ===========================================================================
# STOP
# ===========================================================================
if ($Command -eq "stop") {
    Write-Host "`n=== Stopping TrueBrief ===" -ForegroundColor Cyan
    $n = Stop-All
    Write-Host "`n  Done. Killed $n processes.`n" -ForegroundColor Green
    $global:LASTEXITCODE = 0; exit 0
}

# ===========================================================================
# START  (default -- kills first, then starts)
# ===========================================================================
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  TrueBrief Dev Manager" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Step 1 -- Kill
Write-Host "`n[1/5] Killing old processes..." -ForegroundColor Yellow
$n = Stop-All
Start-Sleep -Seconds 1
Write-Host "      Cleared $n processes." -ForegroundColor DarkGray

# Step 2 -- Redis
Write-Host "[2/5] Redis (port 6379)..." -ForegroundColor Yellow
if (Test-Port 6379) {
    Write-Host "      Already running (Windows Service OK)." -ForegroundColor DarkGray
} else {
    $redisCmd = if (Test-Path $REDIS) { "`"$REDIS`"" } else { "redis-server" }
    Start-Process "cmd.exe" -ArgumentList "/k", "title TrueBrief-Redis && $redisCmd" -WindowStyle Minimized
    if (Wait-Port 6379 15) {
        Write-Host "      Redis is up." -ForegroundColor DarkGray
    } else {
        Write-Host "      WARNING: Redis did not start on port 6379!" -ForegroundColor Red
    }
}

# Step 3 -- FastAPI
Write-Host "[3/5] FastAPI (port 8000)..." -ForegroundColor Yellow
$apiCmd = "title TrueBrief-API && cd /d `"$ROOT`" && set PYTHONPATH=$SRC && `"$PYTHON`" -m uvicorn truebrief.api.server:app --host 0.0.0.0 --port 8000 --reload"
Start-Process "cmd.exe" -ArgumentList "/k", $apiCmd -WindowStyle Minimized
if (Wait-Port 8000 25) {
    Write-Host "      FastAPI is up." -ForegroundColor DarkGray
} else {
    Write-Host "      WARNING: FastAPI did not start! Check the API window." -ForegroundColor Red
}

# Step 4 -- Celery
Write-Host "[4/5] Celery worker + beat..." -ForegroundColor Yellow
$workerCmd = "title TrueBrief-Worker && cd /d `"$ROOT`" && set PYTHONPATH=$SRC && `"$PYTHON`" -m celery -A truebrief.tasks.celery_app worker --loglevel=info -P solo"
$beatCmd   = "title TrueBrief-Beat   && cd /d `"$ROOT`" && set PYTHONPATH=$SRC && `"$PYTHON`" -m celery -A truebrief.tasks.celery_app beat   --loglevel=info"
Start-Process "cmd.exe" -ArgumentList "/k", $workerCmd -WindowStyle Minimized
Start-Sleep -Seconds 1
Start-Process "cmd.exe" -ArgumentList "/k", $beatCmd   -WindowStyle Minimized
Start-Sleep -Seconds 5

$ap = Get-WmiObject Win32_Process -ErrorAction SilentlyContinue
$cmdP = ($ap | Where-Object { $_.Name -eq "cmd.exe" }).ProcessId
$wc = @($ap | Where-Object { $_.Name -eq "python.exe" -and $cmdP -contains $_.ParentProcessId -and ($_.CommandLine -match "celery_app worker" -or $_.CommandLine -match "celery -A.*worker") }).Count
$bc = @($ap | Where-Object { $_.Name -eq "python.exe" -and $cmdP -contains $_.ParentProcessId -and ($_.CommandLine -match "celery_app beat"   -or $_.CommandLine -match "celery -A.*beat") }).Count
$wStatus = if ($wc -gt 0) { "UP" } else { "DOWN - check the Worker window" }
$bStatus = if ($bc -gt 0) { "UP" } else { "DOWN - check the Beat window" }
Write-Host "      Worker: $wStatus   Beat: $bStatus" -ForegroundColor DarkGray

# Step 5 -- Next.js
Write-Host "[5/5] Next.js (port 3000)..." -ForegroundColor Yellow
$feCmd = "title TrueBrief-Frontend && cd /d `"$FRONTEND`" && npm run dev"
Start-Process "cmd.exe" -ArgumentList "/k", $feCmd -WindowStyle Minimized
if (Wait-Port 3000 45) {
    Write-Host "      Next.js is up." -ForegroundColor DarkGray
} else {
    Write-Host "      Next.js is still compiling -- it will be ready soon." -ForegroundColor Yellow
}

# Summary
Write-Host "`n=========================================="
Show-Status
Write-Host "  http://localhost:3000   (frontend)" -ForegroundColor White
Write-Host "  http://localhost:8000   (API)" -ForegroundColor White
Write-Host "  http://localhost:8000/docs  (API docs)" -ForegroundColor White
Write-Host ""
Write-Host "  Stop:    .\dev.ps1 stop" -ForegroundColor DarkGray
Write-Host "  Status:  .\dev.ps1 status" -ForegroundColor DarkGray
Write-Host ""
$global:LASTEXITCODE = 0; exit 0
