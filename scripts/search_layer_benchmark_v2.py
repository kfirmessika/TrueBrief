#!/usr/bin/env python3
"""
scripts/search_layer_benchmark_v2.py

Surgical 9-test benchmark: Gemini Grounding vs Linkup vs Brave.
Tests real dimensions that matter for TrueBrief Alpha extraction.

Scoring is OBJECTIVE per-dimension rubric (not generic LLM vibes):
  - recency      (0-3): mentions today / this week with timestamps
  - numeric      (0-3): specific verifiable numbers present
  - fact_density (0-3): unique atomic facts per 100 words
  - source_qual  (0-3): real article URLs from named outlets (not generic)
  - noise        (0-3): low filler / padding ratio
  - hallucination_penalty: -3 if confident invented facts detected

Max per test: 15 pts.  Grand total: 135 pts.

Usage:
    python scripts/search_layer_benchmark_v2.py
    python scripts/search_layer_benchmark_v2.py --tests A1 B1 C1   # subset
    python scripts/search_layer_benchmark_v2.py --no-parallel

Output: docs/benchmarks/YYYY-MM-DD_search-layer-v2-<slug>.md
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

TODAY = datetime.date.today().isoformat()   # 2026-08-28
JUDGE_MODEL = "gemini-2.5-flash-lite"
CALL_TIMEOUT = 90

# ── Test suite ─────────────────────────────────────────────────────────────────

TESTS = [
    {
        "id": "A1",
        "dimension": "Recency — financial real-time data",
        "why": "Verifiable exact numbers. Who has today's BTC price and S&P level vs stale data?",
        "query": (
            f"What is Bitcoin's price right now on {TODAY}, what was its 24-hour high and low "
            "today, and what is the current S&P 500 level? Include specific numbers."
        ),
        "scoring_focus": "recency + numeric",
        "what_good_looks_like": "Today's date mentioned, specific USD price with cents, 24h high/low range",
        "what_failure_looks_like": "Price from days ago, no high/low, rounded to nearest thousand",
    },
    {
        "id": "A2",
        "dimension": "Recency — breaking geopolitical",
        "why": "Real ongoing topic. Who surfaces the most recent timestamp?",
        "query": (
            f"What is the most recent development in the Iran-US ceasefire situation as of {TODAY}? "
            "Include specific dates, names, and what changed in the last 48 hours."
        ),
        "scoring_focus": "recency + fact_density",
        "what_good_looks_like": "Mentions Aug 27-28 events specifically, named officials, specific terms",
        "what_failure_looks_like": "Generic background on Iran-US relations, no recent timestamps",
    },
    {
        "id": "B1",
        "dimension": "Numeric precision — economic data",
        "why": "CPI/PCE/jobs data is released on known dates. Exact numbers are verifiable.",
        "query": (
            "What was the most recent US inflation figure (CPI or PCE) released this month "
            "(August 2026)? Give the exact percentage, which index it was, and the release date."
        ),
        "scoring_focus": "numeric + source_qual",
        "what_good_looks_like": "Exact % to one decimal, correct index name, exact release date, BLS/Fed source",
        "what_failure_looks_like": "Vague 'inflation around X%', wrong month, no source",
    },
    {
        "id": "B2",
        "dimension": "Structured factual extraction — EU AI Act",
        "why": "Real regulatory document with exact deadlines. Tests who extracts specifics vs summaries.",
        "query": (
            "What are the specific enforcement deadlines and penalty amounts in the EU AI Act "
            "that came into effect in 2026? List exact dates and euro figures."
        ),
        "scoring_focus": "numeric + fact_density",
        "what_good_looks_like": "Specific dates (Aug 2, 2026 GPAI rules, etc.), exact fine tiers (€35M or 7% revenue), article numbers",
        "what_failure_looks_like": "General description of the Act without specific dates/amounts",
    },
    {
        "id": "C1",
        "dimension": "Synthesis quality — high-volume conflict topic",
        "why": "Gaza/ceasefire has massive news volume. Who extracts clean signal vs noise?",
        "query": (
            f"What is the current status of the Gaza ceasefire as of {TODAY}? "
            "List: (1) whether the ceasefire is holding, (2) the most recent violation or breakdown, "
            "(3) which phase of negotiations is active, (4) key sticking points."
        ),
        "scoring_focus": "fact_density + noise",
        "what_good_looks_like": "4 distinct structured facts, no repetition, no background filler",
        "what_failure_looks_like": "Background history of the conflict, vague 'tensions remain'",
    },
    {
        "id": "C2",
        "dimension": "Multi-hop synthesis",
        "why": "Requires chaining Fed → rates → tech stocks → AI demand. Tests reasoning depth.",
        "query": (
            "How did the Federal Reserve's most recent statement or action (August 2026) affect "
            "technology stock valuations, and what does that imply for AI chip demand and "
            "companies like Nvidia? Connect the chain of cause and effect explicitly."
        ),
        "scoring_focus": "fact_density + noise",
        "what_good_looks_like": "Explicit causal chain: Fed action → rate expectation → tech P/E → Nvidia/AMD → datacenter capex",
        "what_failure_looks_like": "Separate paragraphs about Fed and Nvidia with no causal connection",
    },
    {
        "id": "D1",
        "dimension": "Hallucination on obscure niche topic",
        "why": "Real but low-coverage topic. Does any provider invent confident fake details?",
        "query": (
            "What were the key outcomes of the Paraguay Senate debate on cryptocurrency "
            "regulation in August 2026? Include specific bill names, vote counts, and senators involved."
        ),
        "scoring_focus": "hallucination_penalty + source_qual",
        "what_good_looks_like": "Admits uncertainty or returns 'no specific information found' if nothing happened",
        "what_failure_looks_like": "Confident invented bill names, fake vote counts, non-existent senator names",
    },
    {
        "id": "E1",
        "dimension": "Source attribution quality",
        "why": "TrueBrief needs real source URLs for Alpha attribution. Who provides them?",
        "query": (
            "What are the 3 most significant AI industry developments from the past 7 days "
            "(August 21-28 2026)? For each, provide the source publication name and URL."
        ),
        "scoring_focus": "source_qual + fact_density",
        "what_good_looks_like": "3 distinct events, named outlets (Reuters/FT/TechCrunch), specific article URLs",
        "what_failure_looks_like": "No URLs, generic 'according to reports', homepage links only",
    },
    {
        "id": "F1",
        "dimension": "Paywall penetration — financial journalism",
        "why": "WSJ/FT coverage of M&A / earnings. Does any provider reach past the headline?",
        "query": (
            "According to Wall Street Journal or Financial Times reporting this week, what are "
            "the specific deal terms, valuations, or internal details of any major M&A transaction "
            "or corporate restructuring announced in the past 7 days?"
        ),
        "scoring_focus": "source_qual + fact_density",
        "what_good_looks_like": "Specific deal terms (price, structure, conditions), attributed to WSJ/FT body text, not just headline",
        "what_failure_looks_like": "Headline-level summary only, no deal structure specifics, no WSJ/FT attribution",
    },
]

TESTS_BY_ID = {t["id"]: t for t in TESTS}

# ── Collectors ─────────────────────────────────────────────────────────────────

@dataclass
class Result:
    provider: str
    test_id: str
    text: str = ""
    sources: list[dict] = field(default_factory=list)
    error: Optional[str] = None
    latency_s: float = 0.0


def run_gemini(query: str, test_id: str) -> Result:
    t0 = time.monotonic()
    try:
        from google import genai
        api_key = (
            os.getenv("GOOGLE_API_KEY_DEV")
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("GOOGLE_API_KEY_BACKUP") or ""
        )
        if not api_key:
            return Result("gemini", test_id, error="No GOOGLE_API_KEY set", latency_s=0)
        client = genai.Client(api_key=api_key)
        interaction = client.interactions.create(
            model="gemini-2.5-flash-lite",
            input=query,
            tools=[{"type": "google_search"}],
        )
        text = (interaction.output_text or "").strip()
        sources = []
        for step in (interaction.steps or []):
            if getattr(step, "type", "") == "google_search_call":
                d = step.to_dict() if hasattr(step, "to_dict") else {}
                for q in (d.get("arguments") or {}).get("queries", []):
                    sources.append({"url": f"search:{q}", "title": q})
        return Result("gemini", test_id, text=text, sources=sources, latency_s=time.monotonic()-t0)
    except Exception as exc:
        return Result("gemini", test_id, error=str(exc), latency_s=time.monotonic()-t0)


def run_linkup(query: str, test_id: str) -> Result:
    t0 = time.monotonic()
    api_key = os.getenv("LINKUP_API_KEY", "")
    if not api_key:
        return Result("linkup", test_id, error="LINKUP_API_KEY not set", latency_s=0)
    try:
        import httpx
        week_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        resp = httpx.post(
            "https://api.linkup.so/v1/search",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "q": query,
                "depth": "standard",
                "outputType": "sourcedAnswer",
                "maxResults": 15,
                "fromDate": week_ago,
                "toDate": TODAY,
            },
            timeout=CALL_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        answer = data.get("answer", "") or ""
        raw_sources = data.get("sources", []) or []
        sources = [{"url": s.get("url", ""), "title": s.get("title", "")}
                   for s in raw_sources if s.get("url")]
        return Result("linkup", test_id, text=answer, sources=sources, latency_s=time.monotonic()-t0)
    except Exception as exc:
        return Result("linkup", test_id, error=str(exc), latency_s=time.monotonic()-t0)


def run_brave(query: str, test_id: str) -> Result:
    t0 = time.monotonic()
    api_key = os.getenv("BRAVE_API_KEY", "")
    if not api_key:
        return Result("brave", test_id, error="BRAVE_API_KEY not set", latency_s=0)
    try:
        import httpx, re as _re
        from datetime import datetime as _dt, timedelta as _td

        today_d = datetime.date.today()
        week_ago = today_d - datetime.timedelta(days=7)
        freshness = f"{week_ago.isoformat()}to{today_d.isoformat()}"

        resp = httpx.get(
            "https://api.search.brave.com/res/v1/news/search",
            headers={"X-Subscription-Token": api_key, "Accept": "application/json", "Accept-Encoding": "gzip"},
            params={"q": query, "count": 20, "freshness": freshness,
                    "country": "US", "search_lang": "en",
                    "text_decorations": "false", "extra_snippets": "true"},
            timeout=CALL_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        def _age(age_str: str) -> str:
            if not age_str:
                return "?"
            now = _dt.utcnow()
            m = _re.search(r'(\d+)\s+(minute|hour|day|week)', age_str.lower())
            if not m:
                return "?"
            n, unit = int(m.group(1)), m.group(2)
            delta = {"minute": _td(minutes=n), "hour": _td(hours=n),
                     "day": _td(days=n), "week": _td(weeks=n)}.get(unit)
            return (now - delta).date().isoformat() if delta else "?"

        results = data.get("results", [])
        lines, sources = [], []
        for r in results:
            url = r.get("url", "")
            title = r.get("title", "")
            desc = r.get("description", "")
            age = _age(r.get("age", ""))
            extras = " | ".join(r.get("extra_snippets", [])[:2])
            lines.append(f"[{age}] {title}: {desc}" + (f" {extras}" if extras else ""))
            if url:
                sources.append({"url": url, "title": title})

        return Result("brave", test_id, text="\n".join(lines), sources=sources, latency_s=time.monotonic()-t0)
    except Exception as exc:
        return Result("brave", test_id, error=str(exc), latency_s=time.monotonic()-t0)


# ── Judge ──────────────────────────────────────────────────────────────────────

JUDGE_PROMPT = """You are an objective benchmark judge scoring 3 search API responses.
Your scores must be based on what is actually IN each response, not assumed quality.
Today's date: {today}

