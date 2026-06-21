#!/usr/bin/env python3
"""
scripts/quality_benchmark.py

Automated signal-quality benchmark: TrueBrief vs Gemini-Search reference.

Run any time after pipeline changes to see if quality improved or regressed.
No web server needed — imports PipelineRunner directly.

Usage:
    python scripts/quality_benchmark.py "Iran War"
    python scripts/quality_benchmark.py "Trump" "Iran War"   # multiple topics
    python scripts/quality_benchmark.py                       # preset topics

Output:
    • Console: score table + gap list
    • docs/benchmarks/YYYY-MM-DD_<slug>.md  (full report with both briefs)
"""

import os
import sys
import json
import uuid
import datetime
import concurrent.futures
import re
import argparse

# ── bootstrap path + env ───────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv  # noqa: E402  (after sys.path is set)
load_dotenv(os.path.join(ROOT, ".env"))

# ── config ─────────────────────────────────────────────────────────────────────
SEARCH_MODEL  = "gemini-2.5-flash-lite"  # supports Google Search grounding + has quota
JUDGE_MODEL   = "gemini-2.5-flash-lite"
PIPELINE_TIMEOUT = 300               # seconds

DEFAULT_TOPICS = [
    "Iran War ceasefire deal",
    "Trump White House",
]

GEMINI_SEARCH_PROMPT = (
    "Give me the latest news about '{topic}' as of today, {date}. "
    "Maximum signal-to-noise: start with the single most important CURRENT development, "
    "then list the 4-6 most significant other facts. "
    "Be specific — include dates, numbers, names. "
    "No background filler unless it changes the meaning. "
    "No prediction."
)

JUDGE_PROMPT = """You are a news intelligence quality judge.

TOPIC: {topic}
DATE: {date}

=== BRIEF A  (TrueBrief — our system) ===
{brief_a}

=== BRIEF B  (Reference — Gemini Search grounding) ===
{brief_b}

Score each 0-10 on four axes:
  lede_quality  — does it immediately surface the most important current development?
  completeness  — does it cover all key stories, or miss important ones?
  synthesis     — does it provide a "so what" / state of play / biggest-story summary?
  noise_level   — free of repetition, old news, low-priority items? (10=clean, 0=noisy)

Also identify:
  gaps_in_ours          — specific stories/facts Brief B covered that Brief A missed (max 6)
  false_positives_in_ours — items Brief A included that Brief B correctly excluded
  verdict               — one sentence: who wins, by how much, the single most fixable reason

Respond ONLY with valid JSON matching this exact schema (no markdown fences):
{{
  "scores": {{
    "lede_quality":  {{"ours": N, "reference": N}},
    "completeness":  {{"ours": N, "reference": N}},
    "synthesis":     {{"ours": N, "reference": N}},
    "noise_level":   {{"ours": N, "reference": N}}
  }},
  "gaps_in_ours": ["...", "..."],
  "false_positives_in_ours": ["..."],
  "verdict": "..."
}}
"""

# ── runners ────────────────────────────────────────────────────────────────────

def run_truebrief(topic: str) -> tuple[str, str | None]:
    """Run the full TrueBrief pipeline against a throwaway real topic.

    A real topics row is required because known_facts.topic_id has a FK to it —
    a random UUID makes every fact insert fail and never exercises storage/dedup.
    The temp topic (and its facts) are deleted in finally so the DB stays clean.
    """
    db = None
    temp_topic_id = None
    try:
        from truebrief.ledger.database import get_supabase
        from truebrief.pipeline.runner import PipelineRunner

        db = get_supabase()
        marker = f"[bench] {topic} {uuid.uuid4().hex[:8]}"
        res = db.table("topics").insert({"raw_query": marker}).execute()
        temp_topic_id = res.data[0]["id"]

        runner = PipelineRunner()
        brief = runner.run(topic, topic_id=temp_topic_id)
        return (brief or "(pipeline returned empty brief)"), None
    except Exception as exc:
        return "", f"Pipeline error: {exc}"
    finally:
        if db is not None and temp_topic_id is not None:
            for table, col in (
                ("known_facts", "topic_id"),
                ("source_quality_log", "topic_id"),
                ("topics", "id"),
            ):
                try:
                    db.table(table).delete().eq(col, temp_topic_id).execute()
                except Exception:
                    pass


