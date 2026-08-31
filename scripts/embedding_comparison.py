"""
Embedding Comparison — scripts/embedding_comparison.py

Runs LOCAL, GEMINI, and OPENAI embedders on the full benchmark dataset and prints
a comprehensive side-by-side report: accuracy, PR curves, costs, latency, errors.

Usage:
  python scripts/embedding_comparison.py

Requires:
  - sentence-transformers installed (local)
  - GOOGLE_API_KEY in .env (gemini)
  - OPENAI_API_KEY in .env (openai)
  - EMBED_PROVIDER env var is overridden internally; no need to set it

Pricing used (verified 2026-08-31):
  Gemini embedding-2 PAID tier: $0.20 / 1M tokens
  OpenAI text-embedding-3-small: $0.02 / 1M tokens
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
    GEMINI_EMBED_COST_PER_TOKEN_PAID, OPENAI_EMBED_COST_PER_TOKEN, CHARS_PER_TOKEN,
    RAILWAY_VCPU_COST_PER_MIN, RAILWAY_VCPU_ALLOC, LOCAL_MS_PER_TEXT_MEASURED,
    AUTO_MERGE_THRESHOLD, SAME_DAY_DUP_THRESHOLD, GREY_ZONE_MIN,
    classify, cosine, PairResult, get_local_embedder, get_gemini_client, get_openai_client,
    gemini_cost_per_text, openai_cost_per_text, local_cost_per_text,
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


def run_openai_benchmark(pairs):
    """Embed pairs with OpenAI text-embedding-3-small (768-dim, native batch)."""
    from tests.test_embedding_benchmark import run_benchmark
    return run_benchmark(pairs, "openai")


def print_three_way_comparison(local_sum: dict, gemini_sum: dict | None, openai_sum: dict | None):
    print(f"\n{'='*82}")
    print("  3-WAY PROVIDER COMPARISON (LOCAL vs GEMINI vs OPENAI)")
    print(f"{'='*82}")
    header = f"  {'Metric':<35} {'LOCAL':>14} {'GEMINI':>14} {'OPENAI':>14}"
    print(header)
    print(f"  {'-'*(len(header)-2)}")

    def val(s, key, fmt="{:.1f}%", mult=1.0):
        if not s:
            return "N/A"
        v = s[key] * mult
        return fmt.format(v)

    la = val(local_sum, 'accuracy', "{:.1f}%", 100)
    ga = val(gemini_sum, 'accuracy', "{:.1f}%", 100)
    oa = val(openai_sum, 'accuracy', "{:.1f}%", 100)
    print(f"  {'Embed-layer accuracy (auto only)':<35} {la:>14} {ga:>14} {oa:>14}")

    for lbl in ["DUPLICATE", "NEW"]:
        lf = f"{local_sum['per_class'][lbl]['f1']:.3f}" if local_sum else "N/A"
        gf = f"{gemini_sum['per_class'][lbl]['f1']:.3f}" if gemini_sum else "N/A"
        of_ = f"{openai_sum['per_class'][lbl]['f1']:.3f}" if openai_sum else "N/A"
        print(f"  {lbl+' F1 (auto-decided)':<35} {lf:>14} {gf:>14} {of_:>14}")

    lg = val(local_sum, 'grey_zone_pct', "{:.1f}%")
    gg = val(gemini_sum, 'grey_zone_pct', "{:.1f}%")
    og = val(openai_sum, 'grey_zone_pct', "{:.1f}%")
    print(f"  {'Grey zone %':<35} {lg:>14} {gg:>14} {og:>14}")

    lp = f"${local_sum['pipeline_cost_per_story_usd']:.6f}" if local_sum else "N/A"
    gp = f"${gemini_sum['pipeline_cost_per_story_usd']:.6f}" if gemini_sum else "N/A"
    op_ = f"${openai_sum['pipeline_cost_per_story_usd']:.6f}" if openai_sum else "N/A"
    print(f"  {'Pipeline cost/story (USD)':<35} {lp:>14} {gp:>14} {op_:>14}")

    le = f"${local_sum['embed_cost_per_text_usd']:.2e}" if local_sum else "N/A"
    ge = f"${gemini_sum['embed_cost_per_text_usd']:.2e}" if gemini_sum else "N/A"
    oe = f"${openai_sum['embed_cost_per_text_usd']:.2e}" if openai_sum else "N/A"
    print(f"  {'Embed cost/text (USD)':<35} {le:>14} {ge:>14} {oe:>14}")

    ll = f"{local_sum['latency_per_text_ms']:.1f}" if local_sum else "N/A"
    gl = f"{gemini_sum['latency_per_text_ms']:.1f}" if gemini_sum else "N/A"
    ol = f"{openai_sum['latency_per_text_ms']:.1f}" if openai_sum else "N/A"
    print(f"  {'Latency/text (ms)':<35} {ll:>14} {gl:>14} {ol:>14}")
    print()


def run_all():
    from tests.test_embedding_benchmark import run_benchmark

    print("\n" + "="*82)
    print("  TRUEBRIEF EMBEDDING COMPARISON: LOCAL vs GEMINI vs OPENAI")
    print("  Dataset: 60 production (DB-sourced) + 27 adversarial = 87 pairs")
    print("  OpenAI pricing: $0.02/M tokens (text-embedding-3-small, 768d Matryoshka)")
    print("  Gemini pricing: $0.20/M tokens (paid tier, verified 2026-08-30)")
    print("  Judge LLM cost: $0.0000797/call (measured from 1,756 live DB calls)")
    print("="*82)

    # ── Run local ────────────────────────────────────────────────────────────
    print("\n[1/6] Running LOCAL embedder on production set...")
    t0 = time.perf_counter()
    local_prod_r, local_prod_s = run_benchmark(PROD_PAIRS, "local")
    local_prod_time = time.perf_counter() - t0

    print("[2/6] Running LOCAL embedder on adversarial set...")
    t0 = time.perf_counter()
    local_adv_r, local_adv_s = run_benchmark(ADV_PAIRS, "local")
    local_adv_time = time.perf_counter() - t0

    print_report(local_prod_r, local_prod_s, "LOCAL -- PRODUCTION (60 pairs)")
    print_report(local_adv_r, local_adv_s, "LOCAL -- ADVERSARIAL (27 pairs)")

    # ── Run OpenAI ───────────────────────────────────────────────────────────
    openai_prod_r = openai_prod_s = openai_adv_r = openai_adv_s = None
    openai_prod_time = openai_adv_time = 0.0
    openai_failed = False
    try:
        print("\n[3/6] Running OPENAI embedder on production set...")
        t0 = time.perf_counter()
        openai_prod_r, openai_prod_s = run_openai_benchmark(PROD_PAIRS)
        openai_prod_time = time.perf_counter() - t0
        print_report(openai_prod_r, openai_prod_s, "OPENAI -- PRODUCTION (60 pairs)")

        print("[4/6] Running OPENAI embedder on adversarial set...")
        t0 = time.perf_counter()
        openai_adv_r, openai_adv_s = run_openai_benchmark(ADV_PAIRS)
        openai_adv_time = time.perf_counter() - t0
        print_report(openai_adv_r, openai_adv_s, "OPENAI -- ADVERSARIAL (27 pairs)")
    except Exception as exc:
        openai_failed = True
        print(f"\n{'='*82}\n  OPENAI EMBEDDING RUN FAILED: {exc}\n"
              f"  (Check OPENAI_API_KEY in .env)\n{'='*82}\n")

    # ── Run Gemini (rate-limited sequential to avoid 429) ────────────────────
    gemini_prod_r = gemini_prod_s = gemini_adv_r = gemini_adv_s = None
    gemini_prod_time = gemini_adv_time = 0.0
    gemini_failed = False
    try:
        print("\n[5/6] Running GEMINI embedder on production set (rate-limited, ~2 min)...")
        t0 = time.perf_counter()
        gemini_prod_r, gemini_prod_s = run_gemini_rate_limited(PROD_PAIRS)
        gemini_prod_time = time.perf_counter() - t0
        print_report(gemini_prod_r, gemini_prod_s, "GEMINI -- PRODUCTION (60 pairs)")

        print("[6/6] Running GEMINI embedder on adversarial set (rate-limited, ~1 min)...")
        t0 = time.perf_counter()
        gemini_adv_r, gemini_adv_s = run_gemini_rate_limited(ADV_PAIRS)
        gemini_adv_time = time.perf_counter() - t0
        print_report(gemini_adv_r, gemini_adv_s, "GEMINI -- ADVERSARIAL (27 pairs)")
    except Exception as exc:
        gemini_failed = True
        print(f"\n{'='*82}\n  GEMINI EMBEDDING RUN FAILED: {exc}\n"
              f"  (LOCAL/OPENAI results above are unaffected)\n{'='*82}\n")

    # ── PR Curves ────────────────────────────────────────────────────────────
    print(f"\n{'='*82}")
    print("  PR CURVE AUC (DUPLICATE class, production set)")
    print(f"{'='*82}")
    lc = pr_curve(local_prod_r, "DUPLICATE")
    print(f"  Local  AUC: {lc['auc']:.4f}")
    if openai_prod_r:
        oc = pr_curve(openai_prod_r, "DUPLICATE")
        print(f"  OpenAI AUC: {oc['auc']:.4f}  (Gap vs Local: {(oc['auc']-lc['auc']):+.4f})")
    if gemini_prod_r:
        gc = pr_curve(gemini_prod_r, "DUPLICATE")
        print(f"  Gemini AUC: {gc['auc']:.4f}  (Gap vs Local: {(gc['auc']-lc['auc']):+.4f})")

    # ── Threshold Sweep ──────────────────────────────────────────────────────
    print(f"\n  Threshold where escalation rate ~= 75% (what dup cutoff achieves that):")
    def find_threshold_at_escalation(results, target=0.75):
        best = {"t": None, "escal": None, "auto_acc": None}
        best_diff = 999
        for t in np.arange(0.50, 1.00, 0.01):
            n_auto_dup = sum(1 for r in results if r.score >= t)
            n_auto_new = sum(1 for r in results if r.score < GREY_ZONE_MIN)
            n_grey = sum(1 for r in results if GREY_ZONE_MIN <= r.score < t)
            n = len(results)
            escal = n_grey / n
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

    providers_to_sweep = [("Local", local_prod_r)]
    if openai_prod_r:
        providers_to_sweep.append(("OpenAI", openai_prod_r))
    if gemini_prod_r:
        providers_to_sweep.append(("Gemini", gemini_prod_r))

    for label, results in providers_to_sweep:
        b = find_threshold_at_escalation(results, target=0.75)
        print(f"  {label:<8}: dup_threshold={b['t']:.2f}, escalation={b['escal']*100:.1f}%, "
              f"auto-layer-acc={b['auto_acc']*100:.1f}%")

    # ── Full cost breakdown ───────────────────────────────────────────────────
    print(f"\n{'='*82}")
    print("  COST BREAKDOWN (per story, N=3 candidates)")
    print(f"{'='*82}")

    avg_text_len = sum(len(p.text_a) + len(p.text_b) for p in PROD_PAIRS) / (2 * len(PROD_PAIRS))
    local_embed_per_text  = (LOCAL_MS_PER_TEXT_MEASURED / 1000 / 60) * RAILWAY_VCPU_COST_PER_MIN * RAILWAY_VCPU_ALLOC
    openai_embed_per_text = (avg_text_len / CHARS_PER_TOKEN) * OPENAI_EMBED_COST_PER_TOKEN
    gemini_embed_per_text = (avg_text_len / CHARS_PER_TOKEN) * GEMINI_EMBED_COST_PER_TOKEN_PAID

    local_escal  = local_prod_s["escalation_rate"]
    openai_escal = openai_prod_s["escalation_rate"] if openai_prod_s else 0.0
    gemini_escal = gemini_prod_s["escalation_rate"] if gemini_prod_s else 0.0

    local_pipeline  = LEDGER_FETCH_LIMIT * local_embed_per_text  + local_escal  * LEDGER_FETCH_LIMIT * JUDGE_COST_PER_CALL_USD
    openai_pipeline = LEDGER_FETCH_LIMIT * openai_embed_per_text + openai_escal * LEDGER_FETCH_LIMIT * JUDGE_COST_PER_CALL_USD if openai_prod_s else 0.0
    gemini_pipeline = LEDGER_FETCH_LIMIT * gemini_embed_per_text + gemini_escal * LEDGER_FETCH_LIMIT * JUDGE_COST_PER_CALL_USD if gemini_prod_s else 0.0

    print(f"\n  Average text length: {avg_text_len:.0f} chars")
    print(f"\n  {'Component':<35} {'LOCAL':>14} {'OPENAI':>14} {'GEMINI':>14}")
    print(f"  {'-'*79}")
    oe_txt = f"${openai_embed_per_text:>12.2e}" if openai_prod_s else "N/A"
    ge_txt = f"${gemini_embed_per_text:>12.2e}" if gemini_prod_s else "N/A"
    print(f"  {'Embed cost per text':<35} ${local_embed_per_text:>12.2e} {oe_txt:>14} {ge_txt:>14}")

    oe3_txt = f"${openai_embed_per_text*3:>12.2e}" if openai_prod_s else "N/A"
    ge3_txt = f"${gemini_embed_per_text*3:>12.2e}" if gemini_prod_s else "N/A"
    print(f"  {'Embed cost for N=3 candidates':<35} ${local_embed_per_text*3:>12.2e} {oe3_txt:>14} {ge3_txt:>14}")

    oe_esc = f"{openai_escal*100:>13.1f}%" if openai_prod_s else "N/A"
    ge_esc = f"{gemini_escal*100:>13.1f}%" if gemini_prod_s else "N/A"
    print(f"  {'Escalation rate (% needing LLM)':<35} {local_escal*100:>13.1f}% {oe_esc:>14} {ge_esc:>14}")

    oe_calls = f"{openai_escal*3:>14.2f}" if openai_prod_s else "N/A"
    ge_calls = f"{gemini_escal*3:>14.2f}" if gemini_prod_s else "N/A"
    print(f"  {'LLM judge calls per story (N=3)':<35} {local_escal*3:>14.2f} {oe_calls:>14} {ge_calls:>14}")

    oe_llm = f"${openai_escal*3*JUDGE_COST_PER_CALL_USD:>12.6f}" if openai_prod_s else "N/A"
    ge_llm = f"${gemini_escal*3*JUDGE_COST_PER_CALL_USD:>12.6f}" if gemini_prod_s else "N/A"
    print(f"  {'LLM cost per story':<35} ${local_escal*3*JUDGE_COST_PER_CALL_USD:>12.6f} {oe_llm:>14} {ge_llm:>14}")

    oe_tot = f"${openai_pipeline:>12.6f}" if openai_prod_s else "N/A"
    ge_tot = f"${gemini_pipeline:>12.6f}" if gemini_prod_s else "N/A"
    print(f"  {'TOTAL pipeline cost per story':<35} ${local_pipeline:>12.6f} {oe_tot:>14} {ge_tot:>14}")

    # Scale projections
    print(f"\n  Scale projections (total pipeline cost, excl. other pipeline stages):")
    print(f"  {'Scenario':<35} {'LOCAL':>14} {'OPENAI':>14} {'GEMINI':>14}")
    print(f"  {'-'*79}")
    for label, n_stories in [("100 stories/day (1 topic)", 100),
                               ("1,000 stories/day (10 topics)", 1000),
                               ("10,000 stories/day (100 topics)", 10000)]:
        lc_ = f"${local_pipeline * n_stories:>12.4f}"
        oc_ = f"${openai_pipeline * n_stories:>12.4f}" if openai_prod_s else "N/A"
        gc_ = f"${gemini_pipeline * n_stories:>12.4f}" if gemini_prod_s else "N/A"
        print(f"  {label:<35} {lc_:>14} {oc_:>14} {gc_:>14}")

    # ── Latency breakdown ─────────────────────────────────────────────────────
    print(f"\n{'='*82}")
    print("  LATENCY BREAKDOWN")
    print(f"{'='*82}")
    print(f"\n  {'Measurement':<45} {'LOCAL':>12} {'OPENAI':>12} {'GEMINI':>12}")
    print(f"  {'-'*83}")
    op_p_t = f"{openai_prod_time:>11.2f}s" if openai_prod_s else "N/A"
    ge_p_t = f"{gemini_prod_time:>11.2f}s" if gemini_prod_s else "N/A"
    print(f"  {'Embed batch time (prod set, wall clock)':<45} {local_prod_time:>11.2f}s {op_p_t:>12} {ge_p_t:>12}")

    op_a_t = f"{openai_adv_time:>11.2f}s" if openai_adv_s else "N/A"
    ge_a_t = f"{gemini_adv_time:>11.2f}s" if gemini_adv_s else "N/A"
    print(f"  {'Embed batch time (adv set, wall clock)':<45} {local_adv_time:>11.2f}s {op_a_t:>12} {ge_a_t:>12}")

    op_lat = f"{openai_prod_s['latency_per_text_ms']:>11.1f}ms" if openai_prod_s else "N/A"
    ge_lat = f"{gemini_prod_s['latency_per_text_ms']:>11.1f}ms" if gemini_prod_s else "N/A"
    print(f"  {'Per-text latency (amortised)':<45} {local_prod_s['latency_per_text_ms']:>11.1f}ms {op_lat:>12} {ge_lat:>12}")

    op_s_lat = f"{openai_prod_s['latency_per_text_ms']*3:>11.1f}ms" if openai_prod_s else "N/A"
    ge_s_lat = f"{gemini_prod_s['latency_per_text_ms']*3:>11.1f}ms" if gemini_prod_s else "N/A"
    print(f"  {'Per-story latency (N=3 embed)':<45} {local_prod_s['latency_per_text_ms']*3:>11.1f}ms {op_s_lat:>12} {ge_s_lat:>12}")

    # ── 3-Way Summary Table ───────────────────────────────────────────────────
    print_three_way_comparison(local_prod_s, gemini_prod_s, openai_prod_s)

    # ── Failure catalogue ─────────────────────────────────────────────────────
    def _rescue_status(r):
        if r.predicted == "GREY":
            return "escalated to LLM (correct behavior)"
        if r.score >= AUTO_MERGE_THRESHOLD:
            return "UNRESCUABLE — auto-merged, no LLM call, wrong answer reaches user"
        return f"LLM-rescuable (grey zone, +${JUDGE_COST_PER_CALL_USD:.7f} per candidate)"

    def _print_failure_catalogue(adv_r, provider_label):
        if not adv_r:
            return
        print(f"\n{'='*82}")
        print(f"  FAILURE CATALOGUE (adversarial set, {provider_label})")
        print(f"{'='*82}")
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
    if openai_adv_r:
        _print_failure_catalogue(openai_adv_r, "OPENAI")
    if gemini_adv_r:
        _print_failure_catalogue(gemini_adv_r, "GEMINI")

    print(f"\n{'='*82}")
    print("  BOTTOM LINE")
    print(f"{'='*82}")
    if openai_prod_s:
        acc_diff_o = (openai_prod_s['accuracy'] - local_prod_s['accuracy']) * 100
        escal_diff_o = (openai_prod_s['escalation_rate'] - local_prod_s['escalation_rate']) * 100
        cost_diff_o = openai_pipeline - local_pipeline
        print(f"\n  OpenAI vs Local:")
        print(f"    Accuracy diff: {acc_diff_o:+.1f}pp on auto-decided pairs")
        print(f"    Escalation diff: {escal_diff_o:+.1f}pp (positive = MORE LLM calls)")
        print(f"    Pipeline cost diff per story: {cost_diff_o:+.6f} USD")

    if gemini_prod_s:
        acc_diff_g = (gemini_prod_s['accuracy'] - local_prod_s['accuracy']) * 100
        escal_diff_g = (gemini_prod_s['escalation_rate'] - local_prod_s['escalation_rate']) * 100
        cost_diff_g = gemini_pipeline - local_pipeline
        print(f"\n  Gemini vs Local:")
        print(f"    Accuracy diff: {acc_diff_g:+.1f}pp on auto-decided pairs")
        print(f"    Escalation diff: {escal_diff_g:+.1f}pp (positive = MORE LLM calls)")
        print(f"    Pipeline cost diff per story: {cost_diff_g:+.6f} USD")

    print()


if __name__ == "__main__":
    run_all()
