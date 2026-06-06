"""
audit_topic.py — Pipeline Audit Dump

Pulls everything TrueBrief has stored for a topic (Iran war or any keyword)
and writes a structured report to reports/audit_<topic>_<timestamp>.md

Tables queried:
  topics          — topic config and last scan time
  known_facts     — every alpha (NEW + UPDATE) with event_date, source, arbiter decision
  story_nodes     — story clusters with summaries
  briefs          — final delivered briefs with timestamps

Usage:
  python scripts/audit_topic.py "iran"
  python scripts/audit_topic.py "iran" --output reports/
"""

from __future__ import annotations

import sys
import os
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

# Allow importing from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv
load_dotenv()

from truebrief.ledger.database import get_supabase


def fetch_topics(db, keyword: str) -> list[dict]:
    resp = db.table("topics").select("*").ilike("raw_query", f"%{keyword}%").execute()
    return resp.data or []


def fetch_facts(db, topic_id: str) -> list[dict]:
    resp = (
        db.table("known_facts")
        .select("id, alpha_text, context, source_url, source_domain, event_date, first_seen_at, entities, confidence, story_node_id")
        .eq("topic_id", topic_id)
        .order("first_seen_at", desc=False)
        .execute()
    )
    return resp.data or []


def fetch_stories(db, topic_id: str) -> list[dict]:
    resp = (
        db.table("story_nodes")
        .select("id, title, summary, status, fact_count, created_at, updated_at")
        .eq("topic_id", topic_id)
        .order("created_at", desc=False)
        .execute()
    )
    return resp.data or []


def fetch_briefs(db, topic_id: str) -> list[dict]:
    resp = (
        db.table("briefs")
        .select("id, content, delivered_at, is_read, facts_json")
        .eq("topic_id", topic_id)
        .order("delivered_at", desc=False)
        .execute()
    )
    return resp.data or []


def fmt_ts(ts: str | None) -> str:
    if not ts:
        return "—"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return ts


def fmt_event_date(ts: str | None) -> str:
    """Event date — may be less precise, mark clearly."""
    if not ts:
        return "⚠ no event_date"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return ts


