#!/usr/bin/env python3
"""
scripts/search_layer_benchmark.py

3-way benchmark: Gemini Grounding vs Linkup vs Brave — as the V5 search layer.

Runs each collector directly against the same topics, judges all three outputs
with a Gemini LLM judge, and writes a Markdown report to docs/benchmarks/.
Does NOT touch the production pipeline or modify quality_benchmark.py.

Usage:
    python scripts/search_layer_benchmark.py
    python scripts/search_layer_benchmark.py "Iran ceasefire" "AI EU regulation"
    python scripts/search_layer_benchmark.py --no-parallel   # sequential, easier to debug

Output:
    • Console: score table per topic
    • docs/benchmarks/YYYY-MM-DD_search-layer-<slug>.md
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import time
import concurrent.futures
from dataclasses import dataclass, field
from typing import Optional

# ── bootstrap ──────────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

# ── config ─────────────────────────────────────────────────────────────────────
JUDGE_MODEL  = "gemini-2.5-flash-lite"
CALL_TIMEOUT = 60   # seconds per collector call

DEFAULT_TOPICS = [
    "Iran war ceasefire negotiations",
    "AI regulation EU policy",
    "Bitcoin price movement",
]

# Cost per call (USD) — for the report table
COSTS = {
    "gemini":  0.014,   # estimated: 2 calls (grounded search + extract), flash-lite pricing
    "linkup":  0.006,   # standard depth + sourcedAnswer
    "brave":   0.005,   # /news/search, Search Plan
}


# ── result container ───────────────────────────────────────────────────────────

@dataclass
class CollectorResult:
    name: str
    text: str = ""             # synthesized answer / article list for the judge
    sources: list[dict] = field(default_factory=list)   # [{url, title}]
    error: Optional[str] = None
    latency_s: float = 0.0


# ── collectors ─────────────────────────────────────────────────────────────────

def run_gemini(topic: str) -> CollectorResult:
    """Gemini Search via Interactions API — uses a different quota pool than
    models.generate_content grounding (no structured grounding_chunks here,
    but sufficient for benchmarking the text output quality).
    Production GeminiSearchCollector uses models.generate_content for real source URLs.
    """
    t0 = time.monotonic()
    try:
        from google import genai

        api_key = (
            os.getenv("GOOGLE_API_KEY_DEV")
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("GOOGLE_API_KEY_BACKUP")
            or ""
        )
        if not api_key:
            return CollectorResult("gemini", error="No GOOGLE_API_KEY set", latency_s=time.monotonic()-t0)

        client = genai.Client(api_key=api_key)
        today = datetime.date.today().isoformat()
        interaction = client.interactions.create(
            model="gemini-2.5-flash-lite",
            input=(
                f"Give me the latest news about '{topic}' as of today, {today}. "
                "Maximum signal-to-noise: start with the single most important CURRENT "
                "development, then list the 4-6 most significant other facts. "
                "Be specific — include dates, numbers, names. No background filler. No prediction."
            ),
            tools=[{"type": "google_search"}],
        )
        text = (interaction.output_text or "").strip()
        # Extract query terms used (from google_search_call steps) as lightweight source info
        sources = []
        for step in (interaction.steps or []):
            if getattr(step, "type", "") == "google_search_call":
                d = step.to_dict() if hasattr(step, "to_dict") else {}
                for q in (d.get("arguments") or {}).get("queries", []):
                    sources.append({"url": f"google_search:{q}", "title": q})
        tokens = getattr(interaction.usage, "total_tokens", 0) if interaction.usage else 0
        return CollectorResult("gemini", text=text, sources=sources, latency_s=time.monotonic()-t0)
    except Exception as exc:
        return CollectorResult("gemini", error=str(exc), latency_s=time.monotonic()-t0)


def run_linkup(topic: str) -> CollectorResult:
    """Linkup standard search — sourcedAnswer output."""
    t0 = time.monotonic()
    api_key = os.getenv("LINKUP_API_KEY", "")
    if not api_key:
        return CollectorResult("linkup", error="LINKUP_API_KEY not set", latency_s=time.monotonic()-t0)

    try:
        import httpx

        today = datetime.date.today().isoformat()
        week_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()

        resp = httpx.post(
            "https://api.linkup.so/v1/search",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "q": f"Latest news: {topic}",
                "depth": "standard",
                "outputType": "sourcedAnswer",
                "maxResults": 15,
                "fromDate": week_ago,
                "toDate": today,
            },
            timeout=CALL_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        answer = data.get("answer", "") or ""
        raw_sources = data.get("sources", []) or []
        sources = [{"url": s.get("url", ""), "title": s.get("title", s.get("url", ""))}
                   for s in raw_sources if s.get("url")]
        return CollectorResult("linkup", text=answer, sources=sources, latency_s=time.monotonic()-t0)
    except Exception as exc:
        return CollectorResult("linkup", error=str(exc), latency_s=time.monotonic()-t0)


def run_brave(topic: str) -> CollectorResult:
    """Brave News Search — returns article list, no LLM synthesis."""
    t0 = time.monotonic()
    api_key = os.getenv("BRAVE_API_KEY", "")
    if not api_key:
        return CollectorResult("brave", error="BRAVE_API_KEY not set", latency_s=time.monotonic()-t0)

    try:
        import httpx
        import re as _re
        from datetime import datetime as _dt, timedelta as _td

        today = datetime.date.today()
        week_ago = today - datetime.timedelta(days=7)
        freshness = f"{week_ago.isoformat()}to{today.isoformat()}"

        resp = httpx.get(
            "https://api.search.brave.com/res/v1/news/search",
            headers={
                "X-Subscription-Token": api_key,
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
            },
            params={
                "q": topic,
                "count": 20,
                "freshness": freshness,
                "country": "US",
                "search_lang": "en",
                "text_decorations": "false",
                "extra_snippets": "true",
            },
            timeout=CALL_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        if not results:
            return CollectorResult("brave", text="(no results returned)", latency_s=time.monotonic()-t0)

        def _parse_age(age_str: str):
            if not age_str:
                return None
            now = _dt.utcnow()
            m = _re.search(r'(\d+)\s+(minute|hour|day|week)', age_str.lower())
            if not m:
                return None
            n, unit = int(m.group(1)), m.group(2)
            delta = {"minute": _td(minutes=n), "hour": _td(hours=n),
                     "day": _td(days=n), "week": _td(weeks=n)}.get(unit)
            return (now - delta).date().isoformat() if delta else None

        lines = []
        sources = []
        for r in results:
            url = r.get("url", "")
            title = r.get("title", "")
            desc = r.get("description", "")
            age = _parse_age(r.get("age", "")) or "?"
            lines.append(f"- [{age}] {title}: {desc}")
            if url:
                sources.append({"url": url, "title": title})

        return CollectorResult("brave", text="\n".join(lines), sources=sources, latency_s=time.monotonic()-t0)
    except Exception as exc:
        return CollectorResult("brave", error=str(exc), latency_s=time.monotonic()-t0)


# ── judge ──────────────────────────────────────────────────────────────────────

JUDGE_PROMPT = """You are a news intelligence quality judge evaluating THREE search layer candidates.
All three were given the same topic and searched the same live web.

