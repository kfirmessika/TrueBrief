"""
TrueBrief Browser Inspector
----------------------------
Uses Playwright to walk the live frontend and verify page rendering,
console errors, and network failures for unauthenticated flows.

Note on Clerk dev-instance auth:
  Dashboard / topic-detail pages require a Clerk "dev browser" session that
  involves a redirect through accounts.dev. This cannot be automated in headless
  Playwright. Use `python scripts/inspect/api_check.py` for authenticated
  endpoint verification.

Usage:
    python scripts/inspect/browser_check.py
    python scripts/inspect/browser_check.py --headed    # show the browser window
    python scripts/inspect/browser_check.py --no-screenshots

Requires:
    pip install playwright
    playwright install chromium
"""

import os
import sys
# Force UTF-8 on Windows consoles that default to a narrow codepage
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)
import asyncio
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

FRONTEND_URL = "https://frontend-production-c9fa.up.railway.app"
API_URL = "https://api-production-0bd2.up.railway.app"
CLERK_SECRET_KEY = os.environ.get("CLERK_SECRET_KEY", "")
SCREENSHOTS_DIR = Path(__file__).parent / "screenshots"

ANSI_GREEN = "\033[92m"
ANSI_RED = "\033[91m"
ANSI_YELLOW = "\033[93m"
ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
ANSI_DIM = "\033[2m"

# Noise URLs to suppress from the network failures report
_NOISE_URLS = ("accounts.dev", "sentry.io", "clerk.accounts.dev", "_rsc=")


