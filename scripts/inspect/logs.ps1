# TrueBrief Railway Log Tailer
# Usage:
#   .\scripts\inspect\logs.ps1 -Service api
#   .\scripts\inspect\logs.ps1 -Service worker
#   .\scripts\inspect\logs.ps1 -Service beat
#   .\scripts\inspect\logs.ps1 -Service frontend
#   .\scripts\inspect\logs.ps1 -Service api -Tail 50
#   .\scripts\inspect\logs.ps1 -Service api -Follow   # live stream

param(
    [ValidateSet("api", "worker", "beat", "frontend", "Redis")]
    [string]$Service = "api",
    [int]$Tail = 100,
    [switch]$Follow
)

$ServiceMap = @{
    "api"      = "api"
    "worker"   = "Worker"
    "beat"     = "Beat"
    "frontend" = "Frontend"
    "Redis"    = "Redis"
}

$svc = $ServiceMap[$Service]
Write-Host "Tailing Railway logs for service: $svc" -ForegroundColor Cyan

if ($Follow) {
    railway logs --service $svc
} else {
    railway logs --service $svc --tail $Tail
}
