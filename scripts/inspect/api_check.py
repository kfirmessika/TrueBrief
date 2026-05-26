"""
TrueBrief API Inspector
-----------------------
Hits every known API endpoint against the live Railway deployment.
Generates a Clerk JWT automatically via the Backend API — no manual login.

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
FRONTEND_URL = "https://frontend-production-c9fa.up.railway.app"
CLERK_SECRET_KEY = os.environ["CLERK_SECRET_KEY"]
CLERK_API = "https://api.clerk.com/v1"
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


def get_founder_user() -> dict:
    """Get the founder's Clerk user (only user in dev instance)."""
    headers = {"Authorization": f"Bearer {CLERK_SECRET_KEY}"}
    r = httpx.get(f"{CLERK_API}/users?limit=1", headers=headers, timeout=10)
    r.raise_for_status()
    users = r.json()
    if not users:
        raise RuntimeError("No users found in Clerk — have you signed up at least once?")
    u = users[0]
    email = u["email_addresses"][0]["email_address"] if u.get("email_addresses") else "unknown"
    return {"user_id": u["id"], "email": email}


def get_jwt(user_id: str) -> str:
    """Get a fresh JWT from the user's active Clerk session."""
    headers = {"Authorization": f"Bearer {CLERK_SECRET_KEY}"}
    r = httpx.get(
        f"{CLERK_API}/sessions?user_id={user_id}&status=active&limit=1",
        headers=headers, timeout=10,
    )
    r.raise_for_status()
    sessions = r.json()
    if not sessions:
        raise RuntimeError(
            "No active Clerk session found. Open the app in your browser and sign in once first."
        )
    session_id = sessions[0]["id"]
    jwt_r = httpx.post(f"{CLERK_API}/sessions/{session_id}/tokens", headers=headers, json={"expires_in_seconds": 300}, timeout=10)
    jwt_r.raise_for_status()
    return jwt_r.json()["jwt"]


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
    print("Authenticating via Clerk Backend API...")
    try:
        user = get_founder_user()
        token = get_jwt(user["user_id"])
        print(f"  {ANSI_GREEN}{OK}{ANSI_RESET} JWT acquired for {user['email']}\n")
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

        # Bad input checks (should return 422, not 500)
        results.append(check_endpoint(client, "GET", "/api/v1/topics/undefined"))
        results.append(check_endpoint(client, "GET", "/api/v1/briefs/undefined"))

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
        c = status_color(r["status"])
        status_str = str(r["status"]) if r["status"] else "ERR"
        marker = OK if r["status"] and r["status"] < 400 else FAIL
        print(f"{r['method']:<8} {r['path']:<45} {c}{status_str:<8}{ANSI_RESET} {r['ms']:<8} {c}{marker}{ANSI_RESET}")

        if r["status"] >= 400 or r.get("error"):
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

    ok = sum(1 for r in results if r["status"] and r["status"] < 400)
    total = len(results)
    print(f"\n{ok}/{total} endpoints healthy\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    run(verbose=args.verbose)
