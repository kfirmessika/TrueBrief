#!/usr/bin/env python3
"""
scripts/judge_accuracy_audit.py

Reusable, extensive accuracy audit for the dedup pipeline (cosine gate + JudgeLLM),
built in response to a 2026-08-12 live finding: one confirmed leak (a real duplicate
scored 0.714, just under GREY_ZONE_MIN=0.75, auto-inserted as brand-new) and 71% of
same-day-rescan duplicate pairs landing in the grey zone where the LLM judge is
consulted -- but never independently checked for correctness.

This script measures, with the REAL production embedder (LLMClient.embed) and the
REAL Arbiter/JudgeLLM code (src/truebrief/arbiter/{arbiter,judge}.py, imported and
called, never modified):

  1. Cosine-gate accuracy    -- of grader-labeled SAME_EVENT pairs, what % leak below
                                 GREY_ZONE_MIN (0.75)? What's the zone distribution?
  2. JudgeLLM accuracy       -- confusion matrix (predicted MERGE/UPDATE/NEW vs grader
                                 SAME/DIFFERENT) for grey-zone pairs only.
  3. False-positive rate     -- of CERTAIN true-negative cross-topic pairs, what %
                                 scored >= grey-zone or got misjudged as duplicates?
  4. Auto-merge sanity check -- pairs scoring >= 0.97 (no LLM call at all in prod).
  5. End-to-end accuracy     -- % of true duplicates caught by SOME stage vs leaked.

It does NOT import/modify src/truebrief/arbiter/arbiter.py, judge.py, or
vector_store.py -- it imports JudgeLLM directly and drives it with hand-built
(alpha, score) match lists, matching the exact shape the real Arbiter feeds it
(see arbiter.py _grey_zone_decision / judge_alphas), without touching pgvector
or the known_facts table (no DB writes, no FK'd temp topics needed).

Usage:
    python scripts/judge_accuracy_audit.py                       # full run, default topics
    python scripts/judge_accuracy_audit.py --topics "Iran war,Trump"
    python scripts/judge_accuracy_audit.py --load-corpus <path>   # re-run stages 2-4 on a
                                                                    previously collected corpus
                                                                    (no new gemini_search/extract
                                                                    calls, still re-embeds/re-judges)
    python scripts/judge_accuracy_audit.py --skip-grading         # reuse a corpus's cached grader
                                                                    labels (if present) too

Output:
    - Console: full numeric report (same content as the .md file).
    - docs/benchmarks/YYYY-MM-DD_judge-accuracy-audit.md
    - A corpus JSON cache under docs/benchmarks/_data/ (raw alphas + embeddings + grader
      labels) so re-runs don't re-spend on collection/embedding/grading unless asked to.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import math
import os
import random
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# ── bootstrap path + env (mirrors scripts/quality_benchmark.py) ────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(ROOT, ".env"))

# V5_EXECUTION_AUDIT.md §8.2: local .env overrides EMBED_PROVIDER to "local" (free CPU
# embedder). Production's Railway Worker does NOT set this var, so it silently runs on
# the code default, "gemini" (models/gemini-embedding-2). This audit measures PRODUCTION
# behavior, so force the production default here regardless of local .env.
os.environ["EMBED_PROVIDER"] = "gemini"

logging.basicConfig(level=logging.WARNING)  # keep console output to our own prints
logger = logging.getLogger("judge_accuracy_audit")

from truebrief.llm.client import LLMClient  # noqa: E402
from truebrief.collector.gemini_search_collector import GeminiSearchCollector  # noqa: E402
from truebrief.models.alpha import Alpha, DecisionType  # noqa: E402
from truebrief.arbiter.judge import JudgeLLM  # noqa: E402
from truebrief.arbiter.arbiter import AUTO_MERGE_THRESHOLD, GREY_ZONE_MIN  # noqa: E402

# ── config ────────────────────────────────────────────────────────────────────────

DEFAULT_TOPICS = [
    "Iran war",
    "Israel",
    "Trump",
    "US stock market outlook",
    "Ukraine war",
    "Federal Reserve interest rates",
]

# Verified against config/settings.py LLM_CONFIG (already live for gemini_extract /
# arbiter steps in production, per the verify-llm-models skill -- not typed from memory).
GRADER_MODEL = "gemini-3.1-flash-lite"
GRADER_STEP_NAME = "judge_accuracy_grader"  # distinct telemetry stage; not in V5_STAGES,
                                             # won't appear on the admin cost dashboard.

CROSS_TOPIC_PAIRS_PER_COMBO = 2
MULTIDAY_MIN_AGE_DAYS = 2  # facts must be dated >= this many days before "today" to
                            # count as the "older" side of a multi-day-proxy pair.

GRADER_SYSTEM = (
    "You are an independent fact-comparison grader auditing a news deduplication "
    "system. You are NOT the production system being tested -- you are a second "
    "opinion used to measure its accuracy. Be precise and skeptical."
)

GRADER_PROMPT = """Compare these two news facts. Decide whether they describe the SAME
real-world reported development, or DIFFERENT developments.

FACT A (topic: "{topic_a}", event date: {date_a}):
"{text_a}"

FACT B (topic: "{topic_b}", event date: {date_b}):
"{text_b}"