TOPIC: {topic}
DATE: {date}

=== GEMINI GROUNDING (current production — 2-call design: grounded search + structured extract) ===
{brief_gemini}

=== LINKUP (standard depth, sourcedAnswer output — $0.006/call) ===
{brief_linkup}

=== BRAVE NEWS SEARCH (news/search endpoint, no LLM synthesis — $0.005/call) ===
{brief_brave}

Score EACH on four axes (0–10):
  lede_quality  — does it immediately surface the most important current development?
  completeness  — does it cover all key stories, or miss major ones?
  source_quality — are citations real, specific, and verifiable (not generic homepages)?
  noise_level   — free of repetition, old news, off-topic items? (10=clean, 0=noisy)

Also provide:
  gaps_vs_gemini  — facts Gemini had that Linkup/Brave missed (max 5)
  gaps_vs_linkup  — facts Linkup had that Gemini/Brave missed (max 5)
  gaps_vs_brave   — facts Brave had that Gemini/Linkup missed (max 5)
  paywall_notes   — any evidence of paywall access differences between the three
  verdict         — one paragraph: rank the three plainly for use as a TrueBrief
                    news-collection layer, and name the key reason. Consider cost-per-call
                    and whether the output maps cleanly to structured Alpha extraction.

Respond ONLY with valid JSON (no markdown fences):
{{
  "scores": {{
    "lede_quality":   {{"gemini": N, "linkup": N, "brave": N}},
    "completeness":   {{"gemini": N, "linkup": N, "brave": N}},
    "source_quality": {{"gemini": N, "linkup": N, "brave": N}},
    "noise_level":    {{"gemini": N, "linkup": N, "brave": N}}
  }},
  "gaps_vs_gemini": ["..."],
  "gaps_vs_linkup": ["..."],
  "gaps_vs_brave":  ["..."],
  "paywall_notes": "...",
  "verdict": "..."
}}
"""


def run_judge(topic: str, gemini: CollectorResult, linkup: CollectorResult, brave: CollectorResult) -> dict:
    try:
        from google import genai
        from google.genai import types

        # Try dev key first (keeps prod quota clean), then primary, then backup
        api_key = (
            os.getenv("GOOGLE_API_KEY_DEV")
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("GOOGLE_API_KEY_BACKUP")
            or ""
        )
        client = genai.Client(api_key=api_key)

        def _fmt(r: CollectorResult) -> str:
            if r.error:
                return f"(FAILED: {r.error})"
            return r.text or "(empty)"

        prompt = JUDGE_PROMPT.format(
            topic=topic,
            date=datetime.date.today().isoformat(),
            brief_gemini=_fmt(gemini),
            brief_linkup=_fmt(linkup),
            brief_brave=_fmt(brave),
        )
        response = client.models.generate_content(
            model=JUDGE_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        raw = response.text.strip()
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return {"error": f"No JSON in judge response: {raw[:200]}"}
        return json.loads(m.group(0))
    except Exception as exc:
        return {"error": str(exc)}


# ── formatting ─────────────────────────────────────────────────────────────────

AXES = ["lede_quality", "completeness", "source_quality", "noise_level"]
COLLECTORS = ["gemini", "linkup", "brave"]


def _total(scores: dict, key: str) -> int:
    return sum(scores.get(ax, {}).get(key, 0) for ax in AXES)


def print_result(topic: str, results: dict[str, CollectorResult], judgment: dict) -> None:
    scores  = judgment.get("scores", {})
    verdict = judgment.get("verdict", "—")
    error   = judgment.get("error")

    print(f"\n{'='*65}")
    print(f"  SEARCH LAYER BENCHMARK: {topic}")
    print(f"  {datetime.date.today().isoformat()}")
    print(f"{'='*65}")

    if error:
        print(f"  [JUDGE ERROR] {error}")
        return

    # Latency + error summary
    for name in COLLECTORS:
        r = results[name]
        status = f"ERROR: {r.error}" if r.error else f"{r.latency_s:.1f}s"
        print(f"  {name:<8}  latency={status}  sources={len(r.sources)}")

    print()
    print(f"  {'Axis':<18} {'Gemini':>8} {'Linkup':>8} {'Brave':>8}")
    print(f"  {'-'*46}")
    for ax in AXES:
        g = scores.get(ax, {}).get("gemini", "?")
        l = scores.get(ax, {}).get("linkup", "?")
        b = scores.get(ax, {}).get("brave", "?")
        print(f"  {ax:<18} {str(g):>8} {str(l):>8} {str(b):>8}")
    print(f"  {'-'*46}")
    tg = _total(scores, "gemini")
    tl = _total(scores, "linkup")
    tb = _total(scores, "brave")
    winner = max(zip([tg, tl, tb], ["gemini", "linkup", "brave"]))[1].upper()
    print(f"  {'TOTAL':<18} {tg:>8} {tl:>8} {tb:>8}   <- winner: {winner}")

    print(f"\n  Cost/call:  Gemini ~${COSTS['gemini']:.3f}  Linkup ~${COSTS['linkup']:.3f}  Brave ~${COSTS['brave']:.3f}")
    print(f"\n  VERDICT: {verdict}")


def save_report(
    topic: str,
    results: dict[str, CollectorResult],
    judgment: dict,
) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    date_str = datetime.date.today().isoformat()
    filename = f"{date_str}_search-layer-{slug}.md"
    out_dir = os.path.join(ROOT, "docs", "benchmarks")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)

    scores  = judgment.get("scores", {})
    verdict = judgment.get("verdict", "—")
    tg = _total(scores, "gemini")
    tl = _total(scores, "linkup")
    tb = _total(scores, "brave")

    def _status(r: CollectorResult) -> str:
        if r.error:
            return f"❌ FAILED ({r.error})"
        return f"✅ {r.latency_s:.1f}s  |  {len(r.sources)} sources"

    lines = [
        f"# Search Layer Benchmark: {topic}",
        f"**Date:** {date_str}  |  **Judge model:** {JUDGE_MODEL}",
        "",
        "## Scores",
        "",
        f"| Axis | Gemini Grounding | Linkup | Brave News |",
        f"|---|---|---|---|",
    ]
    for ax in AXES:
        g = scores.get(ax, {}).get("gemini", "?")
        l = scores.get(ax, {}).get("linkup", "?")
        b = scores.get(ax, {}).get("brave", "?")
        lines.append(f"| {ax} | {g} | {l} | {b} |")
    lines += [
        f"| **TOTAL** | **{tg}** | **{tl}** | **{tb}** |",
        "",
        "## Metadata",
        "",
        f"| | Gemini Grounding | Linkup | Brave News |",
        f"|---|---|---|---|",
        f"| Cost/call | ~${COSTS['gemini']:.3f} | ~${COSTS['linkup']:.3f} | ~${COSTS['brave']:.3f} |",
        f"| Latency | {results['gemini'].latency_s:.1f}s | {results['linkup'].latency_s:.1f}s | {results['brave'].latency_s:.1f}s |",
        f"| Sources returned | {len(results['gemini'].sources)} | {len(results['linkup'].sources)} | {len(results['brave'].sources)} |",
        f"| Status | {_status(results['gemini'])} | {_status(results['linkup'])} | {_status(results['brave'])} |",
        "",
        f"**Verdict:** {verdict}",
        "",
    ]

    paywall = judgment.get("paywall_notes", "")
    if paywall:
        lines += [f"**Paywall notes:** {paywall}", ""]

    for gap_key, label in [
        ("gaps_vs_gemini", "Facts Gemini had that others missed"),
        ("gaps_vs_linkup", "Facts Linkup had that others missed"),
        ("gaps_vs_brave",  "Facts Brave had that others missed"),
    ]:
        gaps = judgment.get(gap_key, [])
        if gaps:
            lines += [f"### {label}", ""]
            for g in gaps:
                lines.append(f"- {g}")
            lines.append("")

    for name in COLLECTORS:
        r = results[name]
        label = {"gemini": "Gemini Grounding (V5 production)", "linkup": "Linkup", "brave": "Brave News Search"}[name]
        lines += [f"## {label} Output", ""]
        if r.error:
            lines.append(f"**ERROR:** {r.error}")
        else:
            lines += ["```", r.text or "(empty)", "```"]
        lines.append("")
        if r.sources:
            lines += [f"**Sources ({len(r.sources)}):**", ""]
            for s in r.sources[:20]:
                lines.append(f"- [{s.get('title', s['url'])}]({s['url']})")
            lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


# ── orchestrator ───────────────────────────────────────────────────────────────

def benchmark_topic(topic: str, parallel: bool = True) -> tuple[dict[str, CollectorResult], dict]:
    print(f"\n[BENCHMARK] '{topic}'")
    print(f"  Running Gemini + Linkup + Brave {'in parallel' if parallel else 'sequentially'}...")

    if parallel:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            fut_g = pool.submit(run_gemini, topic)
            fut_l = pool.submit(run_linkup, topic)
            fut_b = pool.submit(run_brave,  topic)
            try:
                gemini = fut_g.result(timeout=CALL_TIMEOUT)
            except concurrent.futures.TimeoutError:
                gemini = CollectorResult("gemini", error=f"Timed out after {CALL_TIMEOUT}s")
            try:
                linkup = fut_l.result(timeout=CALL_TIMEOUT)
            except concurrent.futures.TimeoutError:
                linkup = CollectorResult("linkup", error=f"Timed out after {CALL_TIMEOUT}s")
            try:
                brave = fut_b.result(timeout=CALL_TIMEOUT)
            except concurrent.futures.TimeoutError:
                brave = CollectorResult("brave", error=f"Timed out after {CALL_TIMEOUT}s")
    else:
        gemini = run_gemini(topic)
        linkup = run_linkup(topic)
        brave  = run_brave(topic)

    for r in [gemini, linkup, brave]:
        if r.error:
            print(f"  [!] {r.name}: {r.error}")
        else:
            print(f"  [ok] {r.name}: {r.latency_s:.1f}s, {len(r.sources)} sources")

    print("  Judging...")
    judgment = run_judge(topic, gemini, linkup, brave)

    results = {"gemini": gemini, "linkup": linkup, "brave": brave}

    if "error" not in judgment:
        path = save_report(topic, results, judgment)
        judgment["_report_path"] = path
        print(f"  Report: {path}")

    return results, judgment


def main() -> None:
    parser = argparse.ArgumentParser(description="Search layer benchmark: Gemini vs Linkup vs Brave")
    parser.add_argument("topics", nargs="*", help="Topics to benchmark (default: preset list)")
    parser.add_argument("--no-parallel", action="store_true", help="Run collectors sequentially (easier to debug)")
    args = parser.parse_args()

    topics = args.topics or DEFAULT_TOPICS
    parallel = not args.no_parallel

    all_runs: list[tuple[str, dict[str, CollectorResult], dict]] = []
    for topic in topics:
        results, judgment = benchmark_topic(topic, parallel=parallel)
        print_result(topic, results, judgment)
        all_runs.append((topic, results, judgment))

    if len(all_runs) > 1:
        print(f"\n{'='*65}")
        print("  OVERALL SUMMARY")
        print(f"{'='*65}")
        print(f"  {'Topic':<35} {'Gemini':>7} {'Linkup':>7} {'Brave':>7}  Winner")
        print(f"  {'-'*63}")
        for topic, _, judgment in all_runs:
            scores = judgment.get("scores", {})
            tg = _total(scores, "gemini")
            tl = _total(scores, "linkup")
            tb = _total(scores, "brave")
            winner = max(zip([tg, tl, tb], ["GEMINI", "LINKUP", "BRAVE"]))[1]
            short = topic[:33] + ".." if len(topic) > 35 else topic
            print(f"  {short:<35} {tg:>7} {tl:>7} {tb:>7}  {winner}")

        print()
        # Cost comparison footer
        print(f"  Cost per call:  Gemini ~${COSTS['gemini']:.3f}  "
              f"Linkup ~${COSTS['linkup']:.3f}  Brave ~${COSTS['brave']:.3f}")


if __name__ == "__main__":
    main()
