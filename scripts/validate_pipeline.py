"""
validate_pipeline.py — Accumulated history validation script.

Compares what TrueBrief has stored for an existing topic against what Gemini
Search returns for the same query and time window. Also shows duplicate analysis
and what the pipeline dropped in recent scans.

Usage:
    python scripts/validate_pipeline.py --topic-id <uuid>
    python scripts/validate_pipeline.py --topic-name "Iran nuclear deal"
    python scripts/validate_pipeline.py --topic-name "Iran nuclear deal" --days 3
    python scripts/validate_pipeline.py --topic-name "Iran nuclear deal" --compare-gemini

What it shows:
    1. Stored facts (last N days), grouped by date + with signal_score
    2. Near-duplicates in stored facts (cosine > 0.85 between stored facts)
    3. What the pipeline dropped (from pipeline_trace signal_score step)
    4. [--compare-gemini] Gemini Search result + LLM judge comparison

Hard rule: the pipeline is only "working" if stored facts are non-redundant,
signal-worthy, and better than or equal to Gemini on the same time window.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import List, Optional

# ---------------------------------------------------------------------------
# Bootstrap — ensure we can import truebrief from project root
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

import numpy as np
from dotenv import load_dotenv
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from truebrief.ledger.database import get_supabase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cosine(a, b) -> float:
    av, bv = np.array(a, dtype=float), np.array(b, dtype=float)
    denom = np.linalg.norm(av) * np.linalg.norm(bv)
    return float(np.dot(av, bv) / denom) if denom > 0 else 0.0


def _find_near_dupes(facts: List[dict], threshold: float = 0.85) -> List[tuple]:
    """
    Find pairs of stored facts that are suspiciously similar (probably duplicates
    that slipped through within-batch dedup + arbiter).
    Returns list of (fact_a, fact_b, cosine_sim).
    """
    pairs = []
    facts_with_emb = [f for f in facts if f.get("alpha_embedding")]
    for i, a in enumerate(facts_with_emb):
        for b in facts_with_emb[i+1:]:
            emb_a = a["alpha_embedding"]
            emb_b = b["alpha_embedding"]
            if isinstance(emb_a, str):
                emb_a = json.loads(emb_a)
            if isinstance(emb_b, str):
                emb_b = json.loads(emb_b)
            sim = _cosine(emb_a, emb_b)
            if sim >= threshold:
                pairs.append((a, b, round(sim, 3)))
    return sorted(pairs, key=lambda x: -x[2])


def _format_date(raw) -> str:
    if raw is None:
        return "unknown"
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except Exception:
            return raw[:10]
    return str(raw)[:10]


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_topic(db, topic_id: Optional[str], topic_name: Optional[str]) -> dict:
    if topic_id:
        resp = db.table("topics").select("*").eq("id", topic_id).single().execute()
    else:
        resp = db.table("topics").select("*").ilike("topic_name", f"%{topic_name}%").limit(1).execute()
        if resp.data:
            resp.data = resp.data[0]
        else:
            resp.data = None

    if not resp.data:
        print(f"ERROR: Topic not found (id={topic_id}, name={topic_name})")
        sys.exit(1)
    return resp.data


def fetch_facts(db, topic_id: str, days: int) -> List[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    resp = (
        db.table("known_facts")
        .select(
            "id, alpha_text, event_date, created_at, signal_score, signal_class, "
            "event_class, source_domain, verified_count, alpha_embedding"
        )
        .eq("topic_id", topic_id)
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(200)
        .execute()
    )
    return resp.data or []


def fetch_recent_drops(db, topic_id: str, days: int) -> List[dict]:
    """Fetch signal_score step data from pipeline_trace for recent runs."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    try:
        resp = (
            db.table("pipeline_trace")
            .select("created_at, data")
            .eq("topic_id", topic_id)
            .eq("step_name", "signal_score")
            .gte("created_at", since)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        return resp.data or []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def print_facts(facts: List[dict], limit: int = 30) -> None:
    for i, f in enumerate(facts[:limit]):
        score = f.get("signal_score")
        cls = f.get("signal_class") or f.get("event_class") or "?"
        score_str = f"[{cls}/{score}]" if score is not None else f"[{cls}]"
        date_str = _format_date(f.get("event_date") or f.get("created_at"))
        domain = f.get("source_domain") or "?"
        verified = f.get("verified_count", 0)
        v_str = f" +{verified-1}src" if verified and verified > 1 else ""
        print(f"  {i+1:3}. {score_str} {date_str} | {domain}{v_str}")
        print(f"       {f['alpha_text'][:120]}")
    if len(facts) > limit:
        print(f"  ... and {len(facts)-limit} more")


def print_dupes(pairs: List[tuple], limit: int = 10) -> None:
    if not pairs:
        print("  None found (good!)")
        return
    for a, b, sim in pairs[:limit]:
        print(f"\n  Similarity: {sim}")
        print(f"  A [{_format_date(a.get('event_date'))}]: {a['alpha_text'][:100]}")
        print(f"  B [{_format_date(b.get('event_date'))}]: {b['alpha_text'][:100]}")


def print_drops(traces: List[dict]) -> None:
    if not traces:
        print("  No signal_score traces found (V4_SIGNAL_SCORER may not be enabled yet)")
        return
    for trace in traces[:3]:
        created = _format_date(trace.get("created_at"))
        data = trace.get("data") or {}
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                continue
        kept = data.get("kept", "?")
        dropped = data.get("dropped", "?")
        print(f"\n  Run {created}: kept={kept}, dropped={dropped}")
        scored_facts = data.get("scored_facts") or []
        dropped_facts = [f for f in scored_facts if not f.get("kept")]
        if dropped_facts:
            print(f"  Dropped ({len(dropped_facts)}):")
            for f in dropped_facts[:10]:
                reason = f.get("drop_reason", "?")
                cls = f.get("class") or "?"
                score = f.get("score")
                score_str = f"{cls}/{score}" if score is not None else reason
                print(f"    [{score_str}] {f.get('text', '')[:100]}")


# ---------------------------------------------------------------------------
# Gemini comparison
# ---------------------------------------------------------------------------

def run_gemini_comparison(topic_name: str, facts: List[dict]) -> None:
    """Fetch a Gemini grounded result and LLM-judge it against our stored facts."""
    try:
        import google.generativeai as genai
        from config.settings import settings
        genai.configure(api_key=settings.GOOGLE_API_KEY)
    except Exception as e:
        print(f"  ERROR: Could not init Gemini: {e}")
        return

    print("  Running Gemini Search (grounded)...")
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        google_search_tool = {"google_search": {}}
        response = model.generate_content(
            f"What are the most important recent developments about: {topic_name}? "
            "List the top 5-8 specific facts (concrete events, decisions, numbers). "
            "Be concise. One bullet per fact.",
            tools=[google_search_tool],
            generation_config={"max_output_tokens": 800},
        )
        gemini_text = response.text
    except Exception as e:
        print(f"  ERROR: Gemini call failed: {e}")
        return

    # Format our stored facts as a bullet list
    our_facts_text = "\n".join(
        f"- [{_format_date(f.get('event_date'))}] {f['alpha_text']}"
        for f in facts[:20]
    )

    print("\n  --- Gemini Search output ---")
    print(gemini_text[:1500])

    print("\n  --- Our stored facts (last N days) ---")
    print(our_facts_text[:1500])

    print("\n  --- LLM Judge ---")
    try:
        model2 = genai.GenerativeModel("gemini-2.0-flash")
        judge_prompt = f"""You are comparing two news intelligence systems on the topic: "{topic_name}"

SYSTEM A (TrueBrief — accumulated from multiple scans over several days):
{our_facts_text}

SYSTEM B (Gemini Search — fresh single query today):
{gemini_text}

Judge both systems. Answer:
1. What important stories does B have that A is MISSING entirely?
2. What noise/duplicates/irrelevant items does A have that B correctly excluded?
3. What does A have that B missed (A's advantage from accumulated memory)?
4. Overall: is A better, worse, or equal to B for this topic right now?

Be specific and harsh. This is a quality audit."""
        judge_resp = model2.generate_content(judge_prompt)
        print(judge_resp.text)
    except Exception as e:
        print(f"  Judge LLM failed: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Validate TrueBrief pipeline output vs accumulated history")
    parser.add_argument("--topic-id", help="Topic UUID")
    parser.add_argument("--topic-name", help="Topic name (partial match)")
    parser.add_argument("--days", type=int, default=7, help="Look back N days (default: 7)")
    parser.add_argument("--compare-gemini", action="store_true", help="Run Gemini comparison + LLM judge")
    parser.add_argument("--dup-threshold", type=float, default=0.85, help="Cosine threshold for duplicate detection (default: 0.85)")
    args = parser.parse_args()

    if not args.topic_id and not args.topic_name:
        parser.print_help()
        sys.exit(1)

    db = get_supabase()

    # 1. Resolve topic
    topic = fetch_topic(db, args.topic_id, args.topic_name)
    topic_id = topic["id"]
    topic_name = topic.get("topic_name") or topic.get("raw_query") or "unknown"

    print(f"\nTopic: {topic_name} (id={topic_id})")
    print(f"Window: last {args.days} days")

    # 2. Stored facts
    facts = fetch_facts(db, topic_id, args.days)
    section(f"Stored Facts ({len(facts)} in last {args.days} days)")
    if facts:
        print_facts(facts)
    else:
        print("  No facts stored in this window.")

    # 3. Signal score distribution
    if facts:
        scored = [f for f in facts if f.get("signal_score") is not None]
        if scored:
            scores = [f["signal_score"] for f in scored]
            print(f"\n  Signal score distribution (n={len(scored)}):")
            for band, label in [(range(8, 11), "8-10 (strong signal)"),
                                 (range(6, 8), "6-7  (clear signal)"),
                                 (range(4, 6), "4-5  (borderline — should be rare)"),
                                 (range(0, 4), "0-3  (noise — should not be stored)")]:
                count = sum(1 for s in scores if s in band)
                bar = "█" * count
                print(f"    {label}: {count:3}  {bar}")

    # 4. Near-duplicate analysis
    section(f"Near-Duplicates in Stored Facts (cosine > {args.dup_threshold})")
    dupes = _find_near_dupes(facts, threshold=args.dup_threshold)
    print_dupes(dupes)
    if dupes:
        print(f"\n  Found {len(dupes)} near-duplicate pair(s). These are facts that slipped")
        print("  through within-batch dedup + arbiter and were stored as separate entries.")

    # 5. Pipeline drops (from signal_score trace)
    section("What the Pipeline Dropped (SignalScorer trace)")
    traces = fetch_recent_drops(db, topic_id, args.days)
    print_drops(traces)

    # 6. Optional Gemini comparison
    if args.compare_gemini:
        section("Gemini Search Comparison")
        run_gemini_comparison(topic_name, facts)

    print()


if __name__ == "__main__":
    main()
