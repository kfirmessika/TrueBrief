"""
TrueBrief — Full Page Screenshot Capture
-----------------------------------------
Captures all public pages automatically (no auth needed).
For authenticated pages, prints the direct URLs to open in your browser.

Usage:
    python scripts/inspect/screenshot_all.py

Output: scripts/inspect/screenshots/pages/
"""

import asyncio, sys, os
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

FRONTEND_URL = "https://frontend-production-c9fa.up.railway.app"
API_URL      = "https://api-production-0bd2.up.railway.app"
OUT_DIR      = Path(__file__).parent / "screenshots" / "pages"

ANSI_GREEN  = "\033[92m"
ANSI_YELLOW = "\033[93m"
ANSI_RESET  = "\033[0m"
ANSI_BOLD   = "\033[1m"
ANSI_DIM    = "\033[2m"
ANSI_CYAN   = "\033[96m"


async def main():
    from playwright.async_api import async_playwright
    import sys as _sys, httpx as _httpx
    _sys.path.insert(0, str(Path(__file__).parent))

    # ── Fetch real IDs via API ────────────────────────────────────────────────
    topic_id = brief_id = None
    try:
        from api_check import get_founder_user, get_jwt
        u   = get_founder_user()
        jwt = get_jwt(u["user_id"])
        hdr = {"Authorization": f"Bearer {jwt}"}
        topics = _httpx.get(f"{API_URL}/api/v1/topics", headers=hdr, timeout=10).json()
        for topic in (topics if isinstance(topics, list) else []):
            b = _httpx.get(f"{API_URL}/api/v1/topics/{topic['id']}/briefs", headers=hdr, timeout=10).json()
            if isinstance(b, list) and b:
                topic_id = topic["id"]
                brief_id = b[0]["id"]
                break
        if not topic_id and isinstance(topics, list) and topics:
            topic_id = topics[0]["id"]
    except Exception as e:
        print(f"  [WARN] Could not fetch IDs: {e}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ── Page list ─────────────────────────────────────────────────────────────
    public_pages = [
        ("01_landing",  f"{FRONTEND_URL}/"),
        ("02_sign_in",  f"{FRONTEND_URL}/sign-in"),
        ("03_sign_up",  f"{FRONTEND_URL}/sign-up"),
        ("04_share",    f"{FRONTEND_URL}/share/{brief_id}" if brief_id else None),
    ]

    auth_pages = [
        ("05_dashboard",    f"{FRONTEND_URL}/dashboard"),
        ("06_onboarding",   f"{FRONTEND_URL}/onboarding"),
        ("07_history",      f"{FRONTEND_URL}/history"),
        ("08_settings",     f"{FRONTEND_URL}/settings"),
        ("09_topic_detail", f"{FRONTEND_URL}/topics/{topic_id}"                        if topic_id else None),
        ("10_topic_briefs", f"{FRONTEND_URL}/topics/{topic_id}/briefs"                 if topic_id else None),
        ("11_brief_detail", f"{FRONTEND_URL}/topics/{topic_id}/briefs/{brief_id}"      if (topic_id and brief_id) else None),
    ]

    print(f"\n{ANSI_BOLD}TrueBrief — Screenshot Capture{ANSI_RESET}")
    print(f"{ANSI_DIM}Output: {OUT_DIR}{ANSI_RESET}\n")

    # ── Take public screenshots ───────────────────────────────────────────────
    print(f"{ANSI_BOLD}Public Pages (automatic){ANSI_RESET}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            # Disable webdriver flag so Clerk doesn't block it
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await context.new_page()

        for name, url in public_pages:
            if url is None:
                print(f"  {ANSI_YELLOW}[SKIP]{ANSI_RESET} {name} — no brief available")
                continue
            label = url.replace(FRONTEND_URL, "") or "/"
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(800)
                path = OUT_DIR / f"{stamp}_{name}.png"
                await page.screenshot(path=str(path), full_page=True)
                print(f"  {ANSI_GREEN}[OK]{ANSI_RESET} {label}")
                print(f"      {ANSI_DIM}{path}{ANSI_RESET}")
            except Exception as e:
                print(f"  {ANSI_YELLOW}[ERR]{ANSI_RESET} {label}: {e}")

        await browser.close()

    # ── Auth pages: print links ───────────────────────────────────────────────
    print(f"\n{ANSI_BOLD}Authenticated Pages — open these in your browser{ANSI_RESET}")
    print(f"{ANSI_DIM}(Sign in first, then open each URL and take a screenshot with Win+Shift+S){ANSI_RESET}\n")
    for name, url in auth_pages:
        if url is None:
            print(f"  {ANSI_YELLOW}[N/A]{ANSI_RESET} {name} — no topic/brief data")
            continue
        label = url.replace(FRONTEND_URL, "")
        print(f"  {ANSI_CYAN}{label}{ANSI_RESET}")
        print(f"  {ANSI_DIM}{url}{ANSI_RESET}\n")

    print(f"\n{ANSI_DIM}Public screenshots saved to: {OUT_DIR}{ANSI_RESET}")


if __name__ == "__main__":
    asyncio.run(main())