def run_gemini_search(topic: str) -> tuple[str, list[dict], str | None]:
    """Call Gemini with Google Search grounding. Returns (text, sources, error)."""
    try:
        from google import genai
        from google.genai import types
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", "")
        client = genai.Client(api_key=api_key)
        prompt = GEMINI_SEARCH_PROMPT.format(
            topic=topic, date=datetime.date.today().isoformat()
        )
        response = client.models.generate_content(
            model=SEARCH_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            ),
        )
        sources: list[dict] = []
        cand = response.candidates[0] if response.candidates else None
        if cand and cand.grounding_metadata:
            for chunk in cand.grounding_metadata.grounding_chunks or []:
                if chunk.web:
                    sources.append({"url": chunk.web.uri, "title": chunk.web.title})
        return response.text, sources, None
    except Exception as exc:
        return "", [], f"Gemini search error: {exc}"


def run_judge(topic: str, brief_ours: str, brief_reference: str) -> dict:
    """LLM judge: compare both briefs, return structured scores + gaps."""
    try:
        from google import genai
        from google.genai import types
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", "")
        client = genai.Client(api_key=api_key)
        prompt = JUDGE_PROMPT.format(
            topic=topic,
            date=datetime.date.today().isoformat(),
            brief_a=brief_ours,
            brief_b=brief_reference,
        )
        response = client.models.generate_content(
            model=JUDGE_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        raw = response.text.strip()
        # Extract the first {...} JSON object regardless of surrounding text/fences
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return {"error": f"No JSON in judge response: {raw[:200]}"}
        return json.loads(m.group(0))
    except Exception as exc:
        return {"error": str(exc)}


# ── formatting ─────────────────────────────────────────────────────────────────

def _total(scores: dict, key: str) -> int:
    return sum(scores.get(axis, {}).get(key, 0) for axis in scores)


def print_report(topic: str, result: dict) -> None:
    scores   = result.get("scores", {})
    gaps     = result.get("gaps_in_ours", [])
    fps      = result.get("false_positives_in_ours", [])
    verdict  = result.get("verdict", "—")
    error    = result.get("error")

    print(f"\n{'='*60}")
    print(f"  BENCHMARK: {topic}")
    print(f"  {datetime.date.today().isoformat()}")
    print(f"{'='*60}")

    if error:
        print(f"  [JUDGE ERROR] {error}")
        return

    axes = ["lede_quality", "completeness", "synthesis", "noise_level"]
    print(f"  {'Axis':<18} {'Ours':>6} {'Ref':>6}")
    print(f"  {'-'*32}")
    for ax in axes:
        o = scores.get(ax, {}).get("ours", "?")
        r = scores.get(ax, {}).get("reference", "?")
        flag = " <<<" if isinstance(o, int) and isinstance(r, int) and o < r - 2 else ""
        print(f"  {ax:<18} {str(o):>6} {str(r):>6}{flag}")
    print(f"  {'-'*32}")
    t_ours = _total(scores, "ours")
    t_ref  = _total(scores, "reference")
    print(f"  {'TOTAL':<18} {t_ours:>6} {t_ref:>6}")

    print(f"\n  VERDICT: {verdict}")

    if gaps:
        print(f"\n  GAPS IN OURS ({len(gaps)}):")
        for g in gaps:
            print(f"    - {g}")
    if fps:
        print(f"\n  FALSE POSITIVES IN OURS ({len(fps)}):")
        for fp in fps:
            print(f"    - {fp}")


def save_report(
    topic: str,
    brief_ours: str,
    brief_ref: str,
    ref_sources: list[dict],
    result: dict,
) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    date_str = datetime.date.today().isoformat()
    filename = f"{date_str}_{slug}.md"
    out_dir = os.path.join(ROOT, "docs", "benchmarks")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)

    scores  = result.get("scores", {})
    gaps    = result.get("gaps_in_ours", [])
    fps     = result.get("false_positives_in_ours", [])
    verdict = result.get("verdict", "—")
    axes    = ["lede_quality", "completeness", "synthesis", "noise_level"]
    t_ours  = _total(scores, "ours")
    t_ref   = _total(scores, "reference")

    lines = [
        f"# Benchmark: {topic}",
        f"**Date:** {date_str}  |  **Models:** pipeline={SEARCH_MODEL}, judge={JUDGE_MODEL}",
        "",
        "## Scores",
        "",
        f"| Axis | Ours | Reference |",
        f"|---|---|---|",
    ]
    for ax in axes:
        o = scores.get(ax, {}).get("ours", "?")
        r = scores.get(ax, {}).get("reference", "?")
        flag = " ⚠️" if isinstance(o, int) and isinstance(r, int) and o < r - 2 else ""
        lines.append(f"| {ax}{flag} | {o} | {r} |")
    lines += [
        f"| **TOTAL** | **{t_ours}** | **{t_ref}** |",
        "",
        f"**Verdict:** {verdict}",
        "",
    ]

    if gaps:
        lines += ["## Gaps in TrueBrief", ""]
        for g in gaps:
            lines.append(f"- {g}")
        lines.append("")

    if fps:
        lines += ["## False Positives in TrueBrief", ""]
        for fp in fps:
            lines.append(f"- {fp}")
        lines.append("")

    lines += [
        "## TrueBrief Output",
        "",
        "```",
        brief_ours or "(empty)",
        "```",
        "",
        "## Reference Output (Gemini Search)",
        "",
        "```",
        brief_ref or "(empty)",
        "```",
        "",
    ]
    if ref_sources:
        lines += ["## Reference Sources", ""]
        for s in ref_sources:
            lines.append(f"- [{s.get('title', s['url'])}]({s['url']})")
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return path


