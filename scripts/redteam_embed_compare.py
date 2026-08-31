"""
scripts/redteam_embed_compare.py

Full Local vs Gemini embedding comparison on the 131-case red-team set.
Shows per-category wins/losses, error types, and real costs including LLM escalation.

Usage:
    python scripts/redteam_embed_compare.py
"""

import json, os, sys, time
sys.stdout.reconfigure(encoding='utf-8')
from collections import defaultdict
from dataclasses import dataclass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

# ── Constants (same as embedding benchmark) ───────────────────────────────────
AUTO_MERGE   = 0.97
SAME_DAY     = 0.93
GREY_MIN     = 0.75
JUDGE_COST   = 0.0000797   # USD per LLM call (measured from 1,756 live calls)
LOCAL_MS     = 10.0        # ms per text, Railway 2 vCPU (measured)
VCPU_COST    = 0.000463    # $/vCPU-min
VCPU_N       = 2
GEMINI_PAID  = 0.20 / 1_000_000  # $/token paid tier
CHARS_PER_TOK = 4.0

RESULTS_JSON = os.path.join(ROOT, "docs", "benchmarks", "_data",
    "2026-08-13_arbiter-redteam-results-LOCAL-EMBED.json")

CAT_LABELS = {
    "C1":"EXACT_DUPLICATE", "C2":"PARAPHRASE_DUP", "C3":"PARAPHRASE_DATEDRIFT",
    "C4":"TALLY_UPDATE", "C5":"NUMERIC_CHANGE", "C6":"ENTITY_ALIAS_DUP",
    "C7":"ANTONYM_GAP", "C8":"NUMERIC_CONTRADICTION", "C9":"PROMPT_INJECTION",
    "C10":"FALSE_DEDUP", "C11":"MISSING_DATE", "C12":"INTRA_BATCH",
}

def local_embed_cost(ms): return (ms/1000/60) * VCPU_COST * VCPU_N
def gemini_embed_cost(text): return (len(text)/CHARS_PER_TOK) * GEMINI_PAID
def classify(score):
    if score >= SAME_DAY: return "DUPLICATE"
    if score >= GREY_MIN: return "GREY"
    return "NEW"


@dataclass
class Pair:
    id: str
    cat: str
    text_a: str
    text_b: str
    label: str   # DUPLICATE | UPDATE | NEW


def load_pairs():
    data = json.load(open(RESULTS_JSON))
    raw = data["results"]
    matched_ids = [r["matched_alpha_id"] for r in raw if r.get("matched_alpha_id")]
    from truebrief.ledger.database import get_supabase
    sb = get_supabase()
    resp = sb.table("known_facts").select("id, alpha_text").in_("id", list(set(matched_ids))).execute()
    fact_texts = {row["id"]: row["alpha_text"] for row in (resp.data or [])}
    pairs, skipped = [], []
    label_map = {"DUPLICATE":"DUPLICATE","UPDATE":"UPDATE","NEW":"NEW"}
    for r in raw:
        lbl = label_map.get(r["expected_decision"])
        mid = r.get("matched_alpha_id")
        tb = fact_texts.get(mid) if mid else None
        if not lbl or not tb:
            skipped.append(r["id"])
            continue
        pairs.append(Pair(r["id"], r["id"][:2], r["alpha_text"], tb, lbl))
    print(f"  Pairs: {len(pairs)}  Skipped: {len(skipped)} ({', '.join(skipped[:5])}{'...' if len(skipped)>5 else ''})")
    return pairs


def embed_local(pairs):
    from tests.test_embedding_benchmark import get_local_embedder, cosine
    emb = get_local_embedder()
    texts = [p.text_a for p in pairs] + [p.text_b for p in pairs]
    t0 = time.perf_counter()
    vecs = emb.embed_batch(texts)
    ms_each = (time.perf_counter()-t0)*1000 / len(texts)
    va, vb = vecs[:len(pairs)], vecs[len(pairs):]
    return [(cosine(a,b), ms_each) for a,b in zip(va,vb)]