QUERY: {query}
DIMENSION BEING TESTED: {dimension}
SCORING FOCUS: {scoring_focus}
WHAT A GOOD RESPONSE LOOKS LIKE: {good}
WHAT FAILURE LOOKS LIKE: {failure}

=== GEMINI RESPONSE ===
{gemini}

=== LINKUP RESPONSE ===
{linkup}

=== BRAVE RESPONSE ===
{brave}

Score each provider 0-3 on each axis. Be STRICT and LITERAL — score what is actually present, not what you infer.

SCORING AXES:
- recency (0-3): 3=mentions today {today} or yesterday with specific dates, 2=this week with dates, 1=recent but vague, 0=no dates or clearly stale
- numeric (0-3): 3=exact verifiable number (price to cents, %, date), 2=approximate number, 1=number mentioned without precision, 0=no numbers or clearly wrong
- fact_density (0-3): 3=5+ unique atomic facts in <300 words, 2=3-4 facts, 1=1-2 facts or very long padding, 0=no facts or pure filler
- source_qual (0-3): 3=specific article URLs from named outlets, 2=named outlets but no URLs, 1=generic domains or 'according to reports', 0=no sources
- noise (0-3): 3=every sentence is a new fact, 2=minor padding, 1=significant background filler, 0=mostly noise
- hallucination_penalty: -3 if provider confidently states specific facts (names, numbers, dates) that are almost certainly invented rather than admitting uncertainty. 0 otherwise.

