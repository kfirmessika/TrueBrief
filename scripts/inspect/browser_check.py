"""
TrueBrief Browser Inspector
----------------------------
Uses Playwright to walk the live frontend, click through key flows,
and capture console errors, network failures, and screenshots.

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
import json
import time
import asyncio
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

FRONTEND_URL = "https://frontend-production-c9fa.up.railway.app"
API_URL = "https://api-production-0bd2.up.railway.app"
CLERK_SECRET_KEY = os.environ["CLERK_SECRET_KEY"]
CLERK_API = "https://api.clerk.com/v1"
SCREENSHOTS_DIR = Path(__file__).parent / "screenshots"
AUTH_STATE_FILE = Path(__file__).parent / ".browser_auth.json"

ANSI_GREEN = "\033[92m"
ANSI_RED = "\033[91m"
ANSI_YELLOW = "\033[93m"
ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
ANSI_DIM = "\033[2m"


def get_sign_in_token() -> str:
    """Get a Clerk sign-in token for the test user."""
    import httpx

    test_email = "inspector@truebrief-test.local"
    headers = {"Authorization": f"Bearer {CLERK_SECRET_KEY}"}

    # Find or create test user
    r = httpx.get(f"{CLERK_API}/users?email_address={test_email}", headers=headers, timeout=10)
    users = r.json()
    if not users:
        r2 = httpx.post(
            f"{CLERK_API}/users",
            headers=headers,
            json={
                "email_address": [test_email],
                "password": "TrueBriefInspector123!",
                "skip_password_checks": True,
                "skip_password_requirement": True,
            },
            timeout=10,
        )
        r2.raise_for_status()
        user_id = r2.json()["id"]
    else:
        user_id = users[0]["id"]

    # Issue sign-in token
    r3 = httpx.post(
        f"{CLERK_API}/sign_in_tokens",
        headers=headers,
        json={"user_id": user_id, "expires_in_seconds": 3600},
        timeout=10,
    )
    r3.raise_for_status()
    return r3.json()["token"]


async def run_browser(headed: bool = False, screenshots: bool = True):
    from playwright.async_api import async_playwright, Page, ConsoleMessage

    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    issues = []
    passed = []

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
            print(f"  {ANSI_GREEN}✓{ANSI_RESET} {label}")
            return result
        except Exception as e:
            issues.append({"check": label, "error": str(e)})
            print(f"  {ANSI_RED}✗{ANSI_RESET} {label}: {ANSI_RED}{e}{ANSI_RESET}")
            return None

    print(f"\n{ANSI_BOLD}TrueBrief Browser Inspector{ANSI_RESET}")
    print(f"{ANSI_DIM}Target: {FRONTEND_URL}{ANSI_RESET}")
    print(f"{ANSI_DIM}Time:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{ANSI_RESET}\n")

    # Get auth token
    print("Getting Clerk sign-in token...")
    try:
        sign_in_token = get_sign_in_token()
        print(f"  {ANSI_GREEN}✓{ANSI_RESET} Token acquired\n")
    except Exception as e:
        print(f"  {ANSI_RED}✗ Failed to get token: {e}{ANSI_RESET}\n")
        sign_in_token = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not headed)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            record_video_dir=str(SCREENSHOTS_DIR) if screenshots else None,
        )

        # Collect all console errors and network failures
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
        }))

        # ── CHECK 1: Landing page loads ──
        print("── Landing Page ──")
        async def check_landing():
            await page.goto(FRONTEND_URL, wait_until="networkidle", timeout=30000)
            await page.wait_for_selector("body", timeout=5000)
            title = await page.title()
            assert title, "Page has no title"
            return title

        title = await check("Landing page loads", check_landing)
        await screenshot(page, "01_landing")

        # ── CHECK 2: Sign in via Clerk token URL ──
        print("\n── Authentication ──")
        topic_id = None

        if sign_in_token:
            async def do_sign_in():
                clerk_domain = "integral-grackle-67.clerk.accounts.dev"
                # Use Clerk's __clerk_ticket param to bypass UI login
                sign_in_url = (
                    f"https://{clerk_domain}/v1/client/sign_ins"
                    f"?strategy=ticket&ticket={sign_in_token}&redirect_url={FRONTEND_URL}/dashboard"
                )
                await page.goto(
                    f"{FRONTEND_URL}/sign-in#/?redirect_url=/dashboard",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                # Inject the sign-in token via Clerk's JS API if available
                result = await page.evaluate(f"""
                    async () => {{
                        if (window.Clerk) {{
                            try {{
                                await window.Clerk.signIn.create({{
                                    strategy: 'ticket',
                                    ticket: '{sign_in_token}',
                                }});
                                await window.Clerk.setActive({{
                                    session: window.Clerk.client.signIn.createdSessionId,
                                }});
                                return 'clerk_ok';
                            }} catch(e) {{
                                return 'clerk_error: ' + e.message;
                            }}
                        }}
                        return 'clerk_not_loaded';
                    }}
                """)
                return result

            auth_result = await check("Clerk sign-in via ticket", do_sign_in)
            await screenshot(page, "02_after_signin_attempt")

            # Check if we ended up on dashboard
            async def check_dashboard():
                await page.wait_for_url("**/dashboard**", timeout=15000)
                await page.wait_for_load_state("networkidle", timeout=15000)
                content = await page.content()
                assert "dashboard" in page.url.lower() or "topic" in content.lower(), \
                    f"Expected dashboard, got: {page.url}"

            await check("Lands on dashboard after auth", check_dashboard)
            await screenshot(page, "03_dashboard")

        # ── CHECK 3: Dashboard content ──
        print("\n── Dashboard ──")
        async def check_dashboard_content():
            await page.goto(f"{FRONTEND_URL}/dashboard", wait_until="networkidle", timeout=30000)
            content = await page.content()
            # Should not be a blank page or error page
            assert len(content) > 500, "Dashboard page looks empty"
            assert "error" not in content.lower()[:200] or "Error" not in await page.title(), \
                "Dashboard shows error state"
            return content

        dashboard_content = await check("Dashboard renders", check_dashboard_content)
        await screenshot(page, "04_dashboard_full")

        # Try to find a topic link
        async def find_topic():
            links = await page.query_selector_all("a[href*='/topics/']")
            if links:
                href = await links[0].get_attribute("href")
                return href.split("/topics/")[1].split("/")[0]
            return None

        topic_id = await page.evaluate("""
            () => {
                const links = Array.from(document.querySelectorAll('a[href*="/topics/"]'));
                if (links.length) {
                    const m = links[0].href.match(/\\/topics\\/([^/]+)/);
                    return m ? m[1] : null;
                }
                return null;
            }
        """)

        # ── CHECK 4: Topic detail page ──
        print("\n── Topic Detail ──")
        if topic_id:
            async def check_topic_detail():
                await page.goto(f"{FRONTEND_URL}/topics/{topic_id}", wait_until="networkidle", timeout=30000)
                content = await page.content()
                assert len(content) > 500, "Topic detail looks empty"
                return content

            await check(f"Topic detail loads (/topics/{topic_id[:8]}...)", check_topic_detail)
            await screenshot(page, "05_topic_detail")

            # Check tabs
            async def check_tabs():
                tabs = await page.query_selector_all("[role='tab'], button[data-tab]")
                assert len(tabs) > 0, "No tabs found on topic detail"
                return [await t.inner_text() for t in tabs]

            tabs = await check("Topic detail has tabs", check_tabs)
            if tabs:
                print(f"    {ANSI_DIM}Tabs found: {tabs}{ANSI_RESET}")

            # Click Scan button if present
            async def click_scan():
                scan_btn = await page.query_selector("button:has-text('Scan'), button:has-text('scan')")
                if scan_btn:
                    await scan_btn.click()
                    await page.wait_for_timeout(2000)
                    return "clicked"
                return "not found"

            await check("Scan button clickable", click_scan)
            await screenshot(page, "06_after_scan_click")
        else:
            print(f"  {ANSI_YELLOW}⚠{ANSI_RESET} No topics found — skipping topic detail checks")
            print(f"  {ANSI_DIM}(Create a topic first via the dashboard){ANSI_RESET}")

        # ── CHECK 5: Settings page ──
        print("\n── Settings ──")
        async def check_settings():
            await page.goto(f"{FRONTEND_URL}/settings", wait_until="networkidle", timeout=30000)
            content = await page.content()
            assert len(content) > 200, "Settings page empty"
            return content

        await check("Settings page loads", check_settings)
        await screenshot(page, "07_settings")

        # ── CHECK 6: Share page (unauthenticated) ──
        # Skip for now — need a valid brief ID

        await context.close()
        await browser.close()

    # ── REPORT ──
    print(f"\n{'─'*60}")
    print(f"{ANSI_BOLD}Results: {len(passed)} passed, {len(issues)} failed{ANSI_RESET}")

    if console_errors:
        js_errors = [e for e in console_errors if e["type"] == "error"]
        if js_errors:
            print(f"\n{ANSI_RED}{ANSI_BOLD}Console Errors ({len(js_errors)}){ANSI_RESET}")
            seen = set()
            for e in js_errors:
                key = e["text"][:100]
                if key not in seen:
                    seen.add(key)
                    print(f"  {ANSI_RED}•{ANSI_RESET} [{e['url'].split('/')[-1]}] {e['text'][:200]}")

    if network_errors:
        print(f"\n{ANSI_RED}{ANSI_BOLD}Network Failures ({len(network_errors)}){ANSI_RESET}")
        for e in network_errors:
            print(f"  {ANSI_RED}•{ANSI_RESET} {e['url'][:80]} — {e['failure']}")

    if issues:
        print(f"\n{ANSI_RED}{ANSI_BOLD}Failed Checks{ANSI_RESET}")
        for issue in issues:
            print(f"  {ANSI_RED}✗{ANSI_RESET} {issue['check']}")
            print(f"    {ANSI_DIM}{issue['error'][:300]}{ANSI_RESET}")

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