# ── main ───────────────────────────────────────────────────────────────────────

def benchmark_topic(topic: str) -> dict:
    """Run benchmark for one topic. Returns judge result dict."""
    print(f"\n[BENCHMARK] Topic: '{topic}'")
    print("  Running TrueBrief pipeline + Gemini Search in parallel...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        tb_future  = pool.submit(run_truebrief, topic)
        gem_future = pool.submit(run_gemini_search, topic)

        brief_ours, tb_err       = tb_future.result(timeout=PIPELINE_TIMEOUT)
        brief_ref, ref_sources, gem_err = gem_future.result(timeout=60)

    if tb_err:
        print(f"  [!] TrueBrief pipeline failed: {tb_err}")
    if gem_err:
        print(f"  [!] Gemini Search failed: {gem_err}")

    print("  Judging...")
    result = run_judge(topic, brief_ours, brief_ref)

    if "error" not in result:
        path = save_report(topic, brief_ours, brief_ref, ref_sources, result)
        result["_report_path"] = path
        print(f"  Report saved: {path}")

    return result, brief_ours, brief_ref, ref_sources


def main():
    parser = argparse.ArgumentParser(description="TrueBrief quality benchmark")
    parser.add_argument("topics", nargs="*", help="Topics to benchmark (default: preset list)")
    args = parser.parse_args()

    topics = args.topics if args.topics else DEFAULT_TOPICS

    all_results = []
    for topic in topics:
        result, brief_ours, brief_ref, ref_sources = benchmark_topic(topic)
        print_report(topic, result)
        all_results.append((topic, result))

    # Overall summary when multiple topics
    if len(all_results) > 1:
        print(f"\n{'='*60}")
        print("  OVERALL SUMMARY")
        print(f"{'='*60}")
        for topic, result in all_results:
            scores = result.get("scores", {})
            t_ours = _total(scores, "ours")
            t_ref  = _total(scores, "reference")
            winner = "OURS" if t_ours >= t_ref else "REF "
            print(f"  [{winner}] {topic}: {t_ours} vs {t_ref}")


if __name__ == "__main__":
    main()
