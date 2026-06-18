#!/usr/bin/env python
"""
C.5 — Pre-Production Smoke / Preflight Gate.

A single command that fails LOUDLY if the deployment is not safe to flip live.
Run it before a soft/public launch (and ideally in CI before deploy):

    python scripts/preflight.py                      # config + DB checks only
    python scripts/preflight.py --base-url https://api-xxxx.up.railway.app
    PREFLIGHT_BASE_URL=https://... python scripts/preflight.py

What it checks (hard = blocks launch, soft = warning only):
  [hard] Required secrets present     — GOOGLE_API_KEY, SUPABASE_URL/KEY, CLERK_SECRET_KEY, REDIS_URL
  [hard] LLM model config sane        — every pipeline step has a model, none left on a *-preview build
  [hard] Supabase reachable           — can read a core table
  [hard] Migration 012 applied        — pipeline_trace table + prompt/response cols on llm_call_log
                                         (the exact thing that silently breaks the trace panel)
  [soft] Billing/email configured     — Paddle + Resend keys (fine to skip for a free-tier soft launch)
  [hard] Backend /health 200          — only when a base URL is given
  [hard] Public API responds          — GET /api/v1/billing/tiers, only when a base URL is given

Exit code 0 = safe to launch; 1 = at least one hard check failed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Make `config.*` (project root) and `truebrief.*` (src) importable when run directly.
_ROOT = Path(__file__).resolve().parent.parent
for p in (_ROOT, _ROOT / "src"):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

# ── tiny result framework ─────────────────────────────────────────────────────
PASS, FAIL, WARN, SKIP = "PASS", "FAIL", "WARN", "SKIP"
_ICON = {PASS: "+", FAIL: "x", WARN: "!", SKIP: "-"}  # ASCII only (Windows consoles)
_results: list[tuple[str, str, str]] = []


def record(name: str, status: str, detail: str = "") -> None:
    _results.append((name, status, detail))
    print(f"  {_ICON[status]} [{status:4}] {name}" + (f" -- {detail}" if detail else ""))


def _load_dotenv() -> None:
    """Load the project .env into os.environ (real env wins, as on Railway)."""
    try:
        from dotenv import load_dotenv
        load_dotenv(_ROOT / ".env", override=False)
    except Exception:  # noqa: BLE001 — dotenv is best-effort; real env may already be set
        pass


# ── checks ────────────────────────────────────────────────────────────────────
def check_secrets() -> None:
    # Read from the actual environment (after loading .env). Matches how the app +
    # Celery worker read them, and works on Railway where they're real env vars.
    _load_dotenv()

    required = ["GOOGLE_API_KEY", "SUPABASE_URL", "SUPABASE_KEY", "CLERK_SECRET_KEY", "REDIS_URL"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        record("Required secrets present", FAIL, f"missing: {', '.join(missing)}")
    else:
        record("Required secrets present", PASS, f"{len(required)} set")

    # Soft: billing + email only matter for the paid/public launch.
    soft = ["PADDLE_API_KEY", "RESEND_API_KEY"]
    unset = [k for k in soft if not os.getenv(k)]
    if unset:
        record("Billing/email configured", WARN, f"unset (OK for free soft launch): {', '.join(unset)}")
    else:
        record("Billing/email configured", PASS)


def check_model_config() -> None:
    from config.settings import LLM_CONFIG

    if not LLM_CONFIG:
        record("LLM model config sane", FAIL, "LLM_CONFIG is empty")
        return
    bad = []
    for step, cfg in LLM_CONFIG.items():
        model = (cfg or {}).get("model", "")
        if not model:
            bad.append(f"{step}: no model")
        elif "preview" in model.lower():
            # The -preview builds were the daily-quota=0 trap; never launch on them.
            bad.append(f"{step}: preview model '{model}'")
    if bad:
        record("LLM model config sane", FAIL, "; ".join(bad))
    else:
        models = {c["model"] for c in LLM_CONFIG.values()}
        record("LLM model config sane", PASS, f"{len(LLM_CONFIG)} steps -> {', '.join(sorted(models))}")


def check_supabase_and_migration() -> None:
    try:
        from truebrief.ledger.database import get_supabase
        db = get_supabase()
    except Exception as exc:  # noqa: BLE001
        record("Supabase reachable", FAIL, f"client init failed: {exc}")
        record("Migration 012 applied", SKIP, "Supabase unreachable")
        return

    # Reachability: read one row from a core table.
    try:
        db.table("topics").select("id").limit(1).execute()
        record("Supabase reachable", PASS)
    except Exception as exc:  # noqa: BLE001
        record("Supabase reachable", FAIL, str(exc)[:160])
        record("Migration 012 applied", SKIP, "Supabase unreachable")
        return

    # Migration 012: pipeline_trace table + payload columns on llm_call_log.
    problems = []
    try:
        db.table("pipeline_trace").select("id").limit(1).execute()
    except Exception as exc:  # noqa: BLE001
        problems.append(f"pipeline_trace missing ({str(exc)[:80]})")
    try:
        db.table("llm_call_log").select("prompt, response, system_prompt").limit(1).execute()
    except Exception as exc:  # noqa: BLE001
        problems.append(f"llm_call_log payload cols missing ({str(exc)[:80]})")

    if problems:
        record("Migration 012 applied", FAIL, "; ".join(problems))
    else:
        record("Migration 012 applied", PASS, "pipeline_trace + llm_call_log payload cols present")


def _http_get(url: str, timeout: float = 10.0):
    req = urllib.request.Request(url, headers={"User-Agent": "truebrief-preflight"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (trusted URL)
        return resp.status, resp.read().decode("utf-8", "replace")


def check_backend(base_url: str | None) -> None:
    if not base_url:
        record("Backend /health 200", SKIP, "no --base-url given")
        record("Public API responds", SKIP, "no --base-url given")
        return

    base = base_url.rstrip("/")
    # /health
    try:
        status, body = _http_get(f"{base}/health")
        ok = status == 200 and json.loads(body).get("status") == "ok"
        record("Backend /health 200", PASS if ok else FAIL, f"HTTP {status} {body[:80]}")
    except urllib.error.URLError as exc:
        record("Backend /health 200", FAIL, f"unreachable: {exc}")
    except Exception as exc:  # noqa: BLE001
        record("Backend /health 200", FAIL, str(exc)[:120])

    # Public, unauthenticated endpoint.
    try:
        status, body = _http_get(f"{base}/api/v1/billing/tiers")
        record("Public API responds", PASS if status == 200 else FAIL, f"GET /billing/tiers -> HTTP {status}")
    except Exception as exc:  # noqa: BLE001
        record("Public API responds", FAIL, str(exc)[:120])


# ── main ──────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description="TrueBrief pre-production preflight gate.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("PREFLIGHT_BASE_URL"),
        help="Deployed backend base URL (e.g. https://api-xxxx.up.railway.app). "
             "If omitted, HTTP checks are skipped.",
    )
    args = parser.parse_args()

    # Be robust on non-UTF-8 consoles (e.g. Windows cp1255).
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001
        pass

    print("\nTrueBrief preflight\n" + "=" * 60)
    print("- Config & secrets")
    check_secrets()
    check_model_config()
    print("- Database")
    check_supabase_and_migration()
    print("- Live backend" + (f" ({args.base_url})" if args.base_url else ""))
    check_backend(args.base_url)

    fails = [r for r in _results if r[1] == FAIL]
    warns = [r for r in _results if r[1] == WARN]
    print("=" * 60)
    summary = (
        f"{sum(1 for r in _results if r[1] == PASS)} passed, "
        f"{len(fails)} failed, {len(warns)} warnings, "
        f"{sum(1 for r in _results if r[1] == SKIP)} skipped"
    )
    if fails:
        print(f"PREFLIGHT FAILED — {summary}")
        print("Do NOT launch until the ✗ checks above are green.")
        return 1
    print(f"PREFLIGHT OK — {summary}")
    if warns:
        print("(Warnings are fine for a free-tier soft launch; resolve before the paid launch.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
