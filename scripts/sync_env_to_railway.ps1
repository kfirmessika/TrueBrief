# Syncs local .env to Railway Worker + API services (production environment).
# Run from the project root:  .\scripts\sync_env_to_railway.ps1
#
# Local .env is treated as the source of truth for SECRETS and provider switches
# (SEARCH_PROVIDER, EMBED_PROVIDER, GROQ_API_KEY, LINKUP_API_KEY, ...). Vars that
# are environment-specific ($skip below) are never pushed — pushing ENV=development
# to production would flip the app into dev mode (dev keys, dev behaviour).

$envFile = Join-Path $PSScriptRoot ".." ".env"
$projectId = "fde2d977-05d6-4e51-af1c-a783d1985fe9"
$workerServiceId = "cfeed7ce-9c2f-4a44-861f-2f84a23e1634"
$apiServiceId = "17a42f13-e1c2-48f1-a039-43a7fa512bef"

# Never push these — set per-environment in the Railway dashboard.
#   ENV / LOG_LEVEL           : environment-specific (local = development)
#   GOOGLE_API_KEY_DEV        : local-only dev key
#   TRACE_PIPELINE/_MAX_CHARS : founder debugging, off in prod by default
#   REDIS_URL / FRONTEND_URL  : Railway-managed / per-environment
$skip = @(
    "ENV", "LOG_LEVEL",
    "GOOGLE_API_KEY_DEV", "TRACE_PIPELINE", "TRACE_MAX_CHARS",
    "REDIS_URL", "FRONTEND_URL"
)

$vars = @{}
foreach ($line in Get-Content $envFile) {
    if ($line -match "^([A-Z_][A-Z0-9_]*)=(.*)$") {
        $key = $matches[1]
        $val = $matches[2].Trim('"').Trim("'")
        if ($key -notin $skip -and $val -ne "") {
            $vars[$key] = $val
        }
    }
}

Write-Host "Will sync $($vars.Count) variables to Railway (Worker + API):"
Write-Host ("  " + (($vars.Keys | Sort-Object) -join ", "))
Write-Host ""

foreach ($svcId in @($workerServiceId, $apiServiceId)) {
    foreach ($kv in $vars.GetEnumerator()) {
        railway variable set "$($kv.Key)=$($kv.Value)" --service $svcId --project $projectId --skip-deploys 2>&1 | Out-Null
    }
    Write-Host "Done: $svcId"
}

Write-Host ""
Write-Host "All done. Push to main (or redeploy Worker + API in Railway) to pick up changes."
