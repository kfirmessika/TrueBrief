"""
validate_pipeline.py — Accumulated history validation script.

Compares what TrueBrief has stored for an existing topic against what Gemini
Search returns for the same query and time window. Also shows duplicate analysis
and what the pipeline dropped in recent scans.

This tests what the USER actually sees (accumulated facts across many scans),
not a one-clean-scan benchmark. See strategy_quality_crisis memory: the old
benchmark validated the wrong thing.

Usage:
    python scripts/validate_pipeline.py --topic-id <uuid>
    python scripts/validate_pipeline.py --topic-name "iran war"
    python scripts/validate_pipeline.py --topic-name "trump" --days 3
    python scripts/validate_pipeline.py --topic-name "trump" --compare-gemini

What it shows:
    1. Stored facts (last N days), grouped by date + with signal_score when present
    2. Near-duplicates in stored facts (cosine > threshold between stored facts)
    3. What the pipeline dropped (from pipeline_trace signal_score stage)
    4. [--compare-gemini] Gemini Search result + LLM judge comparison

Hard rule: the pipeline is only "working" if stored facts are non-redundant,
signal-worthy, and better than or equal to Gemini on the same time window.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Bootstrap — ensure we can import truebrief from project root
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

import numpy as np
from dotenv import load_dotenv
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from truebrief.ledger.database import get_supabase

# Model with Google Search grounding support + available quota
# (same as scripts/quality_benchmark.py).
GEMINI_SEARCH_MODEL = "gemini-2.5-flash-lite"
GEMINI_JUDGE_MODEL = "gemini-2.5-flash-lite"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cosine(a, b) -> float:
    av, bv = np.array(a, dtype=float), np.array(b, dtype=float)
    denom = np.linalg.norm(av) * np.linalg.norm(bv)
    return float(np.dot(av, bv) / denom) if denom > 0 else 0.0


def _parse_emb(raw):
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return None
    return raw


def _find_near_dupes(facts: List[dict], threshold: float = 0.85) -> List[tuple]:
    """
    Find pairs of stored facts that are suspiciously similar (probably duplicates
    that slipped through within-batch dedup + arbiter).
    Returns list of (fact_a, fact_b, cosine_sim).
    """
    pairs = []
    facts_with_emb = []
    for f in facts:
        emb = _parse_emb(f.get("alpha_embedding"))
        if emb:
            facts_with_emb.append((f, np.array(emb, dtype=float)))

    for i, (a, ea) in enumerate(facts_with_emb):
        for b, eb in facts_with_emb[i + 1:]:
            denom = np.linalg.norm(ea) * np.linalg.norm(eb)
            sim = float(np.dot(ea, eb) / denom) if denom > 0 else 0.0
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
# Data fetching (matches the REAL schema: topics.raw_query, known_facts.first_seen_at)
# ---------------------------------------------------------------------------

def fetch_topic(db, topic_id: Optional[str], topic_name: Optional[str]) -> dict:
    if topic_id:
        resp = db.table("topics").select("*").eq("id", topic_id).single().execute()
        row = resp.data
    else:
        resp = db.table("topics").select("*").ilike("raw_query", f"%{topic_name}%").limit(1).execute()
        row = resp.data[0] if resp.data else None

    if not row:
        print(f"ERROR: Topic not found (id={topic_id}, name={topic_name})")
        sys.exit(1)
    return row


_FACT_COLUMNS_WITH_SIGNAL = (
    "id, alpha_text, event_date, first_seen_at, signal_score, signal_class, "
    "event_class, source_domain, verified_count, relevance, alpha_embedding"
)
_FACT_COLUMNS_BASE = (
    "id, alpha_text, event_date, first_seen_at, "
    "event_class, source_domain, verified_count, relevance, alpha_embedding"
)


def fetch_facts(db, topic_id: str, days: int) -> List[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    for columns in (_FACT_COLUMNS_WITH_SIGNAL, _FACT_COLUMNS_BASE):
        try:
            resp = (
                db.table("known_facts")
                .select(columns)
                .eq("topic_id", topic_id)
                .gte("first_seen_at", since)
                .order("first_seen_at", desc=True)
                .limit(200)
                .execute()
            )
            return resp.data or []
        except Exception:
            # signal_score/signal_class columns absent (migration 025 not applied)
            continue
    return []


def fetch_recent_drops(db, topic_id: str, days: int) -> List[dict]:
    """Fetch signal_score stage traces for this topic's recent runs.

    pipeline_trace has no topic_id — join through pipeline_run.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    try:
        runs = (
            db.table("pipeline_run")
            .select("id, started_at")
            .eq("topic_id", topic_id)
            .gte("started_at", since)
            .order("started_at", desc=True)
            .limit(20)
            .execute()
        )
        run_ids = [r["id"] for r in (runs.data or [])]
        if not run_ids:
            return []
        resp = (
            db.table("pipeline_trace")
            .select("pipeline_run_id, created_at, label, data")
            .in_("pipeline_run_id", run_ids)
            .eq("stage", "signal_score")
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
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def print_facts(facts: List[dict], limit: int = 40) -> None:
    for i, f in enumerate(facts[:limit]):
        score = f.get("signal_score")
        cls = f.get("signal_class") or f.get("event_class") or "?"
        score_str = f"[{cls}/{score}]" if score is not None else f"[{cls}]"
        date_str = _format_date(f.get("event_date") or f.get("first_seen_at"))
        domain = f.get("source_domain") or "?"
        verified = f.get("verified_count", 0)
        v_str = f" +{verified - 1}src" if verified and verified > 1 else ""
        rel = f.get("relevance")
        rel_str = f" rel={rel:.2f}" if isinstance(rel, (int, float)) else ""
        print(f"  {i + 1:3}. {score_str} {date_str} | {domain}{v_str}{rel_str}")
        print(f"       {f['alpha_text'][:130]}")
    if len(facts) > limit:
        print(f"  ... and {len(facts) - limit} more")


def print_dupes(pairs: List[tuple], limit: int = 15) -> None:
    if not pairs:
        print("  None found (good!)")
        return
    for a, b, sim in pairs[:limit]:
        print(f"\n  Similarity: {sim}")
        print(f"  A [{_format_date(a.get('event_date'))}]: {a['alpha_text'][:110]}")
        print(f"  B [{_format_date(b.get('event_date'))}]: {b['alpha_text'][:110]}")
    if len(pairs) > limit:
        print(f"\n  ... and {len(pairs) - limit} more pairs")


def print_drops(traces: List[dict]) -> None:
    if not traces:
        print("  No signal_score traces found (V4_SIGNAL_SCORER not enabled yet, or no scans since).")
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
# Gemini comparison (google-genai SDK, same pattern as quality_benchmark.py)
# ---------------------------------------------------------------------------

def _gemini_search(topic_name: str, api_key: str, days: int) -> Tuple[Optional[str], Optional[str]]:
    """Run Gemini with Google Search grounding. Returns (text, error)."""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=GEMINI_SEARCH_MODEL,
            contents=(
                f"What are the most important developments from the last {days} days "
                f"about: {topic_name}? List the top 5-10 specific facts (concrete "
                "events, decisions, numbers, with dates). Be concise — one bullet per "
                "fact. Only real developments; no background, no opinions."
            ),
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            ),
        )
        return response.text, None
    except Exception as e:
        return None, str(e)


