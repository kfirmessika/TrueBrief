# railway_deploy.ps1
# Full Railway deployment from code — no UI needed.
# Run from the project root: .\scripts\railway_deploy.ps1
#
# Prerequisites:
#   npm install -g @railway/cli
#   railway login

Set-StrictMode -Off
$ErrorActionPreference = "Stop"

# ── Helpers ────────────────────────────────────────────────────────────────

function Log($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok($msg)  { Write-Host "    OK: $msg" -ForegroundColor Green }
function Die($msg) { Write-Host "    ERROR: $msg" -ForegroundColor Red; exit 1 }

# Parse .env into a hashtable (skip comments and blank lines)
function Read-DotEnv($path) {
    $vars = @{}
    foreach ($line in Get-Content $path) {
        $line = $line.Trim()
        if ($line -eq "" -or $line.StartsWith("#")) { continue }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { continue }
        $key   = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1).Trim().Trim('"')
        if ($key -ne "") { $vars[$key] = $value }
    }
    return $vars
}

# Set a batch of variables on a Railway service
function Set-ServiceVars($serviceName, $vars) {
    $pairs = @()
    foreach ($k in $vars.Keys) {
        $v = $vars[$k]
        $pairs += "$k=$v"
    }
    if ($pairs.Count -eq 0) { return }
    # Railway CLI: railway variables set KEY=VAL KEY2=VAL2 --service NAME
    $args = @("variables", "set") + $pairs + @("--service", $serviceName)
    & railway @args
    if ($LASTEXITCODE -ne 0) { Die "Failed to set vars on $serviceName" }
}

# ── Load .env ──────────────────────────────────────────────────────────────

$envPath = Join-Path $PSScriptRoot "..\\.env"
if (-not (Test-Path $envPath)) { Die ".env not found at $envPath" }
$env = Read-DotEnv $envPath
Log "Loaded .env ($($env.Count) variables)"

# ── Check railway CLI ──────────────────────────────────────────────────────

try { railway --version | Out-Null } catch { Die "railway CLI not found. Run: npm install -g @railway/cli" }
Log "Railway CLI found"

# ── Project ────────────────────────────────────────────────────────────────

Log "Linking to Railway project (will prompt if not already linked)"
railway status 2>$null
if ($LASTEXITCODE -ne 0) {
    Log "No project linked — creating new project 'TrueBrief'"
    railway init --name TrueBrief
}

# ── Redis ──────────────────────────────────────────────────────────────────

Log "Adding Redis plugin"
railway add --plugin redis 2>$null
Ok "Redis provisioned (or already exists)"

# Wait a moment for Redis URL to be available
Start-Sleep -Seconds 5

Log "Fetching REDIS_URL from Railway"
$REDIS_URL = (railway variables get REDIS_URL --service redis 2>$null).Trim()
if (-not $REDIS_URL) {
    Write-Host "    Could not auto-fetch REDIS_URL. Open Railway dashboard, copy it, and set it manually." -ForegroundColor Yellow
    $REDIS_URL = Read-Host "    Paste REDIS_URL here"
}
Ok "REDIS_URL: $($REDIS_URL.Substring(0,[Math]::Min(30,$REDIS_URL.Length)))..."

# ── Build shared vars (same for API, Worker, Beat) ────────────────────────