def build_report(keyword: str, topics: list, db) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = []
    lines.append(f"# TrueBrief Pipeline Audit — \"{keyword}\"")
    lines.append(f"Generated: {now}")
    lines.append(f"Topics matched: {len(topics)}")
    lines.append("")

    for topic in topics:
        tid = topic["id"]
        lines.append(f"---")
        lines.append(f"## TOPIC: {topic['raw_query']}")
        lines.append(f"- **ID:** `{tid}`")
        lines.append(f"- **Active:** {topic.get('is_active', '?')}")
        lines.append(f"- **Frequency:** {topic.get('frequency', '?')}")
        lines.append(f"- **Last scan:** {fmt_ts(topic.get('last_run_at') or topic.get('last_checked_at'))}")
        lines.append(f"- **Created:** {fmt_ts(topic.get('created_at'))}")

        # Strategy summary
        strategy = topic.get("search_strategy") or {}
        if strategy:
            topic_name = strategy.get("topic_name", "")
            primary_q = strategy.get("primary_query", "")
            if topic_name:
                lines.append(f"- **Topic name (LLM):** {topic_name}")
            if primary_q:
                lines.append(f"- **Primary query:** {primary_q}")
        lines.append("")

        # ── FACTS ──────────────────────────────────────────────────────────────
        facts = fetch_facts(db, tid)
        lines.append(f"### FACTS ({len(facts)} total)")
        lines.append("")

        if not facts:
            lines.append("_No facts stored._")
            lines.append("")
        else:
            # Group by day for readability
            by_day: dict[str, list] = {}
            for f in facts:
                day = (f.get("first_seen_at") or "")[:10] or "unknown"
                by_day.setdefault(day, []).append(f)

            for day in sorted(by_day.keys()):
                lines.append(f"#### {day} ({len(by_day[day])} facts)")
                for f in by_day[day]:
                    event_dt = fmt_event_date(f.get("event_date"))
                    seen_dt = fmt_ts(f.get("first_seen_at"))
                    story_id = f.get("story_node_id")
                    story_tag = f"story:`{story_id[:8]}`" if story_id else "⚠ no story"
                    domain = f.get("source_domain") or (f.get("source_url") or "")[:40]
                    confidence = f.get("confidence", "?")
                    entities = ", ".join(f.get("entities") or []) or "—"

                    lines.append(f"- **[{seen_dt}]** {f['alpha_text']}")
                    lines.append(f"  - Event date: `{event_dt}`")
                    lines.append(f"  - Source: {domain}")
                    lines.append(f"  - Entities: {entities}")
                    lines.append(f"  - Confidence: {confidence} | {story_tag}")
                    if f.get("context"):
                        lines.append(f"  - Context: _{f['context']}_")
                    lines.append("")

        # ── STORIES ────────────────────────────────────────────────────────────
        stories = fetch_stories(db, tid)
        lines.append(f"### STORY NODES ({len(stories)} total)")
        lines.append("")

        if not stories:
            lines.append("_No story nodes._")
            lines.append("")
        else:
            for s in stories:
                lines.append(f"#### Story `{s['id'][:8]}` — {s['title'][:80]}")
                lines.append(f"- **Status:** {s.get('status', '?')} | **Facts:** {s.get('fact_count', 0)}")
                lines.append(f"- **Created:** {fmt_ts(s.get('created_at'))} | **Updated:** {fmt_ts(s.get('updated_at'))}")
                lines.append(f"- **Summary:** {s.get('summary', '—')}")
                lines.append("")

        # ── BRIEFS ─────────────────────────────────────────────────────────────
        briefs = fetch_briefs(db, tid)
        lines.append(f"### BRIEFS ({len(briefs)} total)")
        lines.append("")

        if not briefs:
            lines.append("_No briefs delivered._")
            lines.append("")
        else:
            for b in briefs:
                delivered = fmt_ts(b.get("delivered_at"))
                is_read = "✓ read" if b.get("is_read") else "unread"
                facts_count = len(b.get("facts_json") or [])
                lines.append(f"#### Brief delivered {delivered} ({is_read})")
                lines.append(f"- Facts snapshot: {facts_count} facts")
                lines.append("")
                # Indent brief content
                for content_line in (b.get("content") or "").splitlines():
                    lines.append(f"  {content_line}")
                lines.append("")

        # ── SIGNAL STATS ───────────────────────────────────────────────────────
        lines.append(f"### SIGNAL STATS")
        lines.append("")
        total_facts = len(facts)
        facts_with_event_date = sum(1 for f in facts if f.get("event_date"))
        facts_with_context = sum(1 for f in facts if f.get("context"))
        facts_with_story = sum(1 for f in facts if f.get("story_node_id"))
        lines.append(f"| Metric | Count | % |")
        lines.append(f"|--------|-------|---|")
        lines.append(f"| Total facts | {total_facts} | 100% |")
        lines.append(f"| Facts with event_date | {facts_with_event_date} | {pct(facts_with_event_date, total_facts)} |")
        lines.append(f"| Facts with context | {facts_with_context} | {pct(facts_with_context, total_facts)} |")
        lines.append(f"| Facts linked to a story | {facts_with_story} | {pct(facts_with_story, total_facts)} |")
        lines.append(f"| Story nodes | {len(stories)} | — |")
        lines.append(f"| Briefs delivered | {len(briefs)} | — |")
        lines.append("")

        # Source diversity
        sources: dict[str, int] = {}
        for f in facts:
            d = f.get("source_domain") or "unknown"
            sources[d] = sources.get(d, 0) + 1
        if sources:
            lines.append(f"**Sources breakdown ({len(sources)} unique domains):**")
            for src, count in sorted(sources.items(), key=lambda x: -x[1]):
                lines.append(f"- {src}: {count} facts")
            lines.append("")

    return "\n".join(lines)


def pct(n: int, total: int) -> str:
    if total == 0:
        return "—"
    return f"{n/total*100:.0f}%"


def main():
    parser = argparse.ArgumentParser(description="Dump TrueBrief pipeline data for a topic keyword.")
    parser.add_argument("keyword", type=str, help="Keyword to search for in topic raw_query (e.g. 'iran')")
    parser.add_argument("--output", type=str, default="reports", help="Output directory (default: reports/)")
    args = parser.parse_args()

    db = get_supabase()
    keyword = args.keyword.lower()

    print(f"[audit] Searching topics for keyword: '{keyword}'...")
    topics = fetch_topics(db, keyword)

    if not topics:
        print(f"[audit] No topics found matching '{keyword}'. Check the database.")
        sys.exit(1)

    print(f"[audit] Found {len(topics)} topic(s). Fetching data...")

    report = build_report(keyword, topics, db)

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_kw = keyword.replace(" ", "_")[:30]
    out_path = out_dir / f"audit_{safe_kw}_{ts}.md"

    out_path.write_text(report, encoding="utf-8")
    print(f"[audit] Report written to: {out_path}")
    print(f"[audit] Open it to see the full pipeline history.")


if __name__ == "__main__":
    main()
