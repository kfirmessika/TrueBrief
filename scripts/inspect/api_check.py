"""
TrueBrief API Inspector
-----------------------
Hits every known API endpoint against the live Railway deployment.
Mints a real Supabase access token for the founder's account automatically
via the GoTrue admin API (generate_link + verify) — no manual login, no
browser.

Usage:
    python scripts/inspect/api_check.py
    python scripts/inspect/api_check.py --verbose   # show full response bodies
"""

import os
import sys
import json
import time
import argparse
import httpx
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

API_URL = "https://api-production-0bd2.up.railway.app"
FRONTEND_URL = "https://truebrief.up.railway.app"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")  # service-role/secret key — required for the GoTrue admin API
FOUNDER_EMAIL = os.environ.get("FOUNDER_EMAIL", "")
AUTH_CACHE = Path(__file__).parent / ".auth_cache.json"

ANSI_GREEN = "\033[92m"
ANSI_RED = "\033[91m"
ANSI_YELLOW = "\033[93m"
ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
ANSI_DIM = "\033[2m"
OK = "[OK]"
FAIL = "[FAIL]"
WARN = "[WARN]"


def _require(value: str, var_name: str, purpose: str) -> str:
    if not value:
        raise RuntimeError(f"Missing required env var {var_name} (needed for: {purpose})")
    return value


def get_founder_access_token() -> str:
    """
    Mint a real Supabase access token for the founder's account, headlessly —
    no browser, no manual login. Uses the GoTrue admin API:

      1. POST /auth/v1/admin/generate_link (type=magiclink), authenticated with
         the service-role/secret key -> returns a `hashed_token` for an
         existing user looked up by email (does not create one).
      2. POST /auth/v1/verify with that hashed_token -> returns a real session
         (access_token, refresh_token, ...), exactly as if the founder had
         clicked the emailed magic link.

    Requires the founder to have already signed up once via the app (so the
    email resolves to an existing auth.users row).
    """
    url = _require(SUPABASE_URL, "SUPABASE_URL", "the Supabase project URL to mint a token against")
    key = _require(SUPABASE_KEY, "SUPABASE_KEY", "the Supabase service-role/secret key needed to call the GoTrue admin API")
    email = _require(FOUNDER_EMAIL, "FOUNDER_EMAIL", "the founder's account email to mint a session for")

    admin_headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    link_r = httpx.post(
        f"{url}/auth/v1/admin/generate_link",
        headers=admin_headers,
        json={"type": "magiclink", "email": email},
        timeout=10,
    )
    link_r.raise_for_status()
    link_data = link_r.json()
    hashed_token = link_data.get("hashed_token")
    if not hashed_token:
        raise RuntimeError(f"generate_link response had no hashed_token (keys: {list(link_data.keys())})")

    verify_r = httpx.post(
        f"{url}/auth/v1/verify",
        headers={"apikey": key, "Content-Type": "application/json"},
        json={"type": "magiclink", "token_hash": hashed_token},
        timeout=10,
    )
    verify_r.raise_for_status()
    session = verify_r.json()
    access_token = session.get("access_token")
    if not access_token:
        raise RuntimeError(f"verify response had no access_token (keys: {list(session.keys())})")
    return access_token


def status_color(code: int) -> str:
    if code < 300:
        return ANSI_GREEN
    if code < 500:
        return ANSI_YELLOW
    return ANSI_RED


def check_endpoint(client: httpx.Client, method: str, path: str, **kwargs) -> dict:
    url = f"{API_URL}{path}"
    start = time.time()
    try:
        r = client.request(method, url, timeout=15, **kwargs)
        elapsed = int((time.time() - start) * 1000)
        body = None
        try:
            body = r.json()
        except Exception:
            body = r.text[:500]
        return {"method": method, "path": path, "status": r.status_code, "ms": elapsed, "body": body}
    except Exception as e:
        return {"method": method, "path": path, "status": 0, "ms": 0, "body": str(e), "error": True}