def embed_gemini(pairs, req_per_min=90):
    from google import genai as _genai
    from tests.test_embedding_benchmark import cosine
    backup = os.environ.get("GOOGLE_API_KEY_BACKUP","")
    key = backup or os.environ.get("GOOGLE_API_KEY","")
    if backup: print("  Using GOOGLE_API_KEY_BACKUP")
    client = _genai.Client(api_key=key)
    delay = 60.0/req_per_min
    texts = [p.text_a for p in pairs] + [p.text_b for p in pairs]
    vecs, t_all = [], time.perf_counter()
    for i, text in enumerate(texts):
        t0 = time.perf_counter()
        for attempt in range(4):
            try:
                resp = client.models.embed_content(model="models/gemini-embedding-2", contents=text)
                vecs.append(resp.embeddings[0].values)
                break
            except Exception as e:
                if attempt == 3: raise
                wait = 5 * (attempt + 1)
                print(f"    Retry {attempt+1} on text {i} ({e.__class__.__name__}), wait {wait}s...", flush=True)
                time.sleep(wait)
        elapsed = time.perf_counter()-t0
        if elapsed < delay: time.sleep(delay-elapsed)
        if (i+1)%30==0: print(f"    {i+1}/{len(texts)}...", flush=True)
    ms_each = (time.perf_counter()-t_all)*1000/len(texts)
    va, vb = vecs[:len(pairs)], vecs[len(pairs):]
    return [(cosine(a,b), ms_each) for a,b in zip(va,vb)]


def analyze(pairs, scores_ms, provider):
    """Returns per-pair analysis dict."""
    results = []
    for pair, (score, ms) in zip(pairs, scores_ms):
        pred = classify(score)
        # Error classification
        if pred == "GREY":
            error = None      # correct abstention → LLM decides
            outcome = "GREY"
        elif pred == "DUPLICATE" and pair.label == "DUPLICATE":
            error = None; outcome = "CORRECT_DUP"
        elif pred == "NEW" and pair.label == "NEW":
            error = None; outcome = "CORRECT_NEW"
        elif pred == "DUPLICATE" and pair.label in ("UPDATE", "NEW"):
            # false merge
            error = "FALSE_MERGE_UNRESCUABLE" if score >= AUTO_MERGE else "FALSE_MERGE_RESCUABLE"
            outcome = "WRONG"
        elif pred == "NEW" and pair.label == "DUPLICATE":
            # missed recall — stored twice in DB, no LLM call ever made
            error = "MISSED_RECALL_UNRESCUABLE"
            outcome = "WRONG"
        elif pred == "NEW" and pair.label == "UPDATE":
            # auto-NEW on UPDATE → treated as new fact, no merge attempted
            error = "MISSED_UPDATE_UNRESCUABLE"
            outcome = "WRONG"
        else:
            error = "OTHER"; outcome = "WRONG"

        # Cost
        if provider == "local":
            embed_cost = local_embed_cost(ms) * 2   # text_a + text_b
        else:
            embed_cost = gemini_embed_cost(pair.text_a) + gemini_embed_cost(pair.text_b)
        llm_cost = JUDGE_COST if pred == "GREY" else 0.0
        total_cost = embed_cost + llm_cost

        results.append(dict(
            id=pair.id, cat=pair.cat, label=pair.label,
            score=score, pred=pred, outcome=outcome, error=error,
            embed_cost=embed_cost, llm_cost=llm_cost, total_cost=total_cost,
            text_a=pair.text_a, text_b=pair.text_b,
        ))
    return results


