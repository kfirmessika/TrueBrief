"""
scripts/redteam_embedding_benchmark.py

Runs the 131-case arbiter red-team set through the embedding benchmark framework
(tests/test_embedding_benchmark.py) -- producing the same metrics as the handcrafted
87-pair benchmark, but on adversarial real cases.

For each case:
  text_a = alpha_text (the new fact being judged)
  text_b = the stored known_fact text matched by the arbiter (fetched from DB by
           matched_alpha_id from the LOCAL-EMBED results JSON -- this is the real
           comparison the arbiter makes)

Skips AMBIGUOUS cases (2 exist in the 131).

Usage:
  python scripts/redteam_embedding_benchmark.py
  python scripts/redteam_embedding_benchmark.py --provider gemini  (if quota allows)
"""

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

sys.path.insert(0, ROOT)

from tests.test_embedding_benchmark import (
    Pair, PairResult, classify, cosine, _summarize, print_report,
    get_local_embedder, get_gemini_client,
    gemini_cost_per_text, local_cost_per_text,
    JUDGE_COST_PER_CALL_USD, LOCAL_MS_PER_TEXT_MEASURED,
    AUTO_MERGE_THRESHOLD, SAME_DAY_DUP_THRESHOLD, GREY_ZONE_MIN,
)

RESULTS_JSON = os.path.join(
    ROOT, "docs", "benchmarks", "_data",
    "2026-08-13_arbiter-redteam-results-LOCAL-EMBED.json"
)

# Map expected_decision from the red-team format to benchmark labels
def _map_label(decision: str) -> str | None:
    if decision == "DUPLICATE":
        return "DUPLICATE"
    if decision == "UPDATE":
        return "UPDATE"
    if decision == "NEW":
        return "NEW"
    return None  # AMBIGUOUS -> skip


def fetch_fact_texts(matched_ids: list[str]) -> dict[str, str]:
    """Fetch alpha_text for each matched_alpha_id from Supabase."""
    from truebrief.ledger.database import get_supabase
    sb = get_supabase()
    ids = [i for i in matched_ids if i]
    if not ids:
        return {}
    resp = sb.table("known_facts").select("id, alpha_text").in_("id", ids).execute()
    return {row["id"]: row["alpha_text"] for row in (resp.data or [])}


def build_pairs(results_json: str) -> list[Pair]:
    data = json.load(open(results_json))
    raw = data["results"]

    # Collect all matched_alpha_ids to batch-fetch
    matched_ids = [r.get("matched_alpha_id") for r in raw if r.get("matched_alpha_id")]
    print(f"Fetching {len(set(matched_ids))} known_fact texts from DB...")
    fact_texts = fetch_fact_texts(list(set(matched_ids)))
    print(f"  Got {len(fact_texts)} texts.")

    pairs = []
    skipped = []
    for r in raw:
        label = _map_label(r["expected_decision"])
        if label is None:
            skipped.append(r["id"])
            continue
        mid = r.get("matched_alpha_id")
        text_b = fact_texts.get(mid) if mid else None
        if not text_b:
            skipped.append(r["id"])
            continue
        pairs.append(Pair(
            id=r["id"],
            text_a=r["alpha_text"],
            text_b=text_b,
            label=label,
            source="redteam",
            note=f"{r['category']} | {r.get('note', '')}",
        ))

    if skipped:
        print(f"  Skipped {len(skipped)} cases (AMBIGUOUS or no matched fact): {skipped}")
    print(f"  Built {len(pairs)} pairs.\n")
    return pairs


def run_local(pairs: list[Pair]) -> tuple[list[PairResult], dict]:
    embedder = get_local_embedder()
    texts = [p.text_a for p in pairs] + [p.text_b for p in pairs]
    t0 = time.perf_counter()
    all_vecs = embedder.embed_batch(texts)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    ms_per = elapsed_ms / len(texts)

    vecs_a = all_vecs[:len(pairs)]
    vecs_b = all_vecs[len(pairs):]
    results = []
    for pair, va, vb in zip(pairs, vecs_a, vecs_b):
        score = cosine(va, vb)
        predicted = classify(score)
        correct = True if predicted == "GREY" else (predicted == pair.label)
        results.append(PairResult(
            pair=pair, score=score, predicted=predicted, correct=correct,
            embed_cost_a=local_cost_per_text(ms_per),
            embed_cost_b=local_cost_per_text(ms_per),
            latency_ms=ms_per,
        ))
    summary = _summarize(results, "local", ms_per)
    return results, summary


