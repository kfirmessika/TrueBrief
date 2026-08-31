#!/usr/bin/env python3
"""
scripts/search_layer_benchmark_v3.py — Pipeline-level search layer comparison

Fair comparison: all 3 providers are run through the SAME two-call extraction
pipeline that GeminiSearchCollector uses in production, then judged on the
quality of the resulting Alpha objects — not on raw API output.

Pipeline for each provider:
  1. COLLECT  — provider-specific (Gemini grounding / Linkup sourcedAnswer / Brave web summary)
  2. EXTRACT  — SAME call for all 3: build_gemini_extract_prompt -> call() -> _parse_facts()
  3. JUDGE    — score the resulting Alpha list on Alpha-fitness dimensions

Nothing is saved to the database. No dedup step.

Usage:
    python scripts/search_layer_benchmark_v3.py
    python scripts/search_layer_benchmark_v3.py --topics "Gaza ceasefire" "Fed rate decision"
    python scripts/search_layer_benchmark_v3.py --no-parallel

Output: docs/benchmarks/YYYY-MM-DD_search-layer-v3-pipeline.md
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

TODAY = datetime.date.today().isoformat()
TODAY_DT = datetime.datetime.now()
WEEK_AGO = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
CALL_TIMEOUT = 120
JUDGE_MODEL = "qwen/qwen3.8-27b"  # Groq — Gemini quota exhausted

DEFAULT_TOPICS = [
    "Iran US ceasefire Strait of Hormuz",
    "Federal Reserve interest rate decision August 2026",
    "EU AI Act enforcement 2026",
    "Bitcoin price August 2026",
    "Gaza ceasefire negotiations",
]

# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class CollectResult:
    provider: str
    topic: str
    # The prose text passed to the extract step
    prose: str = ""
    # Source legend: "[0] Reuters — https://...\n[1] ..."
    source_legend: str = ""
    # For Gemini: the cited text (with [N] markers). For others: prose without markers.
    cited_text: str = ""
    error: Optional[str] = None
    latency_s: float = 0.0
    n_real_sources: int = 0


@dataclass
class AlphaResult:
    alpha_text: str
    event_date: str
    event_class: str
    confidence: float
    importance: float
    is_background: bool
    source_url: str
    source_name: str
    entities: list = field(default_factory=list)


@dataclass
class PipelineResult:
    provider: str
    topic: str
    collect: CollectResult = field(default_factory=lambda: CollectResult("", ""))
    alphas: list[AlphaResult] = field(default_factory=list)
    extract_error: Optional[str] = None
    extract_latency_s: float = 0.0


# ── Step 1: Collect ────────────────────────────────────────────────────────────

def collect_gemini(topic: str) -> CollectResult:
    """Gemini grounded search via Interactions API (different quota pool from models.generate_content).
    Uses gemini-3.7-flash — better model than production's gemini-3.5-flash-lite.
    Note: Interactions API returns synthesized prose but no structured grounding_chunks,
    so source legend is empty — alpha source_attribution will be lower for Gemini by design.
    """
    t0 = time.monotonic()
    try:
        from google import genai
        from truebrief.llm.prompts import build_gemini_search_prompt, GEMINI_SEARCH_SYSTEM

        api_key = (
            os.getenv("GOOGLE_API_KEY_DEV")
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("GOOGLE_API_KEY_BACKUP") or ""
        )
        if not api_key:
            return CollectResult("gemini", topic, error="No GOOGLE_API_KEY", latency_s=0)

        client = genai.Client(api_key=api_key)
        prompt = build_gemini_search_prompt(topic, WEEK_AGO, TODAY)
        full_prompt = f"{GEMINI_SEARCH_SYSTEM}\n\n{prompt}"

        interaction = client.interactions.create(
            model="gemini-3.7-flash",
            input=full_prompt,
            tools=[{"type": "google_search"}],
        )
        text = (interaction.output_text or "").strip()
        if not text:
            return CollectResult("gemini", topic, error="empty response", latency_s=time.monotonic()-t0)

        return CollectResult(
            provider="gemini", topic=topic,
            prose=text,
            cited_text=text,          # no citation markers available from Interactions API
            source_legend="(no source legend — Interactions API does not return grounding_chunks)",
            latency_s=time.monotonic() - t0,
            n_real_sources=0,         # structurally 0 for Interactions API
        )
    except Exception as exc:
        return CollectResult("gemini", topic, error=str(exc), latency_s=time.monotonic() - t0)


def collect_linkup(topic: str) -> CollectResult:
    """Linkup sourcedAnswer → build a source legend from returned sources."""
    t0 = time.monotonic()
    api_key = os.getenv("LINKUP_API_KEY", "")
    if not api_key:
        return CollectResult("linkup", topic, error="LINKUP_API_KEY not set", latency_s=0)
    try:
        import httpx
        resp = httpx.post(
            "https://api.linkup.so/v1/search",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "q": topic,
                "depth": "standard",
                "outputType": "sourcedAnswer",
                "maxResults": 15,
                "fromDate": WEEK_AGO,
                "toDate": TODAY,
            },
            timeout=CALL_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        answer = (data.get("answer") or "").strip()
        raw_sources = data.get("sources") or []

        # Build a numbered source legend matching the extract prompt's expected format
        legend_lines = []
        for i, s in enumerate(raw_sources):
            url = s.get("url", "")
            title = s.get("title") or url
            legend_lines.append(f"[{i}] {title} — {url}")
        legend = "\n".join(legend_lines) if legend_lines else "(no sources)"

        if not answer:
            return CollectResult("linkup", topic, error="empty answer", latency_s=time.monotonic()-t0)

        return CollectResult(
            provider="linkup", topic=topic,
            prose=answer,
            cited_text=answer,  # Linkup prose has no citation markers
            source_legend=legend,
            latency_s=time.monotonic() - t0,
            n_real_sources=len([s for s in raw_sources if s.get("url")]),
        )
    except Exception as exc:
        return CollectResult("linkup", topic, error=str(exc), latency_s=time.monotonic() - t0)


def collect_brave(topic: str) -> CollectResult:
    """Brave Web Search with summary=true — AI synthesized answer, not raw snippets."""
    t0 = time.monotonic()
    api_key = os.getenv("BRAVE_API_KEY", "")
    if not api_key:
        return CollectResult("brave", topic, error="BRAVE_API_KEY not set", latency_s=0)
    try:
        import httpx

        # Web Search with AI summary (requires subscription that supports it)
        resp = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={
                "X-Subscription-Token": api_key,
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
            },
            params={
                "q": topic,
                "count": 10,
                "freshness": f"{WEEK_AGO}to{TODAY}",
                "country": "US",
                "search_lang": "en",
                "text_decorations": "false",
                "summary": "true",   # AI-generated synthesized answer
                "extra_snippets": "true",
            },
            timeout=CALL_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        # Extract AI summary if present
        summary_obj = data.get("summarizer") or {}
        ai_summary = (summary_obj.get("answer") or "").strip()

        # Also gather web results as the source material + legend
        web_results = data.get("web", {}).get("results", [])
        legend_lines = []
        prose_lines = []
        for i, r in enumerate(web_results[:15]):
            url = r.get("url", "")
            title = r.get("title", "")
            desc = r.get("description", "")
            extras = " ".join((r.get("extra_snippets") or [])[:2])
            legend_lines.append(f"[{i}] {title} — {url}")
            prose_lines.append(f"[{i}] {title}: {desc} {extras}".strip())

        legend = "\n".join(legend_lines) if legend_lines else "(no sources)"
        snippets_prose = "\n".join(prose_lines)

        # Use AI summary as the prose if available, otherwise fall back to snippets
        if ai_summary:
            prose = ai_summary
            cited_text = ai_summary  # no citation markers in Brave summary
        elif snippets_prose:
            prose = snippets_prose
            cited_text = snippets_prose
        else:
            return CollectResult("brave", topic, error="no content returned", latency_s=time.monotonic()-t0)

        return CollectResult(
            provider="brave", topic=topic,
            prose=prose,
            cited_text=cited_text,
            source_legend=legend,
            latency_s=time.monotonic() - t0,
            n_real_sources=len(web_results),
        )
    except Exception as exc:
        return CollectResult("brave", topic, error=str(exc), latency_s=time.monotonic() - t0)


# ── Step 2: Extract (same for all providers) ───────────────────────────────────

def extract_alphas(collect: CollectResult) -> tuple[list[AlphaResult], str, float]:
    """Run the real extract prompt (call 2 of the pipeline) on collected prose.
    Returns (alphas, error_str, latency_s).
    """
    if collect.error or not collect.cited_text.strip():
        return [], f"collect failed: {collect.error}", 0.0

    t0 = time.monotonic()
    try:
        from truebrief.llm.client import LLMClient
        from truebrief.llm.prompts import build_gemini_extract_prompt, GEMINI_EXTRACT_SYSTEM

        llm = LLMClient()
        extract_prompt = build_gemini_extract_prompt(
            cited_text=collect.cited_text,
            source_legend=collect.source_legend,
            topic_name=collect.topic,
            today=TODAY,
        )
        raw = llm.call(
            step_name="gemini_extract",
            prompt=extract_prompt,
            json_mode=True,
            system_prompt=GEMINI_EXTRACT_SYSTEM,
        )

        data = json.loads(raw)
        fact_list = data if isinstance(data, list) else data.get("facts") or data.get("alphas") or []

        alphas = []
        for item in fact_list:
            if not isinstance(item, dict):
                continue
            confidence = float(item.get("confidence", 1.0))
            if confidence < 0.6:
                continue
            alpha_text = str(item.get("alpha_text", "")).strip()
            if not alpha_text:
                continue
            raw_date = str(item.get("event_date") or "").strip()
            if not raw_date or raw_date.lower() in ("unknown", "null", "none", ""):
                continue

            # For non-Gemini providers: source attribution comes from the legend directly
            source_url = ""
            source_name = ""
            for ci in (item.get("citation_indices") or []):
                if isinstance(ci, int) and ci >= 0:
                    # Parse from legend line "[N] Title — URL"
                    for line in collect.source_legend.split("\n"):
                        if line.startswith(f"[{ci}]"):
                            parts = line.split(" — ", 1)
                            if len(parts) == 2:
                                source_name = parts[0].replace(f"[{ci}] ", "").strip()
                                source_url = parts[1].strip()
                            break

            alphas.append(AlphaResult(
                alpha_text=alpha_text,
                event_date=raw_date,
                event_class=item.get("event_class") or "",
                confidence=confidence,
                importance=float(item.get("importance") or 0.5),
                is_background=bool(item.get("is_background", False)),
                source_url=source_url,
                source_name=source_name,
                entities=list(item.get("entities") or []),
            ))

        return alphas, "", time.monotonic() - t0
    except Exception as exc:
        return [], str(exc), time.monotonic() - t0


# ── Step 3: Judge Alphas ───────────────────────────────────────────────────────

JUDGE_PROMPT = """You are scoring the Alpha extraction output of 2 search providers for a news pipeline.
Today: {today}. Topic: "{topic}"