Respond ONLY with valid JSON (no markdown fences):
{{
  "gemini":  {{"recency": N, "numeric": N, "fact_density": N, "source_qual": N, "noise": N, "hallucination_penalty": N, "notes": "one sentence"}},
  "linkup":  {{"recency": N, "numeric": N, "fact_density": N, "source_qual": N, "noise": N, "hallucination_penalty": N, "notes": "one sentence"}},
  "brave":   {{"recency": N, "numeric": N, "fact_density": N, "source_qual": N, "noise": N, "hallucination_penalty": N, "notes": "one sentence"}},
  "dimension_winner": "gemini|linkup|brave|tie",
  "key_finding": "one sentence about what this test revealed about the differences"
}}
"""


def _score_total(s: dict) -> int:
    axes = ["recency", "numeric", "fact_density", "source_qual", "noise"]
    return sum(s.get(a, 0) for a in axes) + s.get("hallucination_penalty", 0)


def run_judge(test: dict, results: dict[str, Result]) -> dict:
    try:
        from google import genai
        from google.genai import types
        api_key = (
            os.getenv("GOOGLE_API_KEY_DEV")
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("GOOGLE_API_KEY_BACKUP") or ""
        )
        client = genai.Client(api_key=api_key)

        def _fmt(r: Result) -> str:
            if r.error:
                return f"(FAILED: {r.error})"
            sources_txt = ""
            if r.sources:
                real_urls = [s for s in r.sources if not s["url"].startswith("search:")]
                if real_urls:
                    sources_txt = "\nSOURCES: " + ", ".join(
                        f"{s['title']} ({s['url']})" for s in real_urls[:5]
                    )
            return (r.text or "(empty)") + sources_txt

        prompt = JUDGE_PROMPT.format(
            today=TODAY,
            query=test["query"],
            dimension=test["dimension"],
            scoring_focus=test["scoring_focus"],
            good=test["what_good_looks_like"],
            failure=test["what_failure_looks_like"],
            gemini=_fmt(results["gemini"]),
            linkup=_fmt(results["linkup"]),
            brave=_fmt(results["brave"]),
        )
        response = client.models.generate_content(
            model=JUDGE_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        raw = response.text.strip()
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return {"error": f"No JSON: {raw[:200]}"}
        return json.loads(m.group(0))
    except Exception as exc:
        return {"error": str(exc)}


# ── Orchestrator ───────────────────────────────────────────────────────────────

def run_test(test: dict, parallel: bool = True) -> tuple[dict[str, Result], dict]:
    tid = test["id"]
    query = test["query"]
    print(f"\n  [{tid}] {test['dimension']}")

    if parallel:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            fg = pool.submit(run_gemini, query, tid)
            fl = pool.submit(run_linkup, query, tid)
            fb = pool.submit(run_brave, query, tid)
            try: gemini = fg.result(timeout=CALL_TIMEOUT)
            except: gemini = Result("gemini", tid, error="timeout")
            try: linkup = fl.result(timeout=CALL_TIMEOUT)
            except: linkup = Result("linkup", tid, error="timeout")
            try: brave = fb.result(timeout=CALL_TIMEOUT)
            except: brave = Result("brave", tid, error="timeout")
    else:
        gemini = run_gemini(query, tid)
        linkup = run_linkup(query, tid)
        brave = run_brave(query, tid)

    results = {"gemini": gemini, "linkup": linkup, "brave": brave}

    for name, r in results.items():
        if r.error:
            print(f"       {name}: ERROR — {r.error[:80]}")
        else:
            print(f"       {name}: {r.latency_s:.1f}s  {len(r.sources)} sources  {len(r.text)} chars")

    judgment = run_judge(test, results)
    return results, judgment


# ── Report ─────────────────────────────────────────────────────────────────────

AXES = ["recency", "numeric", "fact_density", "source_qual", "noise", "hallucination_penalty"]
PROVIDERS = ["gemini", "linkup", "brave"]


def print_scorecard(all_results: list[tuple]) -> None:
    print(f"\n{'='*70}")
    print("  DETAILED SCORECARD")
    print(f"{'='*70}")
    print(f"  {'Test':<6} {'Dimension':<35} {'Gem':>5} {'Lnk':>5} {'Bra':>5}  Winner")
    print(f"  {'-'*68}")

    totals = {p: 0 for p in PROVIDERS}
    for test, _, judgment in all_results:
        scores = {p: _score_total(judgment.get(p, {})) for p in PROVIDERS}
        winner = judgment.get("dimension_winner", "?")
        for p in PROVIDERS:
            totals[p] += scores[p]
        g, l, b = scores["gemini"], scores["linkup"], scores["brave"]
        dim = test["dimension"][:33]
        print(f"  {test['id']:<6} {dim:<35} {g:>5} {l:>5} {b:>5}  {winner}")

    print(f"  {'-'*68}")
    print(f"  {'TOTAL':<41} {totals['gemini']:>5} {totals['linkup']:>5} {totals['brave']:>5}")

    print(f"\n  {'Test':<6} {'Key Finding'}")
    print(f"  {'-'*68}")
    for test, _, judgment in all_results:
        finding = judgment.get("key_finding", "—")[:65]
        print(f"  {test['id']:<6} {finding}")

    print(f"\n  Cost/call: Gemini ~$0.014  Linkup ~$0.006  Brave ~$0.005")
    print(f"  Max possible score per provider: {15 * len(all_results)}")


def save_report(all_results: list[tuple]) -> str:
    date_str = datetime.date.today().isoformat()
    path = os.path.join(ROOT, "docs", "benchmarks", f"{date_str}_search-layer-v2-surgical.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)

    totals = {p: 0 for p in PROVIDERS}
    for _, _, judgment in all_results:
        for p in PROVIDERS:
            totals[p] += _score_total(judgment.get(p, {}))

    lines = [
        f"# Search Layer Benchmark v2 — Surgical",
        f"**Date:** {date_str}  |  **Tests:** {len(all_results)}  |  **Max score:** {15 * len(all_results)} per provider",
        "",
        "## Summary Scorecard",
        "",
        f"| Test | Dimension | Gemini | Linkup | Brave | Winner |",
        f"|---|---|---|---|---|---|",
    ]
    for test, _, judgment in all_results:
        scores = {p: _score_total(judgment.get(p, {})) for p in PROVIDERS}
        winner = judgment.get("dimension_winner", "?")
        lines.append(f"| {test['id']} | {test['dimension']} | {scores['gemini']} | {scores['linkup']} | {scores['brave']} | **{winner}** |")
    lines += [
        f"| **TOTAL** | | **{totals['gemini']}** | **{totals['linkup']}** | **{totals['brave']}** | |",
        "",
        f"| | Gemini | Linkup | Brave |",
        f"|---|---|---|---|",
        f"| Cost/call | ~$0.014 | ~$0.006 | ~$0.005 |",
        "",
        "## Per-Test Results",
        "",
    ]

    for test, results, judgment in all_results:
        lines += [
            f"### [{test['id']}] {test['dimension']}",
            f"**Query:** {test['query']}",
            f"**Scoring focus:** {test['scoring_focus']}",
            "",
            f"| Axis | Gemini | Linkup | Brave |",
            f"|---|---|---|---|",
        ]
        for ax in AXES:
            g = judgment.get("gemini", {}).get(ax, "?")
            l = judgment.get("linkup", {}).get(ax, "?")
            b = judgment.get("brave", {}).get(ax, "?")
            lines.append(f"| {ax} | {g} | {l} | {b} |")
        scores = {p: _score_total(judgment.get(p, {})) for p in PROVIDERS}
        lines += [
            f"| **TOTAL** | **{scores['gemini']}** | **{scores['linkup']}** | **{scores['brave']}** |",
            "",
            f"**Winner:** {judgment.get('dimension_winner', '?')}",
            f"**Key finding:** {judgment.get('key_finding', '—')}",
            "",
            f"**Gemini notes:** {judgment.get('gemini', {}).get('notes', '—')}",
            f"**Linkup notes:** {judgment.get('linkup', {}).get('notes', '—')}",
            f"**Brave notes:** {judgment.get('brave', {}).get('notes', '—')}",
            "",
        ]
        for name in PROVIDERS:
            r = results[name]
            label = name.capitalize()
            lines.append(f"<details><summary>{label} raw response ({len(r.text)} chars, {r.latency_s:.1f}s)</summary>")
            lines.append("")
            if r.error:
                lines.append(f"ERROR: {r.error}")
            else:
                lines.append("```")
                lines.append(r.text[:2000] + ("..." if len(r.text) > 2000 else ""))
                lines.append("```")
                if r.sources:
                    real = [s for s in r.sources if not s["url"].startswith("search:")]
                    if real:
                        lines.append(f"\nSources: " + ", ".join(f"[{s['title']}]({s['url']})" for s in real[:8]))
            lines.append("</details>")
            lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tests", nargs="*", help="Test IDs to run (e.g. A1 B1). Default: all")
    parser.add_argument("--no-parallel", action="store_true")
    args = parser.parse_args()

    selected = [TESTS_BY_ID[t] for t in args.tests] if args.tests else TESTS
    parallel = not args.no_parallel

    print(f"\nSearch Layer Benchmark v2 — {TODAY}")
    print(f"Running {len(selected)} tests x 3 providers + {len(selected)} judge calls")
    print(f"Estimated API calls: {len(selected) * 3} search + {len(selected)} judge = {len(selected) * 4} total")

    all_results = []
    for test in selected:
        results, judgment = run_test(test, parallel=parallel)
        if "error" in judgment:
            print(f"       JUDGE ERROR: {judgment['error'][:100]}")
        all_results.append((test, results, judgment))

    print_scorecard(all_results)
    path = save_report(all_results)
    print(f"\n  Report: {path}")


if __name__ == "__main__":
    main()
