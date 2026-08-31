"""
Embedding Comparison — scripts/embedding_comparison.py

Runs both LOCAL and GEMINI embedders on the full benchmark dataset and prints
a comprehensive side-by-side report: accuracy, PR curves, costs, latency, errors.

Usage:
  python scripts/embedding_comparison.py

Requires:
  - sentence-transformers installed (local)
  - GEMINI_API_KEY in .env (gemini)
  - EMBED_PROVIDER env var is overridden internally; no need to set it

Pricing used (verified 2026-08-30):
  Gemini embedding-2 PAID tier: $0.20 / 1M tokens
  Judge LLM (gemini-3.1-flash-lite): $0.0000797 / call (measured from DB)
  Local CPU (Railway 2 vCPU): $0.000463 / vCPU-min; ~10 ms/text amortised
  LEDGER_FETCH_LIMIT = 3 (hard cap in arbiter.py)
"""

import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Load .env
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import numpy as np
import time as _time
from collections import Counter

# Import benchmark internals
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tests.test_embedding_benchmark import (
    PROD_PAIRS, ADV_PAIRS, ALL_PAIRS,
    pr_curve, print_report, print_comparison, _summarize,
    pipeline_cost, JUDGE_COST_PER_CALL_USD, LEDGER_FETCH_LIMIT,
    GEMINI_EMBED_COST_PER_TOKEN_PAID, CHARS_PER_TOKEN,
    RAILWAY_VCPU_COST_PER_MIN, RAILWAY_VCPU_ALLOC, LOCAL_MS_PER_TEXT_MEASURED,
    AUTO_MERGE_THRESHOLD, SAME_DAY_DUP_THRESHOLD, GREY_ZONE_MIN,
    classify, cosine, PairResult, get_local_embedder, get_gemini_client,
    gemini_cost_per_text, local_cost_per_text,
)


def run_gemini_rate_limited(pairs, req_per_min=90):
    """Embed pairs one text at a time with rate limiting to avoid 429s."""
    client = get_gemini_client()
    delay = 60.0 / req_per_min  # seconds between requests
    texts = [p.text_a for p in pairs] + [p.text_b for p in pairs]
    vecs = []
    t_start = _time.perf_counter()
    for i, text in enumerate(texts):
        t0 = _time.perf_counter()
        vecs.append(client.embed(text))
        elapsed = _time.perf_counter() - t0
        if elapsed < delay:
            _time.sleep(delay - elapsed)
        if (i + 1) % 20 == 0:
            print(f"    {i+1}/{len(texts)} embedded...", flush=True)
    total_ms = (_time.perf_counter() - t_start) * 1000
    ms_per = total_ms / len(texts)

    vecs_a, vecs_b = vecs[:len(pairs)], vecs[len(pairs):]
    results = []
    for pair, va, vb in zip(pairs, vecs_a, vecs_b):
        score = cosine(va, vb)
        predicted = classify(score)
        results.append(PairResult(
            pair=pair, score=score, predicted=predicted,
            correct=(predicted == pair.label),
            embed_cost_a=gemini_cost_per_text(pair.text_a, paid_tier=True),
            embed_cost_b=gemini_cost_per_text(pair.text_b, paid_tier=True),
            latency_ms=ms_per,
        ))
    summary = _summarize(results, "gemini", ms_per)
    return results, summary


