"""
Topic Finisher Experiment — scripts/topic_finisher_experiment.py

Standalone, throwaway dev-tool script. NOT wired into any pipeline, route, or the
frontend. Evaluates 3 candidate "topic finishing" strategies (prompts.py, STAGE:
topic_finisher section) for cleaning up topics.raw_query, which today is stored
verbatim and used BOTH as the UI display name AND as the literal search prompt fed to
Gemini Search grounding.

Strategy A: one combined call -> {"name": ..., "search_prompt": ...}
Strategy B: two separate cheap calls -> name only, then search_prompt only
Strategy C: one call -> a single corrected string, reused as BOTH name and search_prompt

For each strategy's resulting search_prompt (or the reused string for C), this script
makes a REAL live call through the same grounding path GeminiSearchCollector uses
(LLMClient.call_gemini_with_grounding with GEMINI_SEARCH_SYSTEM / build_gemini_search_
prompt), then reports how many distinct developments came back, whether grounding_chunks
were real, and a rough relevance judgment against what the user meant.

Usage:
    .venv/Scripts/python.exe scripts/topic_finisher_experiment.py
    .venv/Scripts/python.exe scripts/topic_finisher_experiment.py --inputs-only   # skip live grounding calls
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime

from truebrief.llm.client import LLMClient, LLMError
from truebrief.llm.prompts import (
    GEMINI_SEARCH_SYSTEM,
    TOPIC_FINISHER_COMBINED_SYSTEM,
    TOPIC_FINISHER_CORRECTED_SYSTEM,
    TOPIC_FINISHER_NAME_SYSTEM,
    TOPIC_FINISHER_SEARCH_SYSTEM,
    build_gemini_search_prompt,
    build_topic_finisher_combined_prompt,
    build_topic_finisher_corrected_prompt,
    build_topic_finisher_name_prompt,
    build_topic_finisher_search_prompt,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("topic_finisher_experiment")

# --------------------------------------------------------------------------------
# Fixed test inputs — spread across messiness types.
# --------------------------------------------------------------------------------
TEST_INPUTS: list[tuple[str, str]] = [
    (
        "rambling_run_on_finance",
        "news about stocks that low right now and worth to invest in cose experts think it jump up",
    ),
    (
        "rambling_run_on_geopolitics",
        "what is going on with that ukraine russia thing lately like is there gonna be peace deal "
        "or what everyone keeps saying different stuff",
    ),
    (
        "too_terse",
        "tesla",
    ),
    (
        "typo_laden",
        "nvida ai chp export ban china lattst news",
    ),
    (
        "multi_topic_ambiguous",
        "israel gaza news and also bitcoin price and maybe some AI stuff too",
    ),
    (
        "normal_control",
        "Federal Reserve interest rate decisions",
    ),
    (
        "non_english_slangy",
        "yo whats the deal with lakers this season they balling or nah",
    ),
]


@dataclass
class StrategyResult:
    strategy: str
    call_count: int
    latency_s: float
    name: str = ""
    search_prompt: str = ""
    error: str = ""
    grounding_chunks: int = 0
    grounding_ok: bool = False
    grounded_text_preview: str = ""
    developments_estimate: int = 0
    grounding_error: str = ""
    grounding_latency_s: float = 0.0


def _try_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except Exception:
        logger.warning("Non-JSON response, raw=%s", raw[:200])
        return {}


def run_strategy_a(llm: LLMClient, raw_query: str) -> StrategyResult:
    t0 = time.monotonic()
    try:
        raw = llm.call(
            step_name="topic_finisher_combined",
            prompt=build_topic_finisher_combined_prompt(raw_query),
            json_mode=True,
            system_prompt=TOPIC_FINISHER_COMBINED_SYSTEM,
        )
        data = _try_json(raw)
        return StrategyResult(
            strategy="A (combined)",
            call_count=1,
            latency_s=time.monotonic() - t0,
            name=str(data.get("name", "")).strip(),
            search_prompt=str(data.get("search_prompt", "")).strip(),
        )
    except LLMError as exc:
        return StrategyResult(strategy="A (combined)", call_count=1,
                               latency_s=time.monotonic() - t0, error=str(exc))


def run_strategy_b(llm: LLMClient, raw_query: str) -> StrategyResult:
    t0 = time.monotonic()
    try:
        raw_name = llm.call(
            step_name="topic_finisher_name",
            prompt=build_topic_finisher_name_prompt(raw_query),
            json_mode=True,
            system_prompt=TOPIC_FINISHER_NAME_SYSTEM,
        )
        raw_search = llm.call(
            step_name="topic_finisher_search",
            prompt=build_topic_finisher_search_prompt(raw_query),
            json_mode=True,
            system_prompt=TOPIC_FINISHER_SEARCH_SYSTEM,
        )
        name_data = _try_json(raw_name)
        search_data = _try_json(raw_search)
        return StrategyResult(
            strategy="B (split)",
            call_count=2,
            latency_s=time.monotonic() - t0,
            name=str(name_data.get("name", "")).strip(),
            search_prompt=str(search_data.get("search_prompt", "")).strip(),
        )
    except LLMError as exc:
        return StrategyResult(strategy="B (split)", call_count=2,
                               latency_s=time.monotonic() - t0, error=str(exc))


def run_strategy_c(llm: LLMClient, raw_query: str) -> StrategyResult:
    t0 = time.monotonic()
    try:
        raw = llm.call(
            step_name="topic_finisher_corrected",
            prompt=build_topic_finisher_corrected_prompt(raw_query),
            json_mode=True,
            system_prompt=TOPIC_FINISHER_CORRECTED_SYSTEM,
        )
        data = _try_json(raw)
        corrected = str(data.get("corrected_query", "")).strip()
        return StrategyResult(
            strategy="C (reused)",
            call_count=1,
            latency_s=time.monotonic() - t0,
            name=corrected,
            search_prompt=corrected,
        )
    except LLMError as exc:
        return StrategyResult(strategy="C (reused)", call_count=1,
                               latency_s=time.monotonic() - t0, error=str(exc))


def _estimate_developments(text: str) -> int:
    """Rough count of distinct developments: count non-empty lines / sentences that look
    like separate bullet-ish items. Good enough for a comparative dev-tool report, not a
    precision metric."""
    if not text:
        return 0
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) > 1:
        return len(lines)
    # Fallback: split on sentence-ish boundaries.
    import re
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    return len(sentences)


def run_live_grounding(llm: LLMClient, search_prompt: str) -> tuple:
    """Real live call through the SAME grounding path GeminiSearchCollector uses.
    Returns (chunks_count, ok, text_preview, dev_estimate, error, latency_s)."""
    if not search_prompt:
        return 0, False, "", 0, "empty search_prompt, skipped", 0.0
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = build_gemini_search_prompt(search_prompt, "", today)
    t0 = time.monotonic()
    try:
        grounded = llm.call_gemini_with_grounding(
            step_name="gemini_search",
            prompt=prompt,
            system_prompt=GEMINI_SEARCH_SYSTEM,
        )
        latency = time.monotonic() - t0
        chunks = len(grounded.chunks or [])
        text = grounded.text or ""
        dev_est = _estimate_developments(text)
        return chunks, chunks > 0, text[:300], dev_est, "", latency
    except LLMError as exc:
        return 0, False, "", 0, str(exc), time.monotonic() - t0


def run_all(inputs_only: bool) -> list[dict]:
    llm = LLMClient()
    report: list[dict] = []

    for label, raw_query in TEST_INPUTS:
        print(f"\n{'=' * 90}")
        print(f"INPUT [{label}]: {raw_query!r}")
        print("=" * 90)

        row: dict = {"label": label, "raw_query": raw_query, "strategies": {}}

        for fn in (run_strategy_a, run_strategy_b, run_strategy_c):
            result = fn(llm, raw_query)
            print(f"\n-- Strategy {result.strategy} -- calls={result.call_count} "
                  f"latency={result.latency_s:.2f}s")
            if result.error:
                print(f"   ERROR: {result.error}")
                row["strategies"][result.strategy] = {"error": result.error}
                continue
            print(f"   name:          {result.name!r}")
            print(f"   search_prompt: {result.search_prompt!r}")

            if not inputs_only:
                chunks, ok, preview, dev_est, gerr, glat = run_live_grounding(
                    llm, result.search_prompt
                )
                result.grounding_chunks = chunks
                result.grounding_ok = ok
                result.grounded_text_preview = preview
                result.developments_estimate = dev_est
                result.grounding_error = gerr
                result.grounding_latency_s = glat
                print(f"   grounding: chunks={chunks} ok={ok} dev_estimate={dev_est} "
                      f"latency={glat:.2f}s")
                if gerr:
                    print(f"   grounding ERROR: {gerr}")
                if preview:
                    print(f"   preview: {preview!r}")

            row["strategies"][result.strategy] = {
                "call_count": result.call_count,
                "latency_s": round(result.latency_s, 2),
                "name": result.name,
                "search_prompt": result.search_prompt,
                "grounding_chunks": result.grounding_chunks,
                "grounding_ok": result.grounding_ok,
                "developments_estimate": result.developments_estimate,
                "grounding_latency_s": round(result.grounding_latency_s, 2),
                "grounding_error": result.grounding_error,
            }

        report.append(row)

    return report


def print_summary(report: list[dict]) -> None:
    print(f"\n\n{'#' * 90}")
    print("SUMMARY TABLE")
    print("#" * 90)

    header = f"{'input':<28} {'strat':<12} {'calls':<6} {'chunks':<7} {'devs':<6} {'name'}"
    print(header)
    print("-" * len(header))
    for row in report:
        for strat, data in row["strategies"].items():
            if "error" in data:
                print(f"{row['label']:<28} {strat:<12} {'ERR':<6} {'-':<7} {'-':<6} "
                      f"ERROR: {data['error'][:60]}")
                continue
            print(
                f"{row['label']:<28} {strat:<12} "
                f"{data['call_count']:<6} {data['grounding_chunks']:<7} "
                f"{data['developments_estimate']:<6} {data['name'][:40]}"
            )

    # Rough aggregate scoring: sum of grounding_chunks + developments_estimate per strategy
    # across inputs that didn't error. Purely a comparative dev-tool signal, not a metric.
    totals: dict[str, dict] = {}
    for row in report:
        for strat, data in row["strategies"].items():
            if "error" in data:
                continue
            t = totals.setdefault(strat, {"chunks": 0, "devs": 0, "calls": 0, "n": 0,
                                           "grounding_errors": 0})
            t["chunks"] += data["grounding_chunks"]
            t["devs"] += data["developments_estimate"]
            t["calls"] += data["call_count"]
            t["n"] += 1
            if data.get("grounding_error"):
                t["grounding_errors"] += 1

    print(f"\n{'-' * 90}")
    print("AGGREGATE (sum across all non-errored inputs)")
    print(f"{'-' * 90}")
    for strat, t in totals.items():
        print(f"{strat:<12} total_calls_per_run={t['calls'] // max(t['n'], 1)} "
              f"n_inputs={t['n']} total_chunks={t['chunks']} total_devs={t['devs']} "
              f"grounding_errors={t['grounding_errors']}")

    print(f"\n{'-' * 90}")
    print("COST/LATENCY NOTES")
    print(f"{'-' * 90}")
    print("Strategy A: 1 LLM call (name+search_prompt together) + 1 grounding call = 2 total.")
    print("Strategy B: 2 LLM calls (name, then search_prompt separately) + 1 grounding call = 3 total.")
    print("Strategy C: 1 LLM call (single corrected string reused) + 1 grounding call = 2 total.")
    print("A and C are call-count-equivalent; B costs one extra cheap call per topic finish.")
    print("Latency numbers printed per-strategy above are wall-clock for this run only —")
    print("not averaged over multiple trials; treat as directional, not a benchmark.")

    print(f"\n{'-' * 90}")
    print("RECOMMENDATION")
    print(f"{'-' * 90}")
    if not totals:
        print("No successful strategy runs — cannot recommend. Check errors above "
              "(likely quota exhaustion; see LLMError messages for limit:0 vs normal cap).")
        return

    best_dev = max(totals.items(), key=lambda kv: kv[1]["devs"])
    best_chunks = max(totals.items(), key=lambda kv: kv[1]["chunks"])
    if best_dev[0] == best_chunks[0]:
        print(
            f"Recommend Strategy {best_dev[0]}: highest total grounded developments "
            f"({best_dev[1]['devs']}) AND highest total real grounding_chunks "
            f"({best_chunks[1]['chunks']}) across the test set."
        )
    else:
        print(
            "No clear winner on both axes: "
            f"Strategy {best_dev[0]} surfaced the most developments ({best_dev[1]['devs']}), "
            f"Strategy {best_chunks[0]} surfaced the most real grounding_chunks "
            f"({best_chunks[1]['chunks']}). "
        )
        # Prefer the cheaper of A/C over B when results are close, all else equal.
        if "B (split)" in (best_dev[0], best_chunks[0]):
            print(
                "Since B costs an extra LLM call per topic finish without a clean win on "
                "both axes, recommend A (combined) or C (reused) unless B's advantage is "
                "confirmed on a larger sample — the split call is a real, recurring cost "
                "for a marginal or mixed quality gain."
            )
        else:
            print(
                "Between A and C: A separates the UI name from the search prompt (lets the "
                "search phrasing diverge from the display name), while C guarantees "
                "consistency between what the user sees and what gets searched, at the risk "
                "of an under-specified search_prompt on very terse/ambiguous inputs. Prefer "
                "A when the raw input is terse/ambiguous/multi-topic (name and search intent "
                "diverge); prefer C when inputs are already close to well-formed."
            )

    print("\nQualitative name-field check (read the printed 'name' fields above per input):")
    print("- Watch for genericness (e.g. bare 'News', 'Topic', 'Market') and truncation.")
    print("- Strategy C's reused string is judged as BOTH name and search_prompt — a name")
    print("  that reads fine standalone can still be a weak/underspecified search query, and")
    print("  vice versa; that tension is exactly what this experiment is measuring.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inputs-only", action="store_true",
        help="Skip the live grounding calls; only run the 3 finishing strategies "
             "(name/search_prompt generation) and print those results.",
    )
    args = parser.parse_args()

    report = run_all(inputs_only=args.inputs_only)
    print_summary(report)


if __name__ == "__main__":
    main()