Each provider ran through the same 2-call extraction pipeline (collect -> extract with the same prompt).
You are judging the RESULTING ALPHA OBJECTS, not raw search text. Score what is in the alpha lists.

=== LINKUP ALPHAS ({n_linkup} facts) ===
{linkup_alphas}

=== BRAVE ALPHAS ({n_brave} facts) ===
{brave_alphas}

Score each provider 0-3 on each axis. Be strict and literal.

AXES:
- alpha_quality (0-3): Are alpha_text sentences clean, factual, verifiable, editorial-free?
  3=all clean; 2=mostly clean; 1=mixed; 0=mostly editorializing/vague
- freshness (0-3): Do event_dates fall within the last 7 days (since {week_ago})?
  3=all this week; 2=most; 1=mixed; 0=all old or undated
- fact_count (0-3): Non-background alphas with confidence >= 0.7
  3=6+ fresh facts; 2=4-5; 1=2-3; 0=0-1
- noise_free (0-3): is_background=false facts are genuinely new, not standing states
  3=all fresh developments; 2=minor background noise; 1=some; 0=mostly background
- topic_relevance (0-3): Facts are actually about the topic, not tangential
  3=all on-topic; 2=mostly; 1=mixed; 0=mostly off-topic
- specificity (0-3): Facts contain specific names, dates, numbers, organizations
  3=every fact has 2+ specific details; 2=most do; 1=some; 0=vague only