Rules:
- SAME_EVENT: both facts describe the identical underlying development/announcement/
  incident -- including cases where one is a reworded restatement, a revised number/
  detail on the same event, or reported by a different outlet. Event dates can be
  extracted with noise (off by a few days) -- don't let a date mismatch alone drive
  the label if the substance is clearly the same development.
- DIFFERENT_EVENT: the facts describe genuinely distinct developments, even if about
  the same broad topic, same entities, or same ongoing story arc.

Respond ONLY with valid JSON, no markdown fences:
{{"label": "SAME_EVENT" | "DIFFERENT_EVENT", "reason": "one line, <=25 words"}}
"""


# ── data classes ─────────────────────────────────────────────────────────────────

@dataclasses.dataclass
class Pair:
    category: str            # same_day_rescan | multi_day_proxy | cross_topic
    topic_a: str
    topic_b: str
    new_alpha: Alpha         # the "incoming" fact
    match_alpha: Alpha       # the "existing/known" fact it's compared against
    cosine: float = 0.0
    grader_label: Optional[str] = None      # SAME_EVENT | DIFFERENT_EVENT
    grader_reason: Optional[str] = None
    ground_truth_source: str = "grader"     # "grader" | "construction (cross-topic)"
    zone: Optional[str] = None              # AUTO_NEW | GREY_ZONE | AUTO_MERGE
    predicted: Optional[str] = None         # AUTO_NEW | AUTO_MERGE | MERGE | UPDATE | NEW
    judge_delta: Optional[str] = None
    error: Optional[str] = None


# ── serialization helpers (for corpus caching) ─────────────────────────────────────

def _alpha_to_dict(a: Alpha) -> dict:
    d = dataclasses.asdict(a)
    for k in ("event_date", "published_at", "created_at"):
        if isinstance(d.get(k), datetime):
            d[k] = d[k].isoformat()
    return d


def _alpha_from_dict(d: dict) -> Alpha:
    d = dict(d)
    for k in ("event_date", "published_at", "created_at"):
        if d.get(k):
            try:
                d[k] = datetime.fromisoformat(d[k])
            except Exception:
                d[k] = None
    return Alpha(**d)


# ── stage 1: corpus collection ──────────────────────────────────────────────────

def _is_quota_like(exc: Exception) -> bool:
    msg = str(exc)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower()


def _collect_with_retry(
    collector: "GeminiSearchCollector",
    topic: str,
    last_run_date,
    label: str,
    max_wait_hours: float,
    initial_wait_s: float,
    max_wait_s: float,
):
    """Call collector.collect() with retry-with-backoff on quota-like (429/
    RESOURCE_EXHAUSTED) errors -- confirmed live 2026-08-13 that this quota does NOT
    clear within a 60-90s burst-limit-style wait (tested), so this is almost certainly
    a daily cap tied to the Pacific-time day boundary, not a per-minute limit. Rides it
    out with exponential backoff (capped) instead of bailing on the first failure --
    which is exactly what happened on 2026-08-12's partial run (1/6 topics collected,
    then a hard raise on first quota error). Non-quota errors (real bugs, parsing
    failures, etc.) still raise immediately -- no point retrying those.
    """
    deadline = time.monotonic() + max_wait_hours * 3600
    wait_s = initial_wait_s
    attempt = 0
    while True:
        attempt += 1
        try:
            return collector.collect(topic, last_run_date=last_run_date, topic_id=None)
        except Exception as exc:
            if not _is_quota_like(exc):
                print(f"[collect] {topic!r} {label} -- non-quota error, not retrying: {exc!r}")
                raise
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                print(f"[collect] {topic!r} {label} -- quota still exhausted after "
                      f"{max_wait_hours}h retry budget exceeded. Giving up: {exc!r}")
                raise
            wait_s = min(wait_s, max(remaining, 1))
            print(f"[collect] {topic!r} {label} -- quota-like error (attempt {attempt}), "
                  f"waiting {wait_s:.0f}s before retry (budget remaining: {remaining/3600:.1f}h)...")
            time.sleep(wait_s)
            wait_s = min(wait_s * 1.7, max_wait_s)


def collect_corpus(
    topics: List[str],
    llm: LLMClient,
    sleep_s: float = 2.0,
    corpus: Optional[Dict[str, dict]] = None,
    save_path: Optional[str] = None,
    max_wait_hours: float = 9.0,
    retry_initial_wait_s: float = 120.0,
    retry_max_wait_s: float = 900.0,
) -> Dict[str, dict]:
    """Real GeminiSearchCollector.collect() calls. Per topic, 3 runs:
      - run_a, run_b: both windowed "since today" (last_run_date=today 00:00), a few
        seconds apart -- the same-day-rescan scenario from the 2026-08-12 live finding.
      - run_wide: last_run_date=None (searches the last 7 days per collector docstring)
        -- gives older-dated facts used to build multi-day-proxy pairs (see module
        docstring for why this is a proxy, not a literal days-apart rescan).

    Resilient to mid-run failures (e.g. daily grounding-search quota exhaustion, which
    this audit hit live on 2026-08-12 AND again on 2026-08-13 -- see the report's
    "blocker" section): saves the corpus to `save_path` after EVERY topic, skips any
    topic already present in a pre-supplied `corpus` dict, AND (as of 2026-08-13)
    retries each individual collect() call with backoff on quota-like errors, up to
    `max_wait_hours` per call, instead of bailing on the first failure -- so a run
    started while quota is exhausted rides out the reset instead of producing another
    tiny partial corpus.
    """
    collector = GeminiSearchCollector(llm_client=llm)  # no vector_store -> same-day
                                                        # injection skipped, no DB touched.
    today_midnight = datetime(*datetime.now().timetuple()[:3])
    corpus = corpus if corpus is not None else {}

    for topic in topics:
        if topic in corpus:
            print(f"[collect] {topic!r} -- already in corpus, skipping (resume).")
            continue
        try:
            print(f"[collect] {topic!r} -- run_a (same-day window)...")
            run_a = _collect_with_retry(
                collector, topic, today_midnight, "run_a",
                max_wait_hours, retry_initial_wait_s, retry_max_wait_s,
            )
            time.sleep(sleep_s)

            print(f"[collect] {topic!r} -- run_b (same-day window, second call)...")
            run_b = _collect_with_retry(
                collector, topic, today_midnight, "run_b",
                max_wait_hours, retry_initial_wait_s, retry_max_wait_s,
            )
            time.sleep(sleep_s)

            print(f"[collect] {topic!r} -- run_wide (7-day window)...")
            run_wide = _collect_with_retry(
                collector, topic, None, "run_wide",
                max_wait_hours, retry_initial_wait_s, retry_max_wait_s,
            )
            time.sleep(sleep_s)

            print(f"[collect] {topic!r}: run_a={len(run_a)} run_b={len(run_b)} run_wide={len(run_wide)} facts")
            corpus[topic] = {
                "run_a": [_alpha_to_dict(a) for a in run_a],
                "run_b": [_alpha_to_dict(a) for a in run_b],
                "run_wide": [_alpha_to_dict(a) for a in run_wide],
            }
        except Exception as exc:
            print(f"[collect] {topic!r} FAILED: {exc!r}. Saving progress so far and re-raising.")
            if save_path:
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(corpus, f, indent=2, default=str)
                print(f"[collect] partial corpus ({len(corpus)}/{len(topics)} topics) saved to {save_path}")
            raise
        else:
            if save_path:
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(corpus, f, indent=2, default=str)

    return corpus


def load_corpus_alphas(corpus: Dict[str, dict]) -> Dict[str, Dict[str, List[Alpha]]]:
    out: Dict[str, Dict[str, List[Alpha]]] = {}
    for topic, runs in corpus.items():
        out[topic] = {
            key: [_alpha_from_dict(d) for d in alphas]
            for key, alphas in runs.items()
        }
    return out


# ── stage: embedding (real production embedder) ─────────────────────────────────

def embed_corpus(llm: LLMClient, topic_alphas: Dict[str, Dict[str, List[Alpha]]]) -> None:
    for topic, runs in topic_alphas.items():
        for run_name, alphas in runs.items():
            if not alphas:
                continue
            texts = [a.alpha_text for a in alphas]
            print(f"[embed] {topic!r} / {run_name}: {len(texts)} facts...")
            vectors = llm.embed_batch(texts)
            for a, v in zip(alphas, vectors):
                a.embedding = v


def cosine(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def nearest(new: Alpha, pool: List[Alpha]) -> Optional[Tuple[Alpha, float]]:
    if not pool:
        return None
    scored = [(m, cosine(new.embedding, m.embedding)) for m in pool if m.embedding]
    if not scored:
        return None
    return max(scored, key=lambda t: t[1])


# ── stage 2: pair construction ───────────────────────────────────────────────────

def build_pairs(
    topic_alphas: Dict[str, Dict[str, List[Alpha]]],
    rng: random.Random,
) -> List[Pair]:
    pairs: List[Pair] = []
    today = datetime.now()

    # same_day_rescan: each run_b fact vs its nearest run_a fact (same topic).
    for topic, runs in topic_alphas.items():
        run_a, run_b = runs.get("run_a", []), runs.get("run_b", [])
        for fact in run_b:
            best = nearest(fact, run_a)
            if best is None:
                continue
            match, score = best
            pairs.append(Pair(
                category="same_day_rescan", topic_a=topic, topic_b=topic,
                new_alpha=fact, match_alpha=match, cosine=score,
            ))

    # multi_day_proxy: run_a facts (today's window) vs older-dated run_wide facts
    # (event_date >= MULTIDAY_MIN_AGE_DAYS before today) on the same topic. See module
    # docstring -- this approximates a days-apart rescan within one session; it is NOT
    # a literal two-collect()-calls-days-apart test.
    for topic, runs in topic_alphas.items():
        run_a, run_wide = runs.get("run_a", []), runs.get("run_wide", [])
        older = [
            f for f in run_wide
            if f.event_date and (today - f.event_date).days >= MULTIDAY_MIN_AGE_DAYS
        ]
        if not older:
            continue
        for fact in run_a:
            best = nearest(fact, older)
            if best is None:
                continue
            match, score = best
            pairs.append(Pair(
                category="multi_day_proxy", topic_a=topic, topic_b=topic,
                new_alpha=fact, match_alpha=match, cosine=score,
            ))

    # cross_topic: certain true negatives. Sample facts across distinct topics.
    topics = list(topic_alphas.keys())
    for i in range(len(topics)):
        for j in range(i + 1, len(topics)):
            t_i, t_j = topics[i], topics[j]
            pool_i = topic_alphas[t_i].get("run_a", [])
            pool_j = topic_alphas[t_j].get("run_a", [])
            if not pool_i or not pool_j:
                continue
            n = min(CROSS_TOPIC_PAIRS_PER_COMBO, len(pool_i), len(pool_j))
            sample_i = rng.sample(pool_i, n)
            sample_j = rng.sample(pool_j, n)
            for fa, fb in zip(sample_i, sample_j):
                score = cosine(fa.embedding, fb.embedding)
                pairs.append(Pair(
                    category="cross_topic", topic_a=t_i, topic_b=t_j,
                    new_alpha=fa, match_alpha=fb, cosine=score,
                    ground_truth_source="construction (cross-topic, certain)",
                    grader_label="DIFFERENT_EVENT",  # certain by construction; grader
                                                      # opinion added on top below.
                ))

    return pairs


# ── stage 3: grading (separate LLM call, second opinion) ────────────────────────

def _fmt_date(d) -> str:
    return d.strftime("%Y-%m-%d") if isinstance(d, datetime) else "unknown"


def grade_pairs(llm: LLMClient, pairs: List[Pair]) -> None:
    llm_config = dict(llm._config)  # copy -- do NOT mutate the shared LLM_CONFIG import
    llm_config[GRADER_STEP_NAME] = {"provider": "gemini", "model": GRADER_MODEL}
    llm._config = llm_config

    for idx, p in enumerate(pairs, 1):
        certain_negative = p.category == "cross_topic"
        prompt = GRADER_PROMPT.format(
            topic_a=p.topic_a, date_a=_fmt_date(p.new_alpha.event_date),
            text_a=p.new_alpha.alpha_text,
            topic_b=p.topic_b, date_b=_fmt_date(p.match_alpha.event_date),
            text_b=p.match_alpha.alpha_text,
        )
        try:
            raw = llm.call(
                step_name=GRADER_STEP_NAME, prompt=prompt,
                json_mode=True, system_prompt=GRADER_SYSTEM,
            )
            data = json.loads(raw)
            label = str(data.get("label", "")).upper()
            reason = str(data.get("reason", ""))
            if label not in ("SAME_EVENT", "DIFFERENT_EVENT"):
                raise ValueError(f"unexpected grader label: {label!r}")
            if certain_negative:
                # Ground truth stays DIFFERENT_EVENT by construction (unrelated topics).
                # Record the grader's own opinion separately so we can report cases
                # where even the grader would have been fooled.
                p.grader_reason = f"[grader said {label}: {reason}]"
                if label != "DIFFERENT_EVENT":
                    logger.warning(
                        "cross_topic pair graded %s (grader disagreement, ground truth stays DIFFERENT_EVENT): %s",
                        label, reason,
                    )
            else:
                p.grader_label = label
                p.grader_reason = reason
        except Exception as exc:
            p.error = f"grader error: {exc}"
            if not certain_negative:
                p.grader_label = None
        if idx % 10 == 0:
            print(f"[grade] {idx}/{len(pairs)} pairs graded...")


# ── stage 4: run the REAL pipeline (cosine gate + real JudgeLLM) ────────────────

def run_pipeline(judge: JudgeLLM, pairs: List[Pair]) -> None:
    grey_count = 0
    for p in pairs:
        score = p.cosine
        if score >= AUTO_MERGE_THRESHOLD:
            p.zone = "AUTO_MERGE"
            p.predicted = "AUTO_MERGE"
        elif score < GREY_ZONE_MIN:
            p.zone = "AUTO_NEW"
            p.predicted = "AUTO_NEW"
        else:
            p.zone = "GREY_ZONE"
            grey_count += 1

    grey_pairs = [p for p in pairs if p.zone == "GREY_ZONE"]
    print(f"[pipeline] {len(grey_pairs)} pairs in the grey zone -- calling real JudgeLLM...")
    for idx, p in enumerate(grey_pairs, 1):
        try:
            decision, delta = judge.call(p.new_alpha, [(p.match_alpha, p.cosine)])
            p.predicted = decision.value  # DecisionType.DUPLICATE (=MERGE)/UPDATE/NEW
            # Map DecisionType.DUPLICATE (enum value "DUPLICATE") back to MERGE for
            # reporting clarity -- judge.py's own _parse_response comment: "MERGE maps
            # to DUPLICATE in our enum".
            if p.predicted == "DUPLICATE":
                p.predicted = "MERGE"
            p.judge_delta = delta
        except Exception as exc:
            p.error = (p.error + "; " if p.error else "") + f"judge error: {exc}"
            p.predicted = "NEW"  # matches judge.py's own fail-open default
        if idx % 10 == 0:
            print(f"[pipeline] {idx}/{len(grey_pairs)} grey-zone pairs judged...")


# ── stage 5: report ──────────────────────────────────────────────────────────────

def pct(n: int, d: int) -> str:
    return f"{(100.0 * n / d):.1f}%" if d else "n/a (0 pairs)"


def build_report(pairs: List[Pair], topics: List[str], run_note: Optional[str] = None) -> str:
    lines: List[str] = []
    W = lines.append
    if run_note:
        W("## Run status / known limitations for this specific run")
        W("")
        W(run_note)
        W("")

    total = len(pairs)
    by_cat = {}
    for p in pairs:
        by_cat.setdefault(p.category, []).append(p)

    labeled = [p for p in pairs if p.grader_label in ("SAME_EVENT", "DIFFERENT_EVENT") and p.category != "cross_topic"]
    same = [p for p in labeled if p.grader_label == "SAME_EVENT"]
    diff = [p for p in labeled if p.grader_label == "DIFFERENT_EVENT"]
    cross = by_cat.get("cross_topic", [])

    W(f"# Judge/Dedup Accuracy Audit -- {datetime.now().strftime('%Y-%m-%d')}")
    W("")
    W(f"**Topics:** {', '.join(topics)}")
    W(f"**Total pairs:** {total}  |  same_day_rescan: {len(by_cat.get('same_day_rescan', []))}"
      f"  |  multi_day_proxy: {len(by_cat.get('multi_day_proxy', []))}  |  cross_topic: {len(cross)}")
    W(f"**Grader-labeled pairs (non-cross-topic):** {len(labeled)} "
      f"({len(same)} SAME_EVENT, {len(diff)} DIFFERENT_EVENT)")
    W("")
    W(
        "**Ground truth caveat (read before trusting these numbers):** cross-topic pairs "
        "are the ONLY pairs with CERTAIN ground truth (unrelated topics cannot be the same "
        "event, by construction). All same_day_rescan/multi_day_proxy labels come from a "
        "second LLM call (a distinct grader prompt/model, gemini-3.1-flash-lite) -- this is "
        "a second opinion, not ground truth. It can be wrong, especially on genuinely "
        "ambiguous MERGE-vs-UPDATE calls (see the caveat under §2). Treat the flagged list "
        "at the end of this report as the pairs worth a human eyeball before trusting the "
        "aggregate percentages."
    )
    W(
        "\n**multi_day_proxy caveat:** built within a single script run by pairing a "
        "7-day-window collect() call's older-dated facts against a same-day-window "
        "collect() call's facts on the same topic -- NOT two collect() calls literally "
        "days apart (GeminiSearchCollector.collect() has no way to fake 'today' for a "
        "past-dated run). This approximates the intended scenario but is weaker evidence "
        "than same_day_rescan, which uses two real, independently-timed collect() calls."
    )
    W("")

    # ── §1 cosine gate accuracy ──────────────────────────────────────────────
    W("## 1. Cosine gate accuracy")
    W("")
    if same:
        leaked = [p for p in same if p.cosine < GREY_ZONE_MIN]
        W(f"Of {len(same)} grader-labeled SAME_EVENT pairs (same_day_rescan + multi_day_proxy):")
        W(f"- **Silent leak (scored below GREY_ZONE_MIN={GREY_ZONE_MIN}, never reached the judge, "
          f"auto-inserted as NEW):** {len(leaked)}/{len(same)} = **{pct(len(leaked), len(same))}**")
        zone_counts = {}
        for p in same:
            zone_counts[p.zone] = zone_counts.get(p.zone, 0) + 1
        W(f"- Zone distribution over SAME_EVENT pairs: "
          + ", ".join(f"{z}={n} ({pct(n, len(same))})" for z, n in sorted(zone_counts.items())))
        if leaked:
            W("")
            W("**Leaked pairs (cosine < 0.75, grader says same event):**")
            for p in leaked:
                W(f"  - cosine={p.cosine:.3f} | \"{p.new_alpha.alpha_text[:90]}\" <-> \"{p.match_alpha.alpha_text[:90]}\"")
    else:
        W("No grader-labeled SAME_EVENT pairs available (see corpus size / grading errors below).")
    W("")

    # ── §2 JudgeLLM accuracy on grey-zone pairs ──────────────────────────────
    W("## 2. JudgeLLM accuracy (grey-zone pairs only)")
    W("")
    grey_labeled = [p for p in labeled if p.zone == "GREY_ZONE" and p.predicted]
    W(f"Grey-zone pairs with both a grader label and a real JudgeLLM verdict: {len(grey_labeled)}")
    W("")
    if grey_labeled:
        matrix: Dict[str, Dict[str, int]] = {v: {"SAME_EVENT": 0, "DIFFERENT_EVENT": 0} for v in ("MERGE", "UPDATE", "NEW")}
        for p in grey_labeled:
            matrix.setdefault(p.predicted, {"SAME_EVENT": 0, "DIFFERENT_EVENT": 0})
            matrix[p.predicted][p.grader_label] += 1
        W("**Confusion matrix (rows = JudgeLLM verdict, cols = grader label):**")
        W("")
        W("| predicted \\ grader | SAME_EVENT | DIFFERENT_EVENT |")
        W("|---|---|---|")
        for v in ("MERGE", "UPDATE", "NEW"):
            row = matrix.get(v, {"SAME_EVENT": 0, "DIFFERENT_EVENT": 0})
            W(f"| {v} | {row['SAME_EVENT']} | {row['DIFFERENT_EVENT']} |")
        W("")
        # Binary collapse: MERGE+UPDATE = "duplicate-like" (positive), NEW = negative.
        # Caveat: an UPDATE is legitimately "same underlying event, new info" -- the
        # grader's binary SAME_EVENT/DIFFERENT_EVENT label doesn't distinguish
        # MERGE-worthy from UPDATE-worthy, so both count as "correct" against a
        # SAME_EVENT ground truth here. This is the honest, coarser cut; see the
        # raw 3x2 matrix above for the finer-grained picture.
        tp = matrix.get("MERGE", {}).get("SAME_EVENT", 0) + matrix.get("UPDATE", {}).get("SAME_EVENT", 0)
        fn = matrix.get("NEW", {}).get("SAME_EVENT", 0)
        fp = matrix.get("MERGE", {}).get("DIFFERENT_EVENT", 0) + matrix.get("UPDATE", {}).get("DIFFERENT_EVENT", 0)
        tn = matrix.get("NEW", {}).get("DIFFERENT_EVENT", 0)
        n = tp + fn + fp + tn
        precision = tp / (tp + fp) if (tp + fp) else float("nan")
        recall = tp / (tp + fn) if (tp + fn) else float("nan")
        accuracy = (tp + tn) / n if n else float("nan")
        W(
            "**Binary collapse (MERGE+UPDATE = 'flagged as duplicate-like' vs grader SAME_EVENT):** "
            "caveat above -- this treats UPDATE and MERGE as equally 'correct' against a SAME_EVENT "
            "label, since the grader doesn't distinguish MERGE-worthy from UPDATE-worthy pairs."
        )
        W(f"- Precision: {precision:.3f}  (of pairs flagged MERGE/UPDATE, {pct(tp, tp+fp)} were really SAME_EVENT)")
        W(f"- Recall: {recall:.3f}  (of grader SAME_EVENT pairs, {pct(tp, tp+fn)} were caught as MERGE/UPDATE)")
        W(f"- Overall accuracy: {accuracy:.3f} ({tp+tn}/{n})")
    else:
        W("No grey-zone pairs with a usable grader label -- cannot compute a confusion matrix.")
    W("")

    # ── §3 false-positive rate (cross-topic) ─────────────────────────────────
    W("## 3. False-positive rate (certain true-negative cross-topic pairs)")
    W("")
    if cross:
        gte_grey = [p for p in cross if p.cosine >= GREY_ZONE_MIN]
        misjudged = [p for p in cross if p.predicted in ("MERGE", "UPDATE")]
        grader_fooled = [p for p in cross if p.grader_reason and "grader said SAME_EVENT" in (p.grader_reason or "")]
        W(f"Of {len(cross)} cross-topic pairs (unrelated topics -- certain ground truth: DIFFERENT_EVENT):")
        W(f"- **Scored >= grey-zone threshold ({GREY_ZONE_MIN}):** {len(gte_grey)}/{len(cross)} = **{pct(len(gte_grey), len(cross))}**")
        W(f"- **Misjudged as duplicate by the real pipeline (auto-merge cosine OR JudgeLLM MERGE/UPDATE):** "
          f"{len(misjudged)}/{len(cross)} = **{pct(len(misjudged), len(cross))}** -- real news would have been silently dropped")
        W(f"- Independent grader also said SAME_EVENT (grader itself fooled, ground truth still DIFFERENT_EVENT by construction): {len(grader_fooled)}/{len(cross)}")
        if misjudged:
            W("")
            W("**Misjudged cross-topic pairs (real, distinct topics, pipeline called them a duplicate):**")
            for p in misjudged:
                W(f"  - [{p.topic_a}] \"{p.new_alpha.alpha_text[:80]}\" <-> [{p.topic_b}] \"{p.match_alpha.alpha_text[:80]}\" "
                  f"(cosine={p.cosine:.3f}, predicted={p.predicted})")
    else:
        W("No cross-topic pairs were built (insufficient topic diversity in the corpus).")
    W("")

    # ── §4 auto-merge zone sanity check ──────────────────────────────────────
    W("## 4. Auto-merge zone (cosine >= 0.97) sanity check")
    W("")
    auto_merge_pairs = [p for p in pairs if p.zone == "AUTO_MERGE"]
    W(f"Pairs auto-merged without any LLM call: {len(auto_merge_pairs)}")
    if auto_merge_pairs:
        am_labeled = [p for p in auto_merge_pairs if p.grader_label]
        am_wrong = [p for p in am_labeled if p.grader_label == "DIFFERENT_EVENT"]
        W(f"- Of those with a ground-truth/grader label: {len(am_labeled)}; "
          f"disagreed with auto-merge (grader/construction says DIFFERENT_EVENT): "
          f"{len(am_wrong)}/{len(am_labeled)} = {pct(len(am_wrong), len(am_labeled)) if am_labeled else 'n/a'}")
        if am_wrong:
            for p in am_wrong:
                W(f"  - cosine={p.cosine:.3f} [{p.category}] \"{p.new_alpha.alpha_text[:80]}\" <-> \"{p.match_alpha.alpha_text[:80]}\"")
    W("")

    # ── §5 end-to-end pipeline accuracy ──────────────────────────────────────
    W("## 5. End-to-end pipeline accuracy (true duplicates: caught vs leaked)")
    W("")
    if same:
        caught = [p for p in same if p.predicted in ("AUTO_MERGE", "MERGE", "UPDATE")]
        leaked_e2e = [p for p in same if p.predicted in ("AUTO_NEW", "NEW")]
        W(f"Of {len(same)} grader-labeled true duplicates (SAME_EVENT):")
        W(f"- **Caught by some stage** (auto-merge cosine gate OR JudgeLLM MERGE/UPDATE): "
          f"{len(caught)}/{len(same)} = **{pct(len(caught), len(same))}**")
        W(f"- **Leaked through as NEW** (auto-new cosine gate OR JudgeLLM NEW): "
          f"{len(leaked_e2e)}/{len(same)} = **{pct(len(leaked_e2e), len(same))}**")
        by_stage: Dict[str, int] = {}
        for p in caught:
            by_stage[p.predicted] = by_stage.get(p.predicted, 0) + 1
        W(f"- Breakdown of catches: " + ", ".join(f"{k}={v}" for k, v in sorted(by_stage.items())))
    else:
        W("No grader-labeled SAME_EVENT pairs to compute end-to-end accuracy.")
    W("")

    # ── errors ────────────────────────────────────────────────────────────────
    errored = [p for p in pairs if p.error]
    if errored:
        W(f"## Errors during this run ({len(errored)} pairs affected)")
        W("")
        for p in errored[:20]:
            W(f"- [{p.category}] {p.error}")
        if len(errored) > 20:
            W(f"- ... and {len(errored) - 20} more")
        W("")

    # ── please-eyeball list ──────────────────────────────────────────────────
    W("## Please eyeball these (most important/ambiguous pairs)")
    W("")
    W(
        "Selected by proximity to a decision boundary (cosine near 0.75/0.97) or "
        "predicted/grader disagreement -- the cases where a wrong ground-truth label "
        "or a wrong judge call would matter most."
    )
    W("")
    interesting = []
    for p in pairs:
        boundary_dist = min(abs(p.cosine - GREY_ZONE_MIN), abs(p.cosine - AUTO_MERGE_THRESHOLD))
        disagree = 0
        if p.grader_label and p.predicted:
            said_dup = p.predicted in ("AUTO_MERGE", "MERGE", "UPDATE")
            said_same = p.grader_label == "SAME_EVENT"
            disagree = 1 if said_dup != said_same else 0
        interesting.append((disagree, -boundary_dist, p))
    interesting.sort(key=lambda t: (-t[0], t[1]))
    for i, (disagree, _, p) in enumerate(interesting[:20], 1):
        flag = "DISAGREEMENT" if disagree else "near boundary"
        W(
            f"{i}. [{flag}] category={p.category} cosine={p.cosine:.3f} zone={p.zone} "
            f"predicted={p.predicted} grader={p.grader_label}\n"
            f"   A ({p.topic_a}): \"{p.new_alpha.alpha_text}\"\n"
            f"   B ({p.topic_b}): \"{p.match_alpha.alpha_text}\"\n"
            f"   grader reason: {p.grader_reason}\n"
        )

    return "\n".join(lines)


# ── main ──────────────────────────────────────────────────────────────────────────

def slugify(topics: List[str]) -> str:
    return "judge-accuracy-audit"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--topics", type=str, default=None, help="Comma-separated topic list. Default: built-in diverse set.")
    ap.add_argument("--load-corpus", type=str, default=None, help="Path to a previously saved corpus JSON -- skip collection.")
    ap.add_argument("--skip-grading", action="store_true", help="Reuse grader labels already present in a loaded corpus's pairs cache (if any); otherwise still grades.")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--sleep", type=float, default=2.0, help="Seconds between collector calls.")
    ap.add_argument("--out-dir", type=str, default=os.path.join(ROOT, "docs", "benchmarks"))
    ap.add_argument(
        "--search-model", type=str, default=None,
        help=(
            "Override the model used for the gemini_search (grounded) step, without "
            "touching config/settings.py -- routes around a specific model's exhausted "
            "quota bucket. Must be a model ID already verified live somewhere in this "
            "project's LLM_CONFIG (per the verify-llm-models skill) -- do not pass a "
            "guessed model name."
        ),
    )
    ap.add_argument("--note", type=str, default=None, help="Extra free-text note prepended to the report (e.g. manual context on a blocker).")
    ap.add_argument("--max-wait-hours", type=float, default=9.0, help="Per-call retry budget on quota-like (429/RESOURCE_EXHAUSTED) errors before giving up on a topic.")
    ap.add_argument("--retry-initial-wait", type=float, default=120.0, help="Seconds to wait before the first retry after a quota-like error.")
    ap.add_argument("--retry-max-wait", type=float, default=900.0, help="Cap (seconds) on the exponential backoff between retries.")
    args = ap.parse_args()

    topics = [t.strip() for t in args.topics.split(",")] if args.topics else DEFAULT_TOPICS
    rng = random.Random(args.seed)

    data_dir = os.path.join(args.out_dir, "_data")
    os.makedirs(data_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    corpus_path = args.load_corpus or os.path.join(data_dir, f"{date_str}_judge-accuracy-corpus.json")

    llm = LLMClient()
    if args.search_model:
        cfg = dict(llm._config)
        cfg["gemini_search"] = {"provider": "gemini", "model": args.search_model}
        llm._config = cfg
        print(f"[main] gemini_search step overridden to model={args.search_model!r} (local override only, config/settings.py untouched)")

    # ── stage 1: corpus (resumable -- skips topics already present, saves after each) ──
    corpus: Dict[str, dict] = {}
    if args.load_corpus and os.path.exists(args.load_corpus):
        print(f"[main] loading existing corpus from {args.load_corpus}")
        with open(args.load_corpus, "r", encoding="utf-8") as f:
            corpus = json.load(f)
        corpus_path = args.load_corpus  # keep saving progress to the same file
    collection_error: Optional[str] = None
    missing = [t for t in topics if t not in corpus]
    if missing:
        print(f"[main] collecting corpus for {len(missing)}/{len(topics)} topics not yet in corpus: {missing}")
        try:
            corpus = collect_corpus(
                topics, llm, sleep_s=args.sleep, corpus=corpus, save_path=corpus_path,
                max_wait_hours=args.max_wait_hours,
                retry_initial_wait_s=args.retry_initial_wait,
                retry_max_wait_s=args.retry_max_wait,
            )
        except Exception as exc:
            # Don't lose whatever DID succeed (already saved to corpus_path by collect_corpus
            # on every topic) -- fall through to reporting on the partial corpus instead of
            # crashing, and record exactly what happened for the report.
            collection_error = str(exc)
            still_missing = [t for t in topics if t not in corpus]
            print(f"[main] collection stopped early: {exc!r}")
            print(f"[main] proceeding with the {len(corpus)}/{len(topics)} topics collected before the failure "
                  f"(missing: {still_missing})")
    else:
        print("[main] all requested topics already present in loaded corpus -- no new collect() calls.")
    print(f"[main] corpus at {corpus_path} ({len(corpus)} topics)")

    if not corpus:
        print(f"[main] BLOCKED: zero topics collected. Last error: {collection_error}")
        sys.exit(1)

    topic_alphas = load_corpus_alphas(corpus)
    total_facts = sum(len(runs.get(k, [])) for runs in topic_alphas.values() for k in ("run_a", "run_b", "run_wide"))
    print(f"[main] corpus loaded: {total_facts} total facts across {len(topic_alphas)} topics")

    # ── stage: embed ──
    embed_corpus(llm, topic_alphas)

    # ── stage 2: pairs ──
    pairs = build_pairs(topic_alphas, rng)
    print(f"[main] built {len(pairs)} pairs "
          f"(same_day_rescan={sum(1 for p in pairs if p.category=='same_day_rescan')}, "
          f"multi_day_proxy={sum(1 for p in pairs if p.category=='multi_day_proxy')}, "
          f"cross_topic={sum(1 for p in pairs if p.category=='cross_topic')})")

    if not pairs:
        print("[main] BLOCKED: zero pairs built -- corpus likely came back empty from the collector. "
              "Check GOOGLE_API_KEY quota / GeminiSearchCollector output above.")
        sys.exit(1)

    # ── stage 3: grade ──
    print("[main] grading pairs (separate LLM call, second opinion)...")
    grade_pairs(llm, pairs)

    # ── stage 4: real pipeline ──
    judge = JudgeLLM(llm=llm)
    print("[main] running real cosine gate + real JudgeLLM...")
    run_pipeline(judge, pairs)

    # save full pairs dump (for reproducibility / later --load-corpus reuse of labels)
    pairs_dump_path = os.path.join(data_dir, f"{date_str}_judge-accuracy-pairs.json")
    with open(pairs_dump_path, "w", encoding="utf-8") as f:
        json.dump([
            {
                "category": p.category, "topic_a": p.topic_a, "topic_b": p.topic_b,
                "new_alpha_text": p.new_alpha.alpha_text, "match_alpha_text": p.match_alpha.alpha_text,
                "cosine": p.cosine, "grader_label": p.grader_label, "grader_reason": p.grader_reason,
                "zone": p.zone, "predicted": p.predicted, "judge_delta": p.judge_delta, "error": p.error,
            }
            for p in pairs
        ], f, indent=2)
    print(f"[main] pairs dump saved to {pairs_dump_path}")

    # ── stage 5: report ──
    still_missing = [t for t in topics if t not in corpus]
    auto_note_parts = []
    if still_missing or collection_error:
        auto_note_parts.append(
            f"**Corpus shortfall:** requested {len(topics)} topics ({topics}), only "
            f"{len(corpus)} collected ({list(corpus.keys())}); missing: {still_missing}."
        )
        if collection_error:
            auto_note_parts.append(f"**Collection stopped with:** `{collection_error}`")
        auto_note_parts.append(
            "This run's percentages are computed on a SMALLER corpus than the intended "
            "80-120 pairs / 5-8 topics -- treat them as a directional first read, not a "
            "final verdict, until re-run with the full topic set. Re-run with "
            "`python scripts/judge_accuracy_audit.py --load-corpus <this corpus path>` "
            "once the blocker clears -- already-collected topics are skipped automatically "
            "(resume), only the missing ones trigger new collect() calls."
        )
    if args.note:
        auto_note_parts.append(args.note)
    run_note = "\n\n".join(auto_note_parts) if auto_note_parts else None

    report = build_report(pairs, topics, run_note=run_note)
    print("\n\n" + "=" * 100 + "\n")
    print(report)

    report_path = os.path.join(args.out_dir, f"{date_str}_{slugify(topics)}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n[main] report written to {report_path}")


if __name__ == "__main__":
    main()