def _gemini_judge(topic_name: str, ours: str, reference: str, api_key: str) -> Tuple[Optional[str], Optional[str]]:
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        judge_prompt = f"""You are auditing two news intelligence systems on the topic: "{topic_name}"

SYSTEM A (TrueBrief — accumulated facts from multiple automated scans):
{ours}

SYSTEM B (Gemini Search — fresh single grounded query today):
{reference}

Answer these four questions, specifically and harshly:
1. MISSING: What important stories does B have that A is missing entirely?
2. NOISE: What duplicates / irrelevant / low-value items does A have that B correctly excluded? List them.
3. MEMORY ADVANTAGE: What does A have that B missed (a real benefit of accumulated tracking)?
4. VERDICT: Is A better, worse, or equal to B for a user tracking this topic right now? One sentence why.

This is a quality audit. Do not be polite."""
        response = client.models.generate_content(
            model=GEMINI_JUDGE_MODEL,
            contents=judge_prompt,
        )
        return response.text, None
    except Exception as e:
        return None, str(e)


def run_gemini_comparison(topic_name: str, facts: List[dict], days: int) -> None:
    from config.settings import settings
    api_key = settings.GOOGLE_API_KEY
    if not api_key:
        print("  ERROR: GOOGLE_API_KEY not set in .env")
        return

    print(f"  Running Gemini Search ({GEMINI_SEARCH_MODEL}, grounded)...")
    gemini_text, err = _gemini_search(topic_name, api_key, days)
    if err:
        print(f"  ERROR: Gemini call failed: {err}")
        return

    our_facts_text = "\n".join(
        f"- [{_format_date(f.get('event_date'))}] {f['alpha_text']}"
        for f in facts[:40]
    ) or "(no facts stored in this window)"

    print("\n  --- Gemini Search output ---")
    print(gemini_text[:2500])

    print("\n  --- Our stored facts (same window) ---")
    print(our_facts_text[:2500])

    print("\n  --- LLM Judge ---")
    judge_text, jerr = _gemini_judge(topic_name, our_facts_text, gemini_text, api_key)
    if jerr:
        print(f"  Judge LLM failed: {jerr}")
    else:
        print(judge_text)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Validate TrueBrief pipeline output vs accumulated history")
    parser.add_argument("--topic-id", help="Topic UUID")
    parser.add_argument("--topic-name", help="Topic raw_query (partial match)")
    parser.add_argument("--days", type=int, default=7, help="Look back N days (default: 7)")
    parser.add_argument("--compare-gemini", action="store_true", help="Run Gemini comparison + LLM judge")
    parser.add_argument("--dup-threshold", type=float, default=0.85,
                        help="Cosine threshold for duplicate detection (default: 0.85)")
    args = parser.parse_args()

    if not args.topic_id and not args.topic_name:
        parser.print_help()
        sys.exit(1)

    db = get_supabase()

    # 1. Resolve topic
    topic = fetch_topic(db, args.topic_id, args.topic_name)
    topic_id = topic["id"]
    topic_name = topic.get("raw_query") or "unknown"

    print(f"\nTopic: {topic_name} (id={topic_id})")
    print(f"Window: last {args.days} days")

    # 2. Stored facts
    facts = fetch_facts(db, topic_id, args.days)
    section(f"Stored Facts ({len(facts)} in last {args.days} days)")
    if facts:
        print_facts(facts)
    else:
        print("  No facts stored in this window.")

    # 3. Signal score distribution (only if migration 025 applied + scorer ran)
    scored = [f for f in facts if f.get("signal_score") is not None]
    if scored:
        scores = [f["signal_score"] for f in scored]
        print(f"\n  Signal score distribution (n={len(scored)}):")
        for band, label in [(range(8, 11), "8-10 (strong signal)"),
                            (range(6, 8), "6-7  (clear signal)"),
                            (range(4, 6), "4-5  (borderline - should be rare)"),
                            (range(0, 4), "0-3  (noise - should not be stored)")]:
            count = sum(1 for s in scores if s in band)
            bar = "#" * count
            print(f"    {label}: {count:3}  {bar}")

    # 4. Near-duplicate analysis
    section(f"Near-Duplicates in Stored Facts (cosine > {args.dup_threshold})")
    dupes = _find_near_dupes(facts, threshold=args.dup_threshold)
    print_dupes(dupes)
    if dupes:
        uniq_ids = set()
        for a, b, _ in dupes:
            uniq_ids.add(a["id"])
            uniq_ids.add(b["id"])
        print(f"\n  {len(dupes)} near-duplicate pair(s) involving {len(uniq_ids)} of {len(facts)} facts "
              f"({100 * len(uniq_ids) // max(1, len(facts))}% of the window is redundant).")

    # 5. Pipeline drops (from signal_score trace)
    section("What the Pipeline Dropped (SignalScorer trace)")
    traces = fetch_recent_drops(db, topic_id, args.days)
    print_drops(traces)

    # 6. Optional Gemini comparison
    if args.compare_gemini:
        section("Gemini Search Comparison")
        run_gemini_comparison(topic_name, facts, args.days)

    print()


if __name__ == "__main__":
    main()
