# TrueBrief Inspector Toolkit

Claude uses these scripts to autonomously inspect the live deployment without needing the user to relay information.

## Scripts

| Script | What it does |
|--------|-------------|
| `api_check.py` | Hits every API endpoint with a real JWT, prints a status table + full error details |
| `browser_check.py` | Playwright walks the live frontend, clicks key flows, captures console errors + screenshots |
| `logs.ps1` | Tails Railway logs for a given service |

## Usage

```powershell
# Check all API endpoints
cd d:\projects\Apps\TrueBrief
python scripts/inspect/api_check.py

# Run browser inspector (takes ~60s, saves screenshots to scripts/inspect/screenshots/)
python scripts/inspect/browser_check.py

# Tail logs for a specific service
.\scripts\inspect\logs.ps1 -Service api
.\scripts\inspect\logs.ps1 -Service worker
.\scripts\inspect\logs.ps1 -Service beat
```

## Auth

Both scripts generate a Clerk JWT using CLERK_SECRET_KEY + a test user, so no manual login is needed.
The token is cached in `scripts/inspect/.auth_cache.json` for 55 minutes.
