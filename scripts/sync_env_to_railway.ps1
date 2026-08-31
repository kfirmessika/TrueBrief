# Syncs local .env to Railway Worker + API services
# Run from the project root: .\scripts\sync_env_to_railway.ps1

$envFile = Join-Path $PSScriptRoot ".." ".env"
$projectId = "fde2d977-05d6-4e51-af1c-a783d1985fe9"
$workerServiceId = "cfeed7ce-9c2f-4a44-861f-2f84a23e1634"
$apiServiceId = "17a42f13-e1c2-48f1-a039-43a7fa512bef"

# Variables to skip (local-only or Railway-managed)
$skip = @("GOOGLE_API_KEY_DEV", "TRACE_PIPELINE", "TRACE_MAX_CHARS", "REDIS_URL", "FRONTEND_URL")

$vars = @{}
foreach ($line in Get-Content $envFile) {
    if ($line -match "^([A-Z_]+)=(.*)$") {
        $key = $matches[1]
        $val = $matches[2].Trim('"').Trim("'")
        if ($key -notin $skip -and $val -ne "") {
            $vars[$key] = $val
        }
    }
}

Write-Host "Syncing $($vars.Count) variables to Railway..."

foreach ($svcId in @($workerServiceId, $apiServiceId)) {
    foreach ($kv in $vars.GetEnumerator()) {
        railway variables set "$($kv.Key)=$($kv.Value)" --service $svcId --project $projectId 2>&1 | Out-Null
    }
    Write-Host "Done: $svcId"
}

Write-Host "All done. Redeploy Worker + API in Railway to pick up changes."
