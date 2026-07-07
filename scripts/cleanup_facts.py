"""
cleanup_facts.py — retroactive cleanup of stored facts.

Two independent passes:

1. --dups       Deterministic duplicate collapse: the arbiter's same-day rule
                applied retroactively (cosine >= 0.93 + same event_date + same
                digit runs). Keeps the longest text of each duplicate cluster,
                deletes the rest. No LLM involved.

2. --off-topic  LLM pass over recent facts (default last 7 days): re-scores
                them with the SignalScorer and deletes ONLY facts judged
                on_topic=false. Low scores alone never delete (old facts score
                low for staleness — that's not a reason to erase history).

Default is DRY RUN (prints what would be deleted). Add --apply to delete.

Usage:
    python scripts/cleanup_facts.py --dups                    # dry run
    python scripts/cleanup_facts.py --dups --apply
    python scripts/cleanup_facts.py --off-topic --days 7 --apply
    python scripts/cleanup_facts.py --dups --off-topic --apply
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

import numpy as np
from dotenv import load_dotenv
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from truebrief.ledger.database import get_supabase

DUP_COSINE = 0.93


def _digits(t: str) -> list:
    return re.findall(r"\d+", t)


def _emb(raw):
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            return np.array(json.loads(raw), dtype=float)
        except Exception:
            return None
    return np.array(raw, dtype=float)


def find_dup_clusters(rows: list[dict]) -> list[str]:
    """Return ids to DELETE: for each duplicate cluster keep the longest text."""
    facts = []
    for r in rows:
        e = _emb(r.get("alpha_embedding"))
        if e is not None:
            facts.append((r, e))

    # Greedy: process longest-text first; anything later that matches a kept
    # fact is a duplicate of it.
    facts.sort(key=lambda fe: -len(fe[0]["alpha_text"]))
    kept: list[tuple[dict, np.ndarray]] = []
    to_delete: list[dict] = []
    for r, e in facts:
        is_dup = False
        for kr, ke in kept:
            denom = np.linalg.norm(e) * np.linalg.norm(ke)
            if denom == 0:
                continue
            sim = float(e @ ke / denom)
            if (
                sim >= DUP_COSINE
                and str(r.get("event_date"))[:10] == str(kr.get("event_date"))[:10]
                and _digits(r["alpha_text"]) == _digits(kr["alpha_text"])
            ):
                to_delete.append(r)
                is_dup = True
                break
        if not is_dup:
            kept.append((r, e))
    return to_delete


def run_dups(db, topics: dict, apply: bool) -> None:
    print("\n=== PASS 1: deterministic duplicates (cosine>=0.93, same day, same numbers) ===")
    total = 0
    for name, tid in topics.items():
        rows = (
            db.table("known_facts")
            .select("id, alpha_text, event_date, alpha_embedding")
            .eq("topic_id", tid)
            .execute()
        ).data or []
        dels = find_dup_clusters(rows)
        total += len(dels)
        print(f"\n{name}: {len(rows)} facts, {len(dels)} duplicates to delete")
        for d in dels:
            print("   DEL:", d["alpha_text"][:90])
        if apply and dels:
            ids = [d["id"] for d in dels]
            db.table("known_facts").delete().in_("id", ids).execute()
            print(f"   -> deleted {len(ids)}")
    print(f"\nPass 1 total: {total} rows {'DELETED' if apply else 'would be deleted (dry run)'}")


def run_off_topic(db, topics: dict, days: int, apply: bool) -> None:
    from truebrief.pipeline.signal_scorer import SignalScorer
    from truebrief.models.alpha import Alpha

    print(f"\n=== PASS 2: LLM off-topic sweep (last {days} days; deletes on_topic=false ONLY) ===")
    scorer = SignalScorer()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    total = 0
    for name, tid in topics.items():
        rows = (
            db.table("known_facts")
            .select("id, alpha_text")
            .eq("topic_id", tid)
            .gte("first_seen_at", since)
            .execute()
        ).data or []
        if not rows:
            print(f"\n{name}: no facts in window")
            continue
        dels: list[dict] = []
        # Batches of 25 to keep prompts small and verdicts sharp.
        for i in range(0, len(rows), 25):
            batch = rows[i : i + 25]
            alphas = [
                Alpha(alpha_text=r["alpha_text"], entities=[], source_url="", source_name="")
                for r in batch
            ]
            # topic_id=None: no prototype interaction, pure LLM verdicts.
            _, log = scorer.score(alphas, topic_name=name, topic_id=None)
            by_text = {e["text"]: e for e in log}
            for r in batch:
                e = by_text.get(r["alpha_text"][:200])
                if e and e.get("drop_reason") == "off_topic":
                    dels.append(r)
        total += len(dels)
        print(f"\n{name}: {len(rows)} facts in window, {len(dels)} off-topic to delete")
        for d in dels:
            print("   DEL:", d["alpha_text"][:90])
        if apply and dels:
            ids = [d["id"] for d in dels]
            db.table("known_facts").delete().in_("id", ids).execute()
            print(f"   -> deleted {len(ids)}")
    print(f"\nPass 2 total: {total} rows {'DELETED' if apply else 'would be deleted (dry run)'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dups", action="store_true")
    ap.add_argument("--off-topic", action="store_true")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--apply", action="store_true", help="actually delete (default: dry run)")
    args = ap.parse_args()
    if not args.dups and not args.off_topic:
        ap.print_help()
        sys.exit(1)

    db = get_supabase()
    topics = {
        t["raw_query"]: t["id"]
        for t in (db.table("topics").select("id, raw_query").eq("is_active", True).execute().data or [])
    }
    print("Topics:", ", ".join(topics))
    if not args.apply:
        print("*** DRY RUN — nothing will be deleted. Add --apply to delete. ***")

    if args.dups:
        run_dups(db, topics, args.apply)
    if args.off_topic:
        run_off_topic(db, topics, args.days, args.apply)


if __name__ == "__main__":
    main()