Respond ONLY with valid JSON (no markdown fences):
{{
  "linkup": {{"alpha_quality": N, "freshness": N, "fact_count": N, "noise_free": N, "topic_relevance": N, "specificity": N, "notes": "one sentence"}},
  "brave":  {{"alpha_quality": N, "freshness": N, "fact_count": N, "noise_free": N, "topic_relevance": N, "specificity": N, "notes": "one sentence"}},
  "winner": "linkup|brave|tie",
  "key_finding": "one sentence about what this topic revealed about the two providers"
}}
"""

AXES = ["alpha_quality", "freshness", "fact_count", "noise_free", "topic_relevance", "specificity"]
PROVIDERS = ["linkup", "brave"]


def _format_alphas(alphas: list[AlphaResult]) -> str:
    if not alphas:
        return "(no alphas extracted)"
    lines = []
    for i, a in enumerate(alphas[:8]):  # cap at 8 to stay within Groq context
        bg = " BG" if a.is_background else ""
        lines.append(
            f"{i+1}. [{a.event_date}][{a.event_class}] conf={a.confidence:.1f}{bg} | {a.alpha_text[:180]}"
        )
    return "\n".join(lines)


def run_judge(topic: str, results: dict[str, PipelineResult]) -> dict:
    try:
        from groq import Groq

        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            return {"error": "GROQ_API_KEY not set"}
        client = Groq(api_key=api_key)

        def _alphas_txt(p: str) -> str:
            r = results[p]
            if r.extract_error:
                return f"(EXTRACT FAILED: {r.extract_error[:100]})"
            return _format_alphas(r.alphas)

        prompt = JUDGE_PROMPT.format(
            today=TODAY,
            week_ago=WEEK_AGO,
            topic=topic,
            n_linkup=len(results["linkup"].alphas),
            n_brave=len(results["brave"].alphas),
            linkup_alphas=_alphas_txt("linkup"),
            brave_alphas=_alphas_txt("brave"),
        )
        response = client.chat.completions.create(
            model=JUDGE_MODEL,
            messages=[
                {"role": "system", "content": "You are a precise benchmark judge. Output only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return {"error": f"no JSON: {raw[:200]}"}
        return json.loads(m.group(0))
    except Exception as exc:
        return {"error": str(exc)}


# ── Orchestrator ───────────────────────────────────────────────────────────────

def run_topic(topic: str, parallel: bool = True) -> dict[str, PipelineResult]:
    print(f"\n  Topic: {topic!r}")

    # Step 1: Collect
    if parallel:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            fl = pool.submit(collect_linkup, topic)
            fb = pool.submit(collect_brave, topic)
            l_collect = fl.result(timeout=CALL_TIMEOUT)
            b_collect = fb.result(timeout=CALL_TIMEOUT)
    else:
        l_collect = collect_linkup(topic)
        b_collect = collect_brave(topic)

    for c in [l_collect, b_collect]:
        if c.error:
            print(f"    {c.provider}: COLLECT ERROR — {c.error[:80]}")
        else:
            print(f"    {c.provider}: {c.latency_s:.1f}s | {len(c.prose)} prose chars | {c.n_real_sources} sources")

    # Step 2: Extract (same for all, can parallelize)
    if parallel:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            fle = pool.submit(extract_alphas, l_collect)
            fbe = pool.submit(extract_alphas, b_collect)
            l_alphas, l_err, l_ext_t = fle.result(timeout=CALL_TIMEOUT)
            b_alphas, b_err, b_ext_t = fbe.result(timeout=CALL_TIMEOUT)
    else:
        l_alphas, l_err, l_ext_t = extract_alphas(l_collect)
        b_alphas, b_err, b_ext_t = extract_alphas(b_collect)

    results = {
        "linkup": PipelineResult("linkup", topic, l_collect, l_alphas, l_err, l_ext_t),
        "brave":  PipelineResult("brave",  topic, b_collect, b_alphas, b_err, b_ext_t),
    }

    for p, r in results.items():
        if r.extract_error:
            print(f"    {p}: EXTRACT ERROR — {r.extract_error[:80]}")
        else:
            fresh = [a for a in r.alphas if not a.is_background]
            print(f"    {p}: {len(r.alphas)} alphas ({len(fresh)} fresh) | extract {r.extract_latency_s:.1f}s")

    return results


# ── Report ─────────────────────────────────────────────────────────────────────

def _score_total(scores: dict) -> int:
    return sum(scores.get(a, 0) for a in AXES)


def print_scorecard(all_runs: list[tuple]) -> None:
    print(f"\n{'='*70}")
    print("  PIPELINE SCORECARD (Alpha quality after full 2-call extract)")
    print(f"{'='*70}")
    print(f"  {'Topic':<42} {'Lnk':>5} {'Bra':>5}  Winner")
    print(f"  {'-'*68}")

    totals = {p: 0 for p in PROVIDERS}
    for topic, results, judgment in all_runs:
        scores = {p: _score_total(judgment.get(p, {})) for p in PROVIDERS}
        winner = judgment.get("winner", "?")
        for p in PROVIDERS:
            totals[p] += scores[p]
        t = topic[:40]
        print(f"  {t:<42} {scores['linkup']:>5} {scores['brave']:>5}  {winner}")

    print(f"  {'-'*68}")
    print(f"  {'TOTAL':<42} {totals['linkup']:>5} {totals['brave']:>5}")

    print(f"\n  {'Topic':<42} Key finding")
    print(f"  {'-'*68}")
    for topic, _, judgment in all_runs:
        finding = judgment.get("key_finding", "—")[:50]
        print(f"  {topic[:40]:<42} {finding}")

    print(f"\n  Alpha count by topic:")
    print(f"  {'Topic':<42} {'Lnk':>5} {'Bra':>5}")
    for topic, results, _ in all_runs:
        l = len(results["linkup"].alphas)
        b = len(results["brave"].alphas)
        print(f"  {topic[:40]:<42} {l:>5} {b:>5}")

    print(f"\n  Cost/call: Linkup ~$0.006 + extract | Brave ~$0.005 + extract")
    print(f"  Max per topic: {len(AXES)*3}  Grand max: {len(AXES)*3*len(all_runs)}")


def save_report(all_runs: list[tuple]) -> str:
    date_str = datetime.date.today().isoformat()
    path = os.path.join(ROOT, "docs", "benchmarks", f"{date_str}_search-layer-v3-pipeline.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)

    totals = {p: 0 for p in PROVIDERS}
    for _, results, judgment in all_runs:
        for p in PROVIDERS:
            totals[p] += _score_total(judgment.get(p, {}))

    lines = [
        f"# Search Layer Benchmark v3 — Pipeline Level",
        f"**Date:** {date_str}  |  **Topics:** {len(all_runs)}  |  **Max score:** {len(AXES)*3*len(all_runs)} per provider",
        "",
        "Linkup and Brave run through the same 2-call pipeline (collect -> extract via `build_gemini_extract_prompt`).",
        "Judge scores the resulting Alpha objects, not raw search output. Gemini excluded — quota exhausted.",
        "",
        "## Summary",
        "",
        f"| Topic | Linkup | Brave | Winner |",
        f"|---|---|---|---|",
    ]
    for topic, _, judgment in all_runs:
        scores = {p: _score_total(judgment.get(p, {})) for p in PROVIDERS}
        winner = judgment.get("winner", "?")
        lines.append(f"| {topic} | {scores['linkup']} | {scores['brave']} | **{winner}** |")
    lines += [
        f"| **TOTAL** | **{totals['linkup']}** | **{totals['brave']}** | |",
        "",
        "## Alpha counts",
        "",
        f"| Topic | Linkup | Brave |",
        f"|---|---|---|",
    ]
    for topic, results, _ in all_runs:
        l = len(results["linkup"].alphas)
        b = len(results["brave"].alphas)
        lines.append(f"| {topic} | {l} | {b} |")
    lines.append("")
    lines.append("## Per-Topic Results")
    lines.append("")

    for topic, results, judgment in all_runs:
        lines += [
            f"### {topic}",
            "",
            f"| Axis | Linkup | Brave |",
            f"|---|---|",
        ]
        for ax in AXES:
            l = judgment.get("linkup", {}).get(ax, "?")
            b = judgment.get("brave", {}).get(ax, "?")
            lines.append(f"| {ax} | {l} | {b} |")
        scores = {p: _score_total(judgment.get(p, {})) for p in PROVIDERS}
        lines += [
            f"| **TOTAL** | **{scores['linkup']}** | **{scores['brave']}** |",
            "",
            f"**Winner:** {judgment.get('winner', '?')}  |  **Finding:** {judgment.get('key_finding', '—')}",
            "",
        ]
        for p in PROVIDERS:
            r = results[p]
            notes = judgment.get(p, {}).get("notes", "—")
            fresh_count = len([a for a in r.alphas if not a.is_background])
            sourced = len([a for a in r.alphas if a.source_url])
            lines.append(
                f"**{p.capitalize()}**: {len(r.alphas)} alphas ({fresh_count} fresh, {sourced} sourced) | "
                f"collect {r.collect.latency_s:.1f}s + extract {r.extract_latency_s:.1f}s | {notes}"
            )
            if r.extract_error:
                lines.append(f"  EXTRACT ERROR: {r.extract_error}")
            lines.append("")

        # Alpha detail per provider
        for p in PROVIDERS:
            r = results[p]
            label = p.capitalize()
            lines.append(f"<details><summary>{label} Alphas ({len(r.alphas)})</summary>")
            lines.append("")
            if r.collect.error:
                lines.append(f"Collect failed: {r.collect.error}")
            elif r.extract_error:
                lines.append(f"Extract failed: {r.extract_error}")
            else:
                for i, a in enumerate(r.alphas):
                    bg = " BACKGROUND" if a.is_background else ""
                    src = f" | [{a.source_name}]({a.source_url})" if a.source_url else ""
                    lines.append(
                        f"{i+1}. **[{a.event_date}]** [{a.event_class}] conf={a.confidence:.2f}{bg}{src}  "
                        f"\n   {a.alpha_text}"
                    )
            lines.append("</details>")
            lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topics", nargs="*", help="Override topics")
    parser.add_argument("--no-parallel", action="store_true")
    args = parser.parse_args()

    topics = args.topics or DEFAULT_TOPICS
    parallel = not args.no_parallel

    print(f"\nSearch Layer Benchmark v3 (Pipeline) — {TODAY}")
    print(f"Topics: {len(topics)} | Parallel: {parallel}")
    print(f"Pipeline: collect x3 -> extract x3 (real prompts) -> judge x1 per topic")
    print(f"Estimated calls: {len(topics)} x (2 collect + 2 extract + 1 judge) = {len(topics) * 5}")

    all_runs = []
    for topic in topics:
        results = run_topic(topic, parallel=parallel)
        print(f"    judging...")
        judgment = run_judge(topic, results)
        if "error" in judgment:
            print(f"    JUDGE ERROR: {judgment['error'][:100]}")
        else:
            scores = {p: _score_total(judgment.get(p, {})) for p in PROVIDERS}
            print(f"    Scores: linkup={scores['linkup']} brave={scores['brave']} winner={judgment.get('winner')}")
        all_runs.append((topic, results, judgment))

    print_scorecard(all_runs)
    path = save_report(all_runs)
    print(f"\n  Report: {path}")


if __name__ == "__main__":
    main()