$sharedVars = @{
    GOOGLE_API_KEY         = $env["GOOGLE_API_KEY"]
    SUPABASE_URL           = $env["SUPABASE_URL"]
    SUPABASE_KEY           = $env["SUPABASE_KEY"]
    TAVILY_API_KEY         = $env["TAVILY_API_KEY"]
    BRAVE_API_KEY          = $env["BRAVE_API_KEY"]
    EXA_API_KEY            = $env["EXA_API_KEY"]
    CLERK_PUBLISHABLE_KEY  = $env["CLERK_PUBLISHABLE_KEY"]
    CLERK_SECRET_KEY       = $env["CLERK_SECRET_KEY"]
    CLERK_JWKS_URL         = $env["CLERK_JWKS_URL"]
    CLERK_ISSUER           = $env["CLERK_ISSUER"]
    CLERK_AUDIENCE         = $env["CLERK_AUDIENCE"]
    PADDLE_API_KEY         = $env["PADDLE_API_KEY"]
    PADDLE_WEBHOOK_SECRET  = $env["PADDLE_WEBHOOK_SECRET"]
    PADDLE_PRICE_PRO       = $env["PADDLE_PRICE_PRO"]
    PADDLE_PRICE_POWER     = $env["PADDLE_PRICE_POWER"]
    RESEND_API_KEY         = $env["RESEND_API_KEY"]
    DIGEST_FROM_EMAIL      = $env["DIGEST_FROM_EMAIL"]
    VAPID_SUBJECT          = $env["VAPID_SUBJECT"]
    VAPID_PRIVATE_KEY      = $env["VAPID_PRIVATE_KEY"]
    VAPID_PUBLIC_KEY       = $env["VAPID_PUBLIC_KEY"]
    REDIS_URL              = $REDIS_URL
    ENV                    = "production"
    LOG_LEVEL              = "INFO"
    FRONTEND_URL           = ""   # filled after frontend deploys
}

# ── API service ────────────────────────────────────────────────────────────

Log "Creating API service"
railway service create --name api 2>$null
railway variables set `
    "RAILWAY_SERVICE_START_COMMAND=uvicorn truebrief.api.server:app --host 0.0.0.0 --port `$PORT" `
    --service api 2>$null

Set-ServiceVars "api" $sharedVars
Ok "API vars set"

# ── Worker service ─────────────────────────────────────────────────────────

Log "Creating Worker service"
railway service create --name worker 2>$null
Set-ServiceVars "worker" $sharedVars
Ok "Worker vars set"

# ── Beat service ───────────────────────────────────────────────────────────

Log "Creating Beat service"
railway service create --name beat 2>$null
Set-ServiceVars "beat" $sharedVars
Ok "Beat vars set"

# ── Frontend service ───────────────────────────────────────────────────────

Log "Creating Frontend service"
railway service create --name frontend 2>$null
$frontendVars = @{
    NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY = $env["CLERK_PUBLISHABLE_KEY"]
    CLERK_SECRET_KEY                  = $env["CLERK_SECRET_KEY"]
    NEXT_PUBLIC_API_BASE_URL          = ""   # filled after API deploys
}
Set-ServiceVars "frontend" $frontendVars
Ok "Frontend vars set"

# ── Deploy all services ────────────────────────────────────────────────────

Log "Deploying all services from branch: main"

foreach ($svc in @("api", "worker", "beat", "frontend")) {
    Log "Deploying $svc..."
    railway up --service $svc --detach
    Ok "$svc deploy triggered"
}

# ── Done ───────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host " All services deploying. Two manual steps remain:" -ForegroundColor Green
Write-Host ""
Write-Host " 1. Once API is green, copy its Railway URL and run:" -ForegroundColor Yellow
Write-Host "    railway variables set NEXT_PUBLIC_API_BASE_URL=https://your-api-url --service frontend" -ForegroundColor White
Write-Host "    railway up --service frontend --detach" -ForegroundColor White
Write-Host ""
Write-Host " 2. Once Frontend is green, copy its Railway URL and run:" -ForegroundColor Yellow
Write-Host "    railway variables set FRONTEND_URL=https://your-frontend-url --service api" -ForegroundColor White
Write-Host "    railway variables set FRONTEND_URL=https://your-frontend-url --service worker" -ForegroundColor White
Write-Host "    railway variables set FRONTEND_URL=https://your-frontend-url --service beat" -ForegroundColor White
Write-Host ""
Write-Host " 3. Add your frontend URL to Clerk allowed origins:" -ForegroundColor Yellow
Write-Host "    dashboard.clerk.com -> your app -> Settings -> Domains" -ForegroundColor White
Write-Host "========================================================" -ForegroundColor Green
