"""Quick score distribution check — see if per-topic normalization looks meaningful."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client

db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

topics = db.table("topics").select("id,raw_query,search_strategy").execute().data

for t in topics:
    tid = t["id"]
    raw_q = t["raw_query"]
    strat = t.get("search_strategy") or {}
    topic_name = strat.get("topic_name", raw_q)

    rows = (
        db.table("known_facts")
        .select("alpha_text,relevance")
        .eq("topic_id", tid)
        .not_.is_("relevance", "null")
        .order("relevance", desc=True)
        .execute()
        .data
    )
    if not rows:
        print(f"\n[{raw_q!r}] — no facts with relevance")
        continue

    scores = [r["relevance"] for r in rows if r["relevance"] is not None]
    mn, mx, avg = min(scores), max(scores), sum(scores) / len(scores)
    rng = mx - mn

    print(f"\n{'='*60}")
    print(f"Topic: {raw_q!r}  (name: {topic_name!r})")
    print(f"  Facts: {len(scores)}  |  min={mn:.4f}  max={mx:.4f}  avg={avg:.4f}  range={rng:.4f}")

    buckets = {"green(>=0.70)": 0, "normal(0.35-0.70)": 0, "muted(<0.35)": 0}
    for s in scores:
        norm = (s - mn) / rng if rng > 0.01 else 0.5
        if norm >= 0.70:
            buckets["green(>=0.70)"] += 1
        elif norm >= 0.35:
            buckets["normal(0.35-0.70)"] += 1
        else:
            buckets["muted(<0.35)"] += 1
    print(f"  Buckets: {buckets}")

    print(f"\n  TOP 5 (most relevant):")
    for r in rows[:5]:
        s = r["relevance"]
        norm = (s - mn) / rng if rng > 0.01 else 0.5
        print(f"    [{norm:.2f}] {r['alpha_text'][:100]}")

    print(f"\n  BOTTOM 5 (least relevant):")
    for r in rows[-5:]:
        s = r["relevance"]
        norm = (s - mn) / rng if rng > 0.01 else 0.5
        print(f"    [{norm:.2f}] {r['alpha_text'][:100]}")

print("\nDone.")