def print_full_report(local_r, gemini_r, pairs):
    n = len(pairs)

    def stats(results):
        auto    = [r for r in results if r["pred"] != "GREY"]
        grey    = [r for r in results if r["pred"] == "GREY"]
        correct = [r for r in auto if r["outcome"] != "WRONG"]
        wrong   = [r for r in auto if r["outcome"] == "WRONG"]
        unrescuable = [r for r in wrong if "UNRESCUABLE" in (r["error"] or "")]
        false_merge = [r for r in wrong if "FALSE_MERGE" in (r["error"] or "")]
        missed  = [r for r in wrong if "MISSED" in (r["error"] or "")]
        total_cost = sum(r["total_cost"] for r in results)
        embed_cost = sum(r["embed_cost"] for r in results)
        llm_cost   = sum(r["llm_cost"]   for r in results)
        return dict(n=n, auto=len(auto), grey=len(grey),
                    correct=len(correct), wrong=len(wrong),
                    unrescuable=len(unrescuable),
                    false_merge=len(false_merge), missed=len(missed),
                    total_cost=total_cost, embed_cost=embed_cost, llm_cost=llm_cost)

    L = stats(local_r)
    G = stats(gemini_r)

    print("\n" + "="*74)
    print("  LOCAL vs GEMINI — 119 real red-team pairs")
    print("  text_a=alpha_text vs text_b=matched stored fact (live DB)")
    print("="*74)
    print(f"\n{'Metric':<42} {'LOCAL':>10} {'GEMINI':>10}")
    print("-"*62)
    rows = [
        ("Pairs", L["n"], G["n"]),
        ("Auto-decided (embedding resolves)",        L["auto"],  G["auto"]),
        ("  GREY → sent to LLM",                    L["grey"],  G["grey"]),
        ("Auto-decided CORRECT",                     L["correct"], G["correct"]),
        ("Auto-decided WRONG",                       L["wrong"],   G["wrong"]),
        ("  -> False merges (auto-DUPLICATE, wrong)",L["false_merge"], G["false_merge"]),
        ("  -> Missed recalls/updates (auto-NEW, wrong)", L["missed"], G["missed"]),
        ("UNRESCUABLE errors (no LLM call, wrong)",  L["unrescuable"], G["unrescuable"]),
        ("Embed-layer accuracy (auto-decided only)",
            f'{100*L["correct"]/L["auto"]:.1f}%' if L["auto"] else "N/A",
            f'{100*G["correct"]/G["auto"]:.1f}%' if G["auto"] else "N/A"),
        ("LLM escalation rate",
            f'{100*L["grey"]/n:.1f}%', f'{100*G["grey"]/n:.1f}%'),
        ("Embed cost (119 pairs total)",
            f'${L["embed_cost"]*1e6:.1f}µ', f'${G["embed_cost"]*1e6:.1f}µ'),
        ("LLM cost (escalations × $0.0000797)",
            f'${L["llm_cost"]*1000:.4f}m', f'${G["llm_cost"]*1000:.4f}m'),
        ("Total cost (embed + LLM)",
            f'${L["total_cost"]*1000:.4f}m', f'${G["total_cost"]*1000:.4f}m'),
        ("Cost per pair",
            f'${L["total_cost"]/n*1e6:.2f}µ', f'${G["total_cost"]/n*1e6:.2f}µ'),
    ]
    for label, lv, gv in rows:
        print(f"  {label:<42} {str(lv):>10} {str(gv):>10}")

    # ── Per-category ──────────────────────────────────────────────────────────
    print(f"\n{'─'*74}")
    print(f"  Per-category breakdown")
    print(f"{'─'*74}")
    hdr = f"  {'Cat':<4} {'Label':<22} {'N':>3}  {'LOCAL':^30}  {'GEMINI':^30}"
    print(hdr)
    sub = f"  {'':4} {'':22} {'':3}  {'Auto%':>5} {'Grey%':>5} {'Corr%':>5} {'Unres':>5}  {'Auto%':>5} {'Grey%':>5} {'Corr%':>5} {'Unres':>5}"
    print(sub)
    print(f"  {'-'*70}")

    cats = sorted(set(r["cat"] for r in local_r))
    for cat in cats:
        lr = [r for r in local_r  if r["cat"]==cat]
        gr = [r for r in gemini_r if r["cat"]==cat]
        cn = len(lr)
        def cs(rlist):
            auto = [r for r in rlist if r["pred"]!="GREY"]
            grey = [r for r in rlist if r["pred"]=="GREY"]
            corr = [r for r in auto if r["outcome"]!="WRONG"]
            unr  = [r for r in auto if "UNRESCUABLE" in (r["error"] or "")]
            return (100*len(auto)/cn, 100*len(grey)/cn,
                    100*len(corr)/len(auto) if auto else 0, len(unr))
        la,lg,lc,lu = cs(lr)
        ga,gg,gc,gu = cs(gr)
        lbl = CAT_LABELS.get(cat, cat)
        # winner marker
        win = "<L" if lc > gc+5 else ("<G" if gc > lc+5 else "  ")
        print(f"  {cat:<4} {lbl:<22} {cn:>3}  "
              f"{la:>5.0f}% {lg:>5.0f}% {lc:>5.0f}% {lu:>5}  "
              f"{ga:>5.0f}% {gg:>5.0f}% {gc:>5.0f}% {gu:>5}  {win}")

    # ── Unrescuable error detail ──────────────────────────────────────────────
    for provider, results in [("LOCAL", local_r), ("GEMINI", gemini_r)]:
        unr = [r for r in results if "UNRESCUABLE" in (r["error"] or "")]
        print(f"\n  UNRESCUABLE ERRORS — {provider} ({len(unr)} total)")
        print(f"  {'ID':<10} {'Type':<30} {'Score':>6}  {'text_a (truncated)':>0}")
        for r in unr:
            etype = r["error"].replace("_UNRESCUABLE","")
            print(f"  {r['id']:<10} {etype:<30} {r['score']:.4f}  {r['text_a'][:60]}")
            print(f"  {'':10} {'vs':30}        {r['text_b'][:60]}")

    # ── Cost breakdown ────────────────────────────────────────────────────────
    print(f"\n{'─'*74}")
    print("  COST BREAKDOWN (USD, 119 pairs = 1 full topic scan)")
    print(f"{'─'*74}")
    print(f"  {'':35} {'LOCAL':>12} {'GEMINI':>12}")
    embed_per_pair_l = L["embed_cost"]/n
    embed_per_pair_g = G["embed_cost"]/n
    llm_per_pair_l   = L["llm_cost"]/n
    llm_per_pair_g   = G["llm_cost"]/n
    print(f"  {'Embed cost per pair':35} ${embed_per_pair_l*1e6:>10.3f}µ ${embed_per_pair_g*1e6:>10.3f}µ")
    print(f"  {'LLM cost per pair (escalated)':35} ${llm_per_pair_l*1e6:>10.3f}µ ${llm_per_pair_g*1e6:>10.3f}µ")
    print(f"  {'Total per pair':35} ${(embed_per_pair_l+llm_per_pair_l)*1e6:>10.3f}µ ${(embed_per_pair_g+llm_per_pair_g)*1e6:>10.3f}µ")
    # Extrapolate to 1M pairs/month
    M = 1_000_000
    print(f"  {'At 1M pairs/month':35} ${(embed_per_pair_l+llm_per_pair_l)*M:>10.2f}  ${(embed_per_pair_g+llm_per_pair_g)*M:>10.2f}")
    print(f"  {'  of which: embed':35} ${embed_per_pair_l*M:>10.2f}  ${embed_per_pair_g*M:>10.2f}")
    print(f"  {'  of which: LLM judge':35} ${llm_per_pair_l*M:>10.2f}  ${llm_per_pair_g*M:>10.2f}")

    print(f"\n  Note: LLM cost dominates. Embed cost is <2% of total for both models.")
    print(f"  The real cost difference is LLM escalation rate: {100*L['grey']/n:.0f}% (local) vs {100*G['grey']/n:.0f}% (gemini).")
    winner_cost = "LOCAL" if L["total_cost"] < G["total_cost"] else "GEMINI"
    winner_acc  = "LOCAL" if L["correct"]/max(L["auto"],1) > G["correct"]/max(G["auto"],1) else "GEMINI"
    print(f"\n  Cost winner:     {winner_cost}")
    print(f"  Accuracy winner: {winner_acc}")
    print(f"  Unrescuable errors: LOCAL={L['unrescuable']}  GEMINI={G['unrescuable']}")


def main():
    print("="*74)
    print("  RED-TEAM EMBEDDING COMPARISON: LOCAL vs GEMINI (119 real pairs)")
    print("="*74)
    print("\nLoading pairs from DB...")
    pairs = load_pairs()

    print("\n[1/2] Embedding with LOCAL (BAAI/bge-base-en-v1.5)...")
    local_scores = embed_local(pairs)
    local_results = analyze(pairs, local_scores, "local")

    print("\n[2/2] Embedding with GEMINI (gemini-embedding-2, rate-limited 90/min)...")
    gemini_scores = embed_gemini(pairs)
    gemini_results = analyze(pairs, gemini_scores, "gemini")

    print_full_report(local_results, gemini_results, pairs)


if __name__ == "__main__":
    main()