async def run_browser(headed: bool = False, screenshots: bool = True):
    from playwright.async_api import async_playwright, Page

    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    issues = []
    passed = []
    skipped = []

    def ts() -> str:
        return datetime.now().strftime("%H%M%S")

    async def screenshot(page: Page, name: str):
        if screenshots:
            path = SCREENSHOTS_DIR / f"{ts()}_{name}.png"
            await page.screenshot(path=str(path), full_page=True)
            return path
        return None

    async def check(label: str, fn):
        try:
            result = await fn()
            passed.append(label)
            print(f"  {ANSI_GREEN}[OK]{ANSI_RESET} {label}")
            return result
        except Exception as e:
            issues.append({"check": label, "error": str(e)})
            print(f"  {ANSI_RED}[FAIL]{ANSI_RESET} {label}: {ANSI_RED}{e}{ANSI_RESET}")
            return None

    def skip(label: str, reason: str):
        skipped.append(label)
        print(f"  {ANSI_YELLOW}[SKIP]{ANSI_RESET} {label}: {ANSI_DIM}{reason}{ANSI_RESET}")

    print(f"\n{ANSI_BOLD}TrueBrief Browser Inspector{ANSI_RESET}")
    print(f"{ANSI_DIM}Target: {FRONTEND_URL}{ANSI_RESET}")
    print(f"{ANSI_DIM}Time:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{ANSI_RESET}\n")

    # ── Get a brief ID for the share page check ──
    _brief_id = None
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent))
        import httpx as _httpx
        from api_check import get_founder_user, get_jwt
        _u = get_founder_user()
        _jwt = get_jwt(_u["user_id"])
        _h = {"Authorization": f"Bearer {_jwt}"}
        _topics = _httpx.get(f"{API_URL}/api/v1/topics", headers=_h, timeout=10)
        _topic_list = _topics.json() if _topics.status_code == 200 else []
        if _topic_list:
            _tid = _topic_list[0]["id"]
            _briefs = _httpx.get(f"{API_URL}/api/v1/topics/{_tid}/briefs", headers=_h, timeout=10)
            _brief_list = _briefs.json() if _briefs.status_code == 200 else []
            if _brief_list:
                _brief_id = _brief_list[0]["id"]
        print(f"{ANSI_DIM}Share brief ID: {_brief_id or 'none available'}{ANSI_RESET}\n")
    except Exception as _e:
        print(f"{ANSI_DIM}Could not fetch brief ID for share check: {_e}{ANSI_RESET}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not headed)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            record_video_dir=str(SCREENSHOTS_DIR) if screenshots else None,
        )

        console_errors = []
        network_errors = []

        page = await context.new_page()

        page.on("console", lambda msg: console_errors.append({
            "type": msg.type,
            "text": msg.text,
            "url": page.url,
        }) if msg.type in ("error", "warning") else None)

        page.on("requestfailed", lambda req: network_errors.append({
            "url": req.url,
            "failure": req.failure,
            "page": page.url,
        }) if not any(n in req.url for n in _NOISE_URLS) else None)

        # ── CHECK 1: Landing page ──
        print("── Public Pages ──")

        async def check_landing():
            await page.goto(FRONTEND_URL, wait_until="networkidle", timeout=30000)
            await page.wait_for_selector("body", timeout=5000)
            title = await page.title()
            content = await page.content()
            assert title, "Page has no title"
            assert len(content) > 500, "Landing page looks empty"
            return title

        title = await check("Landing page loads", check_landing)
        await screenshot(page, "01_landing")

        # ── CHECK 2: Sign-in page ──
        async def check_signin():
            await page.goto(f"{FRONTEND_URL}/sign-in", wait_until="networkidle", timeout=30000)
            content = await page.content()
            assert len(content) > 200, "Sign-in page is empty"
            # Should have Clerk sign-in UI elements
            has_clerk = await page.query_selector("[data-clerk-component], .cl-rootBox, input[name='identifier'], input[type='email']")
            # Even if Clerk widget isn't visible, the page should not be blank
            return "has_clerk_ui" if has_clerk else "page_loaded"

        await check("Sign-in page renders", check_signin)
        await screenshot(page, "02_signin")

        # ── CHECK 3: Sign-up page ──
        async def check_signup():
            await page.goto(f"{FRONTEND_URL}/sign-up", wait_until="networkidle", timeout=30000)
            content = await page.content()
            assert len(content) > 200, "Sign-up page is empty"
            return "loaded"

        await check("Sign-up page renders", check_signup)
        await screenshot(page, "03_signup")

        # ── CHECK 4: Share page ──
        print("\n── Share Page (unauthenticated) ──")
        if _brief_id:
            async def check_share():
                await page.goto(f"{FRONTEND_URL}/share/{_brief_id}", wait_until="networkidle", timeout=30000)
                content = await page.content()
                assert len(content) > 500, "Share page is empty"
                # Should NOT redirect to sign-in (share is public)
                assert "sign-in" not in page.url, f"Share page required auth: {page.url}"
                # Should have brief content
                has_article = await page.query_selector("article, .brief-content, h1")
                assert has_article, "Share page has no article/h1 element"
                return page.url

            await check(f"Share page renders (/share/{_brief_id[:8]}...)", check_share)
            await screenshot(page, "04_share")
        else:
            skip("Share page renders", "no briefs available — create a topic and run a scan first")

        # ── Authenticated pages: note the limitation ──
        print("\n── Authenticated Pages ──")
        print(f"  {ANSI_YELLOW}[NOTE]{ANSI_RESET} {ANSI_DIM}Dashboard / topic-detail require Clerk dev-browser auth{ANSI_RESET}")
        print(f"  {ANSI_DIM}       which cannot be automated in headless Playwright.{ANSI_RESET}")
        print(f"  {ANSI_DIM}       Run `python scripts/inspect/api_check.py` for API verification.{ANSI_RESET}")

        skip("Dashboard UI", "Clerk dev-instance requires accounts.dev browser flow")
        skip("Topic detail UI", "Clerk dev-instance requires accounts.dev browser flow")

        # Quick sanity: do these URLs at least 302 to sign-in (not 500)?
        async def check_dashboard_redirect():
            r = await page.request.get(f"{FRONTEND_URL}/dashboard", max_redirects=0)
            # 200 (already logged in cached), 307 (redirect to sign-in), 302 — all valid
            assert r.status < 500, f"Dashboard returned {r.status} (server error)"

        await check("Dashboard returns non-500 response", check_dashboard_redirect)

        await context.close()
        await browser.close()

    # ── REPORT ──
    print(f"\n{'─'*60}")
    print(f"{ANSI_BOLD}Results: {len(passed)} passed, {len(issues)} failed, {len(skipped)} skipped{ANSI_RESET}")

    if console_errors:
        js_errors = [e for e in console_errors if e["type"] == "error"
                     and not any(n in e.get("text", "") for n in ("accounts.dev", "clerk_db_jwt", "Sentry"))]
        if js_errors:
            print(f"\n{ANSI_RED}{ANSI_BOLD}Console Errors ({len(js_errors)}){ANSI_RESET}")
            seen = set()
            for e in js_errors:
                key = e["text"][:100]
                if key not in seen:
                    seen.add(key)
                    url_label = e["url"].split("/")[-1][:40] if e["url"] else ""
                    print(f"  {ANSI_RED}*{ANSI_RESET} [{url_label}] {e['text'][:200]}")

    if network_errors:
        print(f"\n{ANSI_RED}{ANSI_BOLD}Network Failures ({len(network_errors)}){ANSI_RESET}")
        for e in network_errors:
            print(f"  {ANSI_RED}*{ANSI_RESET} {e['url'][:80]} -- {e['failure']}")

    if issues:
        print(f"\n{ANSI_RED}{ANSI_BOLD}Failed Checks{ANSI_RESET}")
        for issue in issues:
            print(f"  {ANSI_RED}[FAIL]{ANSI_RESET} {issue['check']}")
            print(f"    {ANSI_DIM}{issue['error'][:300]}{ANSI_RESET}")

    if not issues:
        print(f"\n{ANSI_GREEN}{ANSI_BOLD}All checks passed{ANSI_RESET}")

    if screenshots:
        print(f"\n{ANSI_DIM}Screenshots saved to: {SCREENSHOTS_DIR}{ANSI_RESET}")

    return issues


def run(headed: bool = False, screenshots: bool = True):
    issues = asyncio.run(run_browser(headed=headed, screenshots=screenshots))
    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--headed", action="store_true", help="Show browser window")
    parser.add_argument("--no-screenshots", action="store_true")
    args = parser.parse_args()
    run(headed=args.headed, screenshots=not args.no_screenshots)