def run(verbose: bool = False):
    print(f"\n{ANSI_BOLD}TrueBrief API Inspector{ANSI_RESET}")
    print(f"{ANSI_DIM}Target: {API_URL}{ANSI_RESET}")
    print(f"{ANSI_DIM}Time:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{ANSI_RESET}\n")

    # Auth
    print("Authenticating via Supabase GoTrue admin API...")
    try:
        token = get_founder_access_token()
        print(f"  {ANSI_GREEN}{OK}{ANSI_RESET} Access token acquired for {FOUNDER_EMAIL}\n")
    except Exception as e:
        print(f"  {ANSI_RED}{FAIL} Auth failed: {e}{ANSI_RESET}")
        print("  Continuing with unauthenticated checks only.\n")
        token = None

    headers = {"Authorization": f"Bearer {token}"} if token else {}
    results = []

    with httpx.Client(headers=headers, follow_redirects=True) as client:
        # --- Unauthenticated ---
        results.append(check_endpoint(client, "GET", "/health"))
        results.append(check_endpoint(client, "GET", "/openapi.json"))

        # --- Auth-required ---
        results.append(check_endpoint(client, "GET", "/api/v1/topics"))
        results.append(check_endpoint(client, "POST", "/api/v1/topics",
            json={"name": "__inspector_test__", "raw_query": "artificial intelligence"}))
        results.append(check_endpoint(client, "GET", "/api/v1/briefs/history"))
        results.append(check_endpoint(client, "GET", "/api/v1/users/me/stats"))
        results.append(check_endpoint(client, "GET", "/api/v1/admin/cost-summary"))

        # Get topic_id: prefer existing topics, fallback to the just-created test topic
        topic_id = None
        test_topic_id = None
        for r in results:
            if r["path"] == "/api/v1/topics" and r["status"] == 200:
                topics = r["body"] if isinstance(r["body"], list) else []
                if topics:
                    topic_id = topics[0].get("id")
                break
        if not topic_id:
            created = next((r for r in results if r["method"] == "POST" and "/topics" in r["path"] and r["status"] in (200, 201)), None)
            if created and isinstance(created.get("body"), dict):
                topic_id = created["body"].get("id")
                test_topic_id = topic_id  # mark for cleanup

        if topic_id:
            results.append(check_endpoint(client, "GET", f"/api/v1/topics/{topic_id}"))
            results.append(check_endpoint(client, "GET", f"/api/v1/topics/{topic_id}/briefs"))
            results.append(check_endpoint(client, "GET", f"/api/v1/topics/{topic_id}/ayr"))
            results.append(check_endpoint(client, "GET", f"/api/v1/topics/{topic_id}/query-variants"))
            results.append(check_endpoint(client, "GET", f"/api/v1/topics/{topic_id}/stories"))
        else:
            print(f"  {ANSI_YELLOW}[WARN] No topics available for per-topic checks{ANSI_RESET}")

        # Bad input checks (should return 422, not 500) — mark as expected_status=422
        r_bad_topic = check_endpoint(client, "GET", "/api/v1/topics/undefined")
        r_bad_topic["expected_status"] = 422
        results.append(r_bad_topic)
        r_bad_brief = check_endpoint(client, "GET", "/api/v1/briefs/undefined")
        r_bad_brief["expected_status"] = 422
        results.append(r_bad_brief)

        # Unauthenticated share (should work without token)
        if topic_id:
            briefs_r = [r for r in results if r["path"].endswith("/briefs")]
            if briefs_r and briefs_r[0]["status"] == 200:
                briefs = briefs_r[0]["body"] if isinstance(briefs_r[0]["body"], list) else []
                if briefs:
                    brief_id = briefs[0].get("id")
                    with httpx.Client(follow_redirects=True) as anon_client:
                        results.append(check_endpoint(anon_client, "GET", f"/api/v1/share/{brief_id}"))

        # Clean up test topic if we created one
        if test_topic_id:
            client.delete(f"{API_URL}/api/v1/topics/{test_topic_id}", timeout=10)

    # --- Print results ---
    print(f"{'METHOD':<8} {'ENDPOINT':<45} {'STATUS':<8} {'MS':<8} RESULT")
    print("-" * 100)

    errors = []
    for r in results:
        expected = r.get("expected_status")
        is_ok = (expected and r["status"] == expected) or (not expected and r["status"] and r["status"] < 400)
        c = ANSI_GREEN if is_ok else (ANSI_YELLOW if r.get("expected_status") else ANSI_RED)
        status_str = str(r["status"]) if r["status"] else "ERR"
        note = f" (expected {expected})" if expected else ""
        marker = OK if is_ok else FAIL
        print(f"{r['method']:<8} {r['path']:<45} {c}{status_str:<8}{ANSI_RESET} {r['ms']:<8} {c}{marker}{note}{ANSI_RESET}")

        is_real_error = not is_ok and (r["status"] == 0 or r["status"] >= 400)
        if is_real_error:
            errors.append(r)
            if verbose:
                print(f"         {ANSI_DIM}{json.dumps(r['body'], indent=2)[:300]}{ANSI_RESET}")

    print()
    if errors:
        print(f"{ANSI_RED}{ANSI_BOLD}ERRORS ({len(errors)}){ANSI_RESET}")
        for r in errors:
            print(f"\n  {ANSI_RED}{r['method']} {r['path']} -> {r['status']}{ANSI_RESET}")
            body = r["body"]
            if isinstance(body, dict):
                detail = body.get("detail", body)
                print(f"  {json.dumps(detail, indent=4)[:500]}")
            else:
                print(f"  {str(body)[:500]}")
    else:
        print(f"{ANSI_GREEN}{ANSI_BOLD}All endpoints OK{ANSI_RESET}")

    ok = sum(1 for r in results if (r.get("expected_status") and r["status"] == r["expected_status"]) or (not r.get("expected_status") and r["status"] and r["status"] < 400))
    total = len(results)
    print(f"\n{ok}/{total} endpoints healthy\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    run(verbose=args.verbose)