def run_all():
    from tests.test_embedding_benchmark import run_benchmark

    print("\n" + "="*72)
    print("  TRUEBRIEF EMBEDDING COMPARISON: LOCAL vs GEMINI (PAID TIER)")
    print("  Dataset: 60 production (DB-sourced) + 27 adversarial = 87 pairs")
    print("  Gemini pricing: $0.20/M tokens (paid tier, verified 2026-08-30)")
    print("  Judge LLM cost: $0.0000797/call (measured from 1,756 live DB calls)")
    print("  Gemini rate-limited to 90 req/min to avoid free-tier 429s")
    print("="*72)

    # ── Run local ────────────────────────────────────────────────────────────
    print("\n[1/4] Running LOCAL embedder on production set...")
    t0 = time.perf_counter()
    local_prod_r, local_prod_s = run_benchmark(PROD_PAIRS, "local")
    local_prod_time = time.perf_counter() - t0

    print("[2/4] Running LOCAL embedder on adversarial set...")
    t0 = time.perf_counter()
    local_adv_r, local_adv_s = run_benchmark(ADV_PAIRS, "local")
    local_adv_time = time.perf_counter() - t0

    # ── Reports so far (printed now, not just at the end) ────────────────────
    print_report(local_prod_r, local_prod_s, "LOCAL -- PRODUCTION (60 pairs)")
    print_report(local_adv_r, local_adv_s, "LOCAL -- ADVERSARIAL (27 pairs)")

    # ── Run Gemini (rate-limited sequential to avoid 429) ────────────────────
    # 2026-08-30 fix: this used to crash uncaught on the free-tier daily embedding
    # quota (separate limit from grounding-search quota, 1000 req/day) and lose the
    # LOCAL results computed above along with it. Catch it, report what we have.
    gemini_prod_r = gemini_prod_s = gemini_adv_r = gemini_adv_s = None
    gemini_failed = False
    try:
        print("[3/4] Running GEMINI embedder on production set (rate-limited, ~2 min)...")
        t0 = time.perf_counter()
        gemini_prod_r, gemini_prod_s = run_gemini_rate_limited(PROD_PAIRS)
        gemini_prod_time = time.perf_counter() - t0
        print_report(gemini_prod_r, gemini_prod_s, "GEMINI -- PRODUCTION (60 pairs)")

        print("[4/4] Running GEMINI embedder on adversarial set (rate-limited, ~1 min)...")
        t0 = time.perf_counter()
        gemini_adv_r, gemini_adv_s = run_gemini_rate_limited(ADV_PAIRS)
        gemini_adv_time = time.perf_counter() - t0
        print_report(gemini_adv_r, gemini_adv_s, "GEMINI -- ADVERSARIAL (27 pairs)")
    except Exception as exc:
        gemini_failed = True
        print(f"\n{'='*72}\n  GEMINI EMBEDDING RUN FAILED: {exc}\n"
              f"  (LOCAL results above are unaffected -- reporting local-only below.)\n{'='*72}\n")

    if gemini_failed:
        print(f"\n{'='*72}\n  BOTTOM LINE (LOCAL ONLY -- GEMINI QUOTA-BLOCKED)\n{'='*72}")
        print("  Could not compare -- Gemini's free-tier daily embedding quota "
              "(1000 req/day) is exhausted for today.")
        print("  LOCAL embedder ran to completion with zero quota risk (see reports above).")
        return

    # ── PR Curves ────────────────────────────────────────────────────────────
    print(f"\n{'='*72}")
    print("  PR CURVE AUC (DUPLICATE class, production set)")
    print(f"{'='*72}")
    lc = pr_curve(local_prod_r, "DUPLICATE")
    gc = pr_curve(gemini_prod_r, "DUPLICATE")
    print(f"  Local  AUC: {lc['auc']:.4f}")
    print(f"  Gemini AUC: {gc['auc']:.4f}")
    print(f"  Gap:        {(gc['auc']-lc['auc']):+.4f}  ({'Gemini better' if gc['auc'] > lc['auc'] else 'Local better or equal'})")

    # Find the DUPLICATE threshold where escalation rate approaches 75%
    print(f"\n  Threshold where escalation rate ~= 75% (what dup cutoff achieves that):")
    def find_threshold_at_escalation(results, target=0.75):
        best = {"t": None, "escal": None, "auto_acc": None}
        best_diff = 999
        for t in np.arange(0.50, 1.00, 0.01):
            # At this threshold: score >= t -> auto-DUPLICATE; score < GREY_ZONE_MIN -> auto-NEW
            n_auto_dup = sum(1 for r in results if r.score >= t)
            n_auto_new = sum(1 for r in results if r.score < GREY_ZONE_MIN)
            n_grey = sum(1 for r in results if GREY_ZONE_MIN <= r.score < t)
            n = len(results)
            escal = n_grey / n
            # Accuracy among auto-decided pairs at this threshold
            correct = sum(1 for r in results
                          if (r.score >= t and r.pair.label == "DUPLICATE") or
                             (r.score < GREY_ZONE_MIN and r.pair.label == "NEW"))
            auto = n_auto_dup + n_auto_new
            acc_auto = correct / auto if auto else 0.0
            diff = abs(escal - target)
            if diff < best_diff:
                best_diff = diff
                best = {"t": round(t, 2), "escal": escal, "auto_acc": acc_auto}
        return best
    for label, results in [("Local", local_prod_r), ("Gemini", gemini_prod_r)]:
        b = find_threshold_at_escalation(results, target=0.75)
        print(f"  {label}: dup_threshold={b['t']:.2f}, escalation={b['escal']*100:.1f}%, "
              f"auto-layer-acc={b['auto_acc']*100:.1f}%")

    # ── Full cost breakdown ───────────────────────────────────────────────────
    print(f"\n{'='*72}")
    print("  COST BREAKDOWN (per story, N=3 candidates, paid-tier Gemini)")
    print(f"{'='*72}")

    avg_text_len = sum(len(p.text_a) + len(p.text_b) for p in PROD_PAIRS) / (2 * len(PROD_PAIRS))
    gemini_embed_per_text = (avg_text_len / CHARS_PER_TOKEN) * GEMINI_EMBED_COST_PER_TOKEN_PAID
    local_embed_per_text  = (LOCAL_MS_PER_TEXT_MEASURED / 1000 / 60) * RAILWAY_VCPU_COST_PER_MIN * RAILWAY_VCPU_ALLOC

    local_escal  = local_prod_s["escalation_rate"]
    gemini_escal = gemini_prod_s["escalation_rate"]

    local_pipeline  = LEDGER_FETCH_LIMIT * local_embed_per_text  + local_escal  * LEDGER_FETCH_LIMIT * JUDGE_COST_PER_CALL_USD
    gemini_pipeline = LEDGER_FETCH_LIMIT * gemini_embed_per_text + gemini_escal * LEDGER_FETCH_LIMIT * JUDGE_COST_PER_CALL_USD

    print(f"\n  Average text length: {avg_text_len:.0f} chars")
    print(f"\n  {'Component':<40} {'LOCAL':>14} {'GEMINI':>14}")
    print(f"  {'-'*70}")
    print(f"  {'Embed cost per text (paid tier)':<40} ${local_embed_per_text:>12.2e} ${gemini_embed_per_text:>12.2e}")
    print(f"  {'Embed cost for N=3 candidates':<40} ${local_embed_per_text*3:>12.2e} ${gemini_embed_per_text*3:>12.2e}")
    print(f"  {'Escalation rate (% needing LLM)':<40} {local_escal*100:>13.1f}% {gemini_escal*100:>13.1f}%")
    print(f"  {'LLM judge calls per story (N=3)':<40} {local_escal*3:>14.2f} {gemini_escal*3:>14.2f}")
    print(f"  {'LLM cost per story':<40} ${local_escal*3*JUDGE_COST_PER_CALL_USD:>12.6f} ${gemini_escal*3*JUDGE_COST_PER_CALL_USD:>12.6f}")
    print(f"  {'TOTAL pipeline cost per story':<40} ${local_pipeline:>12.6f} ${gemini_pipeline:>12.6f}")
    print(f"\n  Embed is {local_embed_per_text*3 / local_pipeline * 100:.2f}% of local total cost")
    print(f"  Embed is {gemini_embed_per_text*3 / gemini_pipeline * 100:.2f}% of gemini total cost")
    print(f"  LLM is  {local_escal*3*JUDGE_COST_PER_CALL_USD / local_pipeline * 100:.2f}% of local total cost")
    print(f"  LLM is  {gemini_escal*3*JUDGE_COST_PER_CALL_USD / gemini_pipeline * 100:.2f}% of gemini total cost")

    # Scale projections
    print(f"\n  Scale projections (total pipeline cost, excl. other pipeline stages):")
    print(f"  {'Scenario':<35} {'LOCAL':>14} {'GEMINI':>14}")
    print(f"  {'-'*65}")
    for label, n_stories in [("100 stories/day (1 topic)", 100),
                               ("1,000 stories/day (10 topics)", 1000),
                               ("10,000 stories/day (100 topics)", 10000)]:
        lc_ = local_pipeline * n_stories
        gc_ = gemini_pipeline * n_stories
        print(f"  {label:<35} ${lc_:>12.4f} ${gc_:>12.4f}")

    # ── Latency breakdown ─────────────────────────────────────────────────────
    print(f"\n{'='*72}")
    print("  LATENCY BREAKDOWN")
    print(f"{'='*72}")
    print(f"\n  {'Measurement':<45} {'LOCAL':>12} {'GEMINI':>12}")
    print(f"  {'-'*71}")
    print(f"  {'Embed batch time (prod set, wall clock)':<45} {local_prod_time:>11.2f}s {gemini_prod_time:>11.2f}s")
    print(f"  {'Embed batch time (adv set, wall clock)':<45} {local_adv_time:>11.2f}s {gemini_adv_time:>11.2f}s")
    print(f"  {'Per-text latency (amortised)':<45} {local_prod_s['latency_per_text_ms']:>11.1f}ms {gemini_prod_s['latency_per_text_ms']:>11.1f}ms")
    print(f"  {'Per-story latency (N=3 embed)':<45} {local_prod_s['latency_per_text_ms']*3:>11.1f}ms {gemini_prod_s['latency_per_text_ms']*3:>11.1f}ms")
    print(f"  {'Judge LLM latency (avg, from DB)':<45} {'~500ms':>12} {'~500ms':>12}")

    # ── Side-by-side summary ──────────────────────────────────────────────────
    print_comparison(local_prod_s, gemini_prod_s)

    # ── Failure catalogue ─────────────────────────────────────────────────────
    def _rescue_status(r):
        if r.predicted == "GREY":
            return "escalated to LLM (correct behavior)"
        if r.score >= AUTO_MERGE_THRESHOLD:
            return "UNRESCUABLE — auto-merged, no LLM call, wrong answer reaches user"
        return f"LLM-rescuable (grey zone, +${JUDGE_COST_PER_CALL_USD:.7f} per candidate)"

    def _print_failure_catalogue(adv_r, provider_label):
        print(f"\n{'='*72}")
        print(f"  FAILURE CATALOGUE (adversarial set, {provider_label})")
        print(f"{'='*72}")
        # Only auto-decided wrong pairs — GREY pairs are correct escalation, not errors
        auto_errors = [r for r in adv_r if r.predicted != "GREY" and not r.correct]
        known = [r for r in auto_errors if "KNOWN BLIND SPOT" in r.pair.note]
        other = [r for r in auto_errors if "KNOWN BLIND SPOT" not in r.pair.note]

        print(f"\n  Auto-decision errors on known blind spots:")
        for r in known:
            print(f"  [{r.pair.id}] TRUE={r.pair.label} PRED={r.predicted} score={r.score:.3f}")
            print(f"    Rescue: {_rescue_status(r)}")
            print(f"    A: {r.pair.text_a[:80]}")
            print(f"    B: {r.pair.text_b[:80]}")
        if not known:
            print("  (none)")
        print(f"\n  Auto-decision errors on non-blind-spot pairs:")
        for r in other:
            print(f"  [{r.pair.id}] TRUE={r.pair.label} PRED={r.predicted} score={r.score:.3f}")
            print(f"    Rescue: {_rescue_status(r)}")
            print(f"    A: {r.pair.text_a[:80]}")
            print(f"    B: {r.pair.text_b[:80]}")
        if not other:
            print("  (none)")

        grey_wrong = [r for r in adv_r if r.predicted == "GREY" and r.pair.label == "NEW"]
        if grey_wrong:
            print(f"\n  GREY pairs where true label is NEW (LLM must catch these):")
            for r in grey_wrong:
                print(f"  [{r.pair.id}] TRUE={r.pair.label} PRED=GREY score={r.score:.3f}")
                print(f"    A: {r.pair.text_a[:80]}")
                print(f"    B: {r.pair.text_b[:80]}")

    _print_failure_catalogue(local_adv_r, "LOCAL")
    _print_failure_catalogue(gemini_adv_r, "GEMINI")

    print(f"\n{'='*72}")
    print("  BOTTOM LINE")
    print(f"{'='*72}")
    acc_diff = (gemini_prod_s['accuracy'] - local_prod_s['accuracy']) * 100
    escal_diff = (gemini_prod_s['escalation_rate'] - local_prod_s['escalation_rate']) * 100
    cost_diff = gemini_pipeline - local_pipeline
    print(f"\n  Embed-layer accuracy diff (Gemini - Local): {acc_diff:+.1f}pp on auto-decided pairs")
    print(f"  Escalation diff (Gemini - Local): {escal_diff:+.1f}pp (positive = MORE LLM calls)")
    print(f"  Pipeline cost diff per story: {cost_diff:+.6f} USD (positive = Gemini more expensive)")
    print()
    if acc_diff > 10 and escal_diff < -5:
        print("  VERDICT: Gemini is meaningfully better -- higher accuracy AND fewer LLM calls.")
        print("           The paid embedding cost is justified.")
    elif acc_diff > 10:
        print("  VERDICT: Gemini has higher accuracy but similar/worse escalation rate.")
        print("           The extra accuracy may not reduce total cost.")
    elif escal_diff < -10:
        print("  VERDICT: Gemini escalates less (fewer LLM calls) even if accuracy is similar.")
        print("           Depending on LLM cost, Gemini may be cheaper overall.")
    else:
        print("  VERDICT: No significant advantage for Gemini at paid-tier pricing.")
        print("           LOCAL is preferred: zero marginal embed cost, no quota risk, ~10ms latency.")
    print()


if __name__ == "__main__":
    run_all()
