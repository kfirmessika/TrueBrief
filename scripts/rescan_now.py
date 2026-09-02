"""
One-shot admin script: clean stale facts and trigger immediate rescan of all topics.

Usage:
  python scripts/rescan_now.py [--dry-run]

What it does:
  1. Deletes facts whose event_date is older than MAX_FACT_AGE_DAYS (30).
     These are the July-08 earnings facts and 2023 transfer facts stamped as "today".
  2. Also deletes facts from known junk/low-tier source domains.
  3. Sets next_run_at = now - 1 minute on every active topic.
     The Beat scheduler (60s heartbeat) picks them up on its next tick.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

# ── load .env ────────────────────────────────────────────────────────────────
from pathlib import Path
env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from supabase import create_client  # noqa: E402

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

# Facts older than this are removed (genuinely stale content).
MAX_FACT_AGE_DAYS = 30

# Known junk/ultra-low-tier domains found in the bad scan batch.
JUNK_DOMAINS = [
    "stopthehousingbailout.com",
    "ghanaclasic.com",
    "nexnews.org",
]


def main(dry_run: bool) -> None:
    db = create_client(SUPABASE_URL, SUPABASE_KEY)
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=MAX_FACT_AGE_DAYS)).date().isoformat()

    tag = "[DRY-RUN] " if dry_run else ""

    # ── 1. Count / delete stale facts (event_date too old) ──────────────────
    stale_res = db.table("known_facts").select("id", count="exact").lt("event_date", cutoff).execute()
    stale_count = stale_res.count or 0
    print(f"{tag}Stale facts (event_date < {cutoff}): {stale_count}")
    if stale_count and not dry_run:
        db.table("known_facts").delete().lt("event_date", cutoff).execute()
        print(f"  Deleted {stale_count} stale facts.")

    # ── 2. Delete facts from junk domains ───────────────────────────────────
    for domain in JUNK_DOMAINS:
        junk_res = (
            db.table("known_facts")
            .select("id", count="exact")
            .ilike("source_domain", f"%{domain}%")
            .execute()
        )
        junk_count = junk_res.count or 0
        print(f"{tag}Junk domain '{domain}' facts: {junk_count}")
        if junk_count and not dry_run:
            db.table("known_facts").delete().ilike("source_domain", f"%{domain}%").execute()
            print(f"  Deleted {junk_count} junk-domain facts.")

    # ── 3. Delete facts with category/tag/index page URLs ────────────────────
    for seg in ("/category/", "/tag/", "/tags/", "/topic/", "/topics/"):
        cat_res = (
            db.table("known_facts")
            .select("id", count="exact")
            .ilike("source_url", f"%{seg}%")
            .execute()
        )
        cat_count = cat_res.count or 0
        print(f"{tag}Category-URL facts ({seg}): {cat_count}")
        if cat_count and not dry_run:
            db.table("known_facts").delete().ilike("source_url", f"%{seg}%").execute()
            print(f"  Deleted {cat_count} category-URL facts.")

    # ── 3. Set next_run_at = now - 1 min on all active topics ───────────────
    topics_res = db.table("topics").select("id,raw_query,next_run_at").eq("is_active", True).execute()
    topics = topics_res.data or []
    print(f"\n{tag}Active topics: {len(topics)}")
    for t in topics:
        print(f"  {t['id'][:8]}… {t['raw_query'][:50]}  next_run_at={t.get('next_run_at', 'NULL')}")

    if not dry_run:
        due_at = (now - timedelta(minutes=1)).isoformat()
        ids = [t["id"] for t in topics]
        for tid in ids:
            db.table("topics").update({"next_run_at": due_at}).eq("id", tid).execute()
        print(f"\nSet next_run_at={due_at} on {len(ids)} topic(s).")
        print("Beat scheduler will enqueue pipeline tasks within ~60 seconds.")
    else:
        print("\n[DRY-RUN] Would set next_run_at to now-1min on all active topics.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen, no writes.")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
