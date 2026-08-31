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

=== BRIEF V4  (TrueBrief V4 — old custom collect/harvest/arbitrate pipeline) ===
{brief_v4}

=== BRIEF V5  (TrueBrief V5 — Gemini Search grounding + memory/dedup + judge) ===
{brief_v5}

=== BRIEF REFERENCE  (a SIMPLE, unstructured "give me the news" ask to Gemini Search —
no memory, no dedup, no structured extraction; the honest floor to beat) ===
{brief_ref}

Score EACH of the three briefs 0-10 on four axes:
  lede_quality  — does it immediately surface the most important current development?
  completeness  — does it cover all key stories, or miss important ones?
  synthesis     — does it provide a "so what" / state of play / biggest-story summary?
  noise_level   — free of repetition, old news, low-priority items? (10=clean, 0=noisy)

Also identify (all relative to V5, since that's the system being evaluated for whether
it's worth building over just asking Gemini directly):
  gaps_in_v5             — specific stories/facts V4 or Reference covered that V5 missed (max 6)
  false_positives_in_v5  — items V5 included that the others correctly excluded (padding,
                            stale facts, duplicates that should have been merged)
  verdict                — one paragraph: rank the three plainly, and name the single most
                            fixable reason for V5's weakest axis if it's not winning outright.
                            Be explicit about whether V5 actually beats the simple Reference ask
                            — that comparison is the entire point of this benchmark.

Respond ONLY with valid JSON matching this exact schema (no markdown fences):
{{
  "scores": {{
    "lede_quality":  {{"v4": N, "v5": N, "reference": N}},
    "completeness":  {{"v4": N, "v5": N, "reference": N}},
    "synthesis":     {{"v4": N, "v5": N, "reference": N}},
    "noise_level":   {{"v4": N, "v5": N, "reference": N}}
  }},
  "gaps_in_v5": ["...", "..."],
  "false_positives_in_v5": ["..."],
  "verdict": "..."
}}
"""

# ── runners ────────────────────────────────────────────────────────────────────

def run_truebrief(topic: str) -> tuple[str, str | None]:
    """Run the V5 TrueBrief pipeline (GeminiSearchRunner) against a throwaway real topic.

    A real topics row is required because known_facts.topic_id has a FK to it.
    The temp topic (and its facts) are deleted in finally so the DB stays clean.
    """
    db = None
    temp_topic_id = None
    try:
        from truebrief.ledger.database import get_supabase
        from truebrief.pipeline.v5_runner import GeminiSearchRunner

        db = get_supabase()
        marker = f"[bench] {topic} {uuid.uuid4().hex[:8]}"
        res = db.table("topics").insert({"raw_query": marker}).execute()
        temp_topic_id = res.data[0]["id"]

        runner = GeminiSearchRunner()
        brief = runner.run(topic, topic_id=temp_topic_id)
        brief = brief or "(pipeline returned empty brief)"
        return brief, None
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


def run_v5(topic: str) -> tuple[str, str | None]:
    """Run the V5 pipeline: Gemini Search collector -> memory/dedup + judge -> briefer.

    Same throwaway-topic pattern as run_truebrief (known_facts.topic_id has an FK to
    topics, and the temp row + its facts are deleted in finally so the DB stays clean).
    Uses the SAME Briefer as V4 so the two outputs are formatted identically for the
    judge — the comparison is about the facts/dedup quality, not markdown formatting.
    """
    db = None
    temp_topic_id = None
    try:
        from truebrief.ledger.database import get_supabase
        from truebrief.arbiter.arbiter import Arbiter
        from truebrief.briefer.briefer import Briefer
        from truebrief.collector.gemini_search_collector import GeminiSearchCollector
        from truebrief.models.alpha import DecisionType

        db = get_supabase()
        marker = f"[bench-v5] {topic} {uuid.uuid4().hex[:8]}"
        res = db.table("topics").insert({"raw_query": marker}).execute()
        temp_topic_id = res.data[0]["id"]

        alphas = GeminiSearchCollector().collect(topic, last_run_date=None, topic_id=temp_topic_id)
        if not alphas:
            return "(V5 collector extracted no facts)", None

        arbiter = Arbiter()
        decisions = arbiter.judge_alphas(alphas, topic_id=temp_topic_id)

        # Persist NEW/UPDATE facts — the arbiter's decision doesn't store by itself in
        # production either (pipeline/runner.py does this); do the same here so a
        # multi-fact run's later dedup checks see the earlier facts, matching real use.
        for d in decisions:
            if d.decision in (DecisionType.NEW, DecisionType.UPDATE):
                d.alpha.topic_id = temp_topic_id
                arbiter.ledger.add_fact(d.alpha)

        brief = Briefer().generate(decisions, topic)
        brief = brief or "(V5: no NEW/UPDATE facts survived dedup to brief)"
        return brief, None
    except Exception as exc:
        return "", f"V5 pipeline error: {exc}"
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
        api_key = os.getenv("GOOGLE_API_KEY_DEV") or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", "")
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


def run_judge(topic: str, brief_v4: str, brief_v5: str, brief_reference: str) -> dict:
    """LLM judge: compare all three briefs, return structured scores + gaps."""
    try:
        from google import genai
        from google.genai import types
        api_key = os.getenv("GOOGLE_API_KEY_DEV") or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", "")
        client = genai.Client(api_key=api_key)
        prompt = JUDGE_PROMPT.format(
            topic=topic,
            date=datetime.date.today().isoformat(),
            brief_v4=brief_v4,
            brief_v5=brief_v5,
            brief_ref=brief_reference,
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
    gaps     = result.get("gaps_in_v5", [])
    fps      = result.get("false_positives_in_v5", [])
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
    print(f"  {'Axis':<18} {'V4':>6} {'V5':>6} {'Ref':>6}")
    print(f"  {'-'*38}")
    for ax in axes:
        v4 = scores.get(ax, {}).get("v4", "?")
        v5 = scores.get(ax, {}).get("v5", "?")
        r  = scores.get(ax, {}).get("reference", "?")
        flag = " <<<" if isinstance(v5, int) and isinstance(r, int) and v5 < r - 2 else ""
        print(f"  {ax:<18} {str(v4):>6} {str(v5):>6} {str(r):>6}{flag}")
    print(f"  {'-'*38}")
    t_v4  = _total(scores, "v4")
    t_v5  = _total(scores, "v5")
    t_ref = _total(scores, "reference")
    print(f"  {'TOTAL':<18} {t_v4:>6} {t_v5:>6} {t_ref:>6}")

    print(f"\n  VERDICT: {verdict}")

    if gaps:
        print(f"\n  GAPS IN V5 ({len(gaps)}):")
        for g in gaps:
            print(f"    - {g}")
    if fps:
        print(f"\n  FALSE POSITIVES IN V5 ({len(fps)}):")
        for fp in fps:
            print(f"    - {fp}")


def save_report(
    topic: str,
    brief_v4: str,
    brief_v5: str,
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
    gaps    = result.get("gaps_in_v5", [])
    fps     = result.get("false_positives_in_v5", [])
    verdict = result.get("verdict", "—")
    axes    = ["lede_quality", "completeness", "synthesis", "noise_level"]
    t_v4    = _total(scores, "v4")
    t_v5    = _total(scores, "v5")
    t_ref   = _total(scores, "reference")

    lines = [
        f"# Benchmark: {topic}",
        f"**Date:** {date_str}  |  **Models:** search/judge={SEARCH_MODEL}",
        "",
        "## Scores (V4 = old pipeline, V5 = Gemini Search + memory/dedup, "
        "Reference = simple unstructured Gemini ask)",
        "",
        f"| Axis | V4 | V5 | Reference |",
        f"|---|---|---|---|",
    ]
    for ax in axes:
        v4 = scores.get(ax, {}).get("v4", "?")
        v5 = scores.get(ax, {}).get("v5", "?")
        r  = scores.get(ax, {}).get("reference", "?")
        flag = " ⚠️" if isinstance(v5, int) and isinstance(r, int) and v5 < r - 2 else ""
        lines.append(f"| {ax}{flag} | {v4} | {v5} | {r} |")
    lines += [
        f"| **TOTAL** | **{t_v4}** | **{t_v5}** | **{t_ref}** |",
        "",
        f"**Verdict:** {verdict}",
        "",
    ]

    if gaps:
        lines += ["## Gaps in V5", ""]
        for g in gaps:
            lines.append(f"- {g}")
        lines.append("")

    if fps:
        lines += ["## False Positives in V5", ""]
        for fp in fps:
            lines.append(f"- {fp}")
        lines.append("")

    lines += [
        "## V4 Output (old pipeline)",
        "",
        "```",
        brief_v4 or "(empty)",
        "```",
        "",
        "## V5 Output (Gemini Search + memory/dedup)",
        "",
        "```",
        brief_v5 or "(empty)",
        "```",
        "",
        "## Reference Output (simple, unstructured Gemini Search ask)",
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
    """Run benchmark for one topic: V4 pipeline, V5 pipeline, and a simple Gemini
    Search ask, all in parallel, then judge all three. Returns judge result dict."""
    print(f"\n[BENCHMARK] Topic: '{topic}'")
    print("  Running V4 pipeline + V5 pipeline + simple Gemini Search in parallel...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        v4_future  = pool.submit(run_truebrief, topic)
        v5_future  = pool.submit(run_v5, topic)
        gem_future = pool.submit(run_gemini_search, topic)

        # A timed-out arm (e.g. V4's search dependencies quota-exhausted) is itself a
        # meaningful benchmark result, not a reason to crash the whole comparison —
        # report it as an error for that arm and keep going with whatever did finish.
        try:
            brief_v4, v4_err = v4_future.result(timeout=PIPELINE_TIMEOUT)
        except concurrent.futures.TimeoutError:
            brief_v4, v4_err = "", f"V4 pipeline did not finish within {PIPELINE_TIMEOUT}s (likely dead/quota-exhausted search dependencies)"
        try:
            brief_v5, v5_err = v5_future.result(timeout=PIPELINE_TIMEOUT)
        except concurrent.futures.TimeoutError:
            brief_v5, v5_err = "", f"V5 pipeline did not finish within {PIPELINE_TIMEOUT}s"
        try:
            brief_ref, ref_sources, gem_err = gem_future.result(timeout=60)
        except concurrent.futures.TimeoutError:
            brief_ref, ref_sources, gem_err = "", [], "Gemini Search did not finish within 60s"

    if v4_err:
        print(f"  [!] V4 pipeline failed: {v4_err}")
        brief_v4 = f"(V4 FAILED: {v4_err})"
    if v5_err:
        print(f"  [!] V5 pipeline failed: {v5_err}")
        brief_v5 = f"(V5 FAILED: {v5_err})"
    if gem_err:
        print(f"  [!] Gemini Search failed: {gem_err}")
        brief_ref = f"(Reference FAILED: {gem_err})"

    print("  Judging...")
    result = run_judge(topic, brief_v4, brief_v5, brief_ref)

    if "error" not in result:
        path = save_report(topic, brief_v4, brief_v5, brief_ref, ref_sources, result)
        result["_report_path"] = path
        print(f"  Report saved: {path}")

    return result, brief_v4, brief_v5, brief_ref, ref_sources


def main():
    parser = argparse.ArgumentParser(description="TrueBrief quality benchmark")
    parser.add_argument("topics", nargs="*", help="Topics to benchmark (default: preset list)")
    args = parser.parse_args()

    topics = args.topics if args.topics else DEFAULT_TOPICS

    all_results = []
    for topic in topics:
        result, brief_v4, brief_v5, brief_ref, ref_sources = benchmark_topic(topic)
        print_report(topic, result)
        all_results.append((topic, result))

    # Overall summary when multiple topics
    if len(all_results) > 1:
        print(f"\n{'='*60}")
        print("  OVERALL SUMMARY")
        print(f"{'='*60}")
        for topic, result in all_results:
            scores = result.get("scores", {})
            t_v4  = _total(scores, "v4")
            t_v5  = _total(scores, "v5")
            t_ref = _total(scores, "reference")
            winner = "V5" if t_v5 >= max(t_v4, t_ref) else ("V4" if t_v4 >= t_ref else "REF")
            print(f"  [{winner:<3}] {topic}: v4={t_v4} v5={t_v5} ref={t_ref}")


if __name__ == "__main__":
    main()