def run_gemini(pairs: list[Pair], req_per_min: int = 90, use_backup_key: bool = False) -> tuple[list[PairResult], dict]:
    import time as _t
    backup = os.environ.get("GOOGLE_API_KEY_BACKUP", "") if use_backup_key else ""
    if backup:
        print(f"  Using GOOGLE_API_KEY_BACKUP")
        from google import genai as _genai
        _raw_client = _genai.Client(api_key=backup)
        class _DirectClient:
            def embed(self, text):
                resp = _raw_client.models.embed_content(
                    model="models/gemini-embedding-2", contents=text)
                return resp.embeddings[0].values
        client = _DirectClient()
    else:
        client = get_gemini_client()
    delay = 60.0 / req_per_min
    texts = [p.text_a for p in pairs] + [p.text_b for p in pairs]
    vecs = []
    t_start = _t.perf_counter()
    for i, text in enumerate(texts):
        t0 = _t.perf_counter()
        vecs.append(client.embed(text))
        elapsed = _t.perf_counter() - t0
        if elapsed < delay:
            _t.sleep(delay - elapsed)
        if (i + 1) % 20 == 0:
            print(f"    {i+1}/{len(texts)} embedded...", flush=True)
    ms_per = (_t.perf_counter() - t_start) * 1000 / len(texts)

    vecs_a, vecs_b = vecs[:len(pairs)], vecs[len(pairs):]
    results = []
    for pair, va, vb in zip(pairs, vecs_a, vecs_b):
        score = cosine(va, vb)
        predicted = classify(score)
        correct = True if predicted == "GREY" else (predicted == pair.label)
        results.append(PairResult(
            pair=pair, score=score, predicted=predicted, correct=correct,
            embed_cost_a=gemini_cost_per_text(pair.text_a, paid_tier=True),
            embed_cost_b=gemini_cost_per_text(pair.text_b, paid_tier=True),
            latency_ms=ms_per,
        ))
    summary = _summarize(results, "gemini", ms_per)
    return results, summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="local", choices=["local", "gemini"])
    args = parser.parse_args()

    print("=" * 72)
    print("  RED-TEAM EMBEDDING BENCHMARK (131 cases, real arbiter pairs)")
    print(f"  Provider: {args.provider.upper()}")
    print(f"  text_a = alpha_text (new fact)  |  text_b = matched stored fact from DB")
    print("=" * 72 + "\n")

    pairs = build_pairs(RESULTS_JSON)

    if args.provider == "local":
        print(f"Running LOCAL embedder on {len(pairs)} pairs...")
        results, summary = run_local(pairs)
    else:
        print(f"Running GEMINI embedder on {len(pairs)} pairs (rate-limited)...")
        results, summary = run_gemini(pairs, use_backup_key=True)

    print_report(results, summary, f"{args.provider.upper()} -- RED-TEAM 131 CASES")

    # Per-category breakdown
    from collections import defaultdict
    cat_stats = defaultdict(lambda: dict(n=0, auto=0, grey=0, correct=0, unrescuable=0))
    for r in results:
        cat = r.pair.id[:2]
        d = cat_stats[cat]
        d["n"] += 1
        if r.predicted == "GREY":
            d["grey"] += 1
        else:
            d["auto"] += 1
            if r.correct:
                d["correct"] += 1
            elif r.score >= AUTO_MERGE_THRESHOLD:
                d["unrescuable"] += 1

    cat_labels = {
        "C1": "EXACT_DUPLICATE", "C2": "PARAPHRASE_DUP", "C3": "PARAPHRASE_DATEDR",
        "C4": "TALLY_UPDATE", "C5": "NUMERIC_CHANGE", "C6": "ENTITY_ALIAS_DUP",
        "C7": "ANTONYM_GAP", "C8": "NUMERIC_CONTRADICT", "C9": "PROMPT_INJECTION",
        "C10": "FALSE_DEDUP", "C11": "MISSING_DATE", "C12": "INTRA_BATCH",
    }
    print("\n  Per-category breakdown:")
    print(f"  {'Cat':<4} {'Label':<20} {'N':>4} {'Auto%':>6} {'Grey%':>6} "
          f"{'AutoCorr%':>10} {'Unrescuable':>12}")
    for cat in sorted(cat_stats):
        d = cat_stats[cat]
        n = d["n"]
        if n == 0:
            continue
        auto = d["auto"]
        grey_p = 100 * d["grey"] / n
        auto_p = 100 * auto / n
        corr_p = 100 * d["correct"] / auto if auto else 0
        lbl = cat_labels.get(cat, cat)
        print(f"  {cat:<4} {lbl:<20} {n:>4} {auto_p:>6.0f}% {grey_p:>6.0f}% "
              f"{corr_p:>10.0f}% {d['unrescuable']:>12}")


if __name__ == "__main__":
    main()
