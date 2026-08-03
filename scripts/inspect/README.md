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

Both scripts mint a real Supabase access token for the founder's account, headlessly, via the
GoTrue admin API (`api_check.get_founder_access_token()`):

1. `POST {SUPABASE_URL}/auth/v1/admin/generate_link` (type=`magiclink`), authenticated with the
   service-role/secret key (`SUPABASE_KEY`) — looks up the existing user by email and returns a
   `hashed_token`.
2. `POST {SUPABASE_URL}/auth/v1/verify` with that `hashed_token` — returns a real session
   (`access_token`, `refresh_token`, ...), exactly as if the founder had clicked the emailed magic
   link.

Requires in `.env`: `SUPABASE_URL`, `SUPABASE_KEY` (service-role/secret — the anon key cannot call
admin endpoints), and `FOUNDER_EMAIL` (must already be a signed-up user; `generate_link` doesn't
create one for `magiclink`). Each run mints a fresh token — nothing is cached.

Dashboard / topic-detail pages can't be reached by `browser_check.py`: TrueBrief's only sign-in
paths are Google OAuth (interactive consent) and an emailed magic link, neither of which a headless
browser can complete on its own. `api_check.py` sidesteps this entirely by minting a session
directly via the GoTrue admin API above.
