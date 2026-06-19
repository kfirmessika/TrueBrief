"""
inspect_run.py — methodical post-mortem of a single pipeline run.

Pulls the same data the /admin/runs/[id] panel shows, plus the article
PUBLISH DATES (parsed out of the harvester prompts) and the topic's stored
fact freshness — so we can answer "why did the brief lead with 5-day-old news?"

Usage:
    python scripts/inspect_run.py                 # latest run, any topic
    python scripts/inspect_run.py iran            # latest run whose topic matches 'iran'
    python scripts/inspect_run.py --run <run_id>  # a specific run
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (_ROOT, _ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows cp1255 chokes on λ/·
except Exception:
    pass

from truebrief.ledger.database import get_supabase

db = get_supabase()


def _arg(name: str, default=None):
    if name in sys.argv:
        i = sys.argv.index(name)
        return sys.argv[i + 1] if i + 1 < len(sys.argv) else default
    return default


def _age(date_str: str | None, now: datetime) -> str:
    if not date_str:
        return "  ? "
    try:
        d = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        days = (now - d).days
        return f"{days:>3}d"
    except Exception:
        return "  ? "


def find_run() -> dict | None:
    run_id = _arg("--run")
    topic_filter = next((a for a in sys.argv[1:] if not a.startswith("--")), None)

    if run_id:
        r = db.table("pipeline_run").select("*").eq("id", run_id).single().execute()
        return r.data

    topic_id = None
    if topic_filter:
        t = (
            db.table("topics")
            .select("id, raw_query")
            .ilike("raw_query", f"%{topic_filter}%")
            .execute()
        )
        if not t.data:
            print(f"No topic matches '{topic_filter}'.")
            return None
        topic_id = t.data[0]["id"]
        print(f"Topic: '{t.data[0]['raw_query']}'  (id={topic_id})")

    q = db.table("pipeline_run").select("*").order("started_at", desc=True).limit(1)
    if topic_id:
        q = q.eq("topic_id", topic_id)
    r = q.execute()
    return r.data[0] if r.data else None


def main():
    now = datetime.now(timezone.utc)
    run = find_run()
    if not run:
        print("No run found.")
        return

    rid = run["id"]
    print("=" * 90)
    print(f"RUN {rid}")
    print(f"  started   : {run.get('started_at')}")
    print(f"  status    : {run.get('exit_status')}   duration: {run.get('duration_ms')}ms")
    print(
        f"  collected : {run.get('articles_collected')}   "
        f"selected: {run.get('articles_selected')}   "
        f"alphas: {run.get('alphas_extracted')}"
    )
    print(
        f"  decisions : NEW={run.get('decisions_new')} "
        f"UPDATE={run.get('decisions_update')} DUP={run.get('decisions_duplicate')}   "
        f"brief_len={run.get('brief_length')}"
    )

    # ---- trace walk -------------------------------------------------------
    tr = (
        db.table("pipeline_trace")
        .select("seq, stage, label, data")
        .eq("pipeline_run_id", rid)
        .order("seq")
        .execute()
    )
    print("\n" + "=" * 90)
    print("TRACE (stage by stage)")
    print("=" * 90)
    for row in tr.data or []:
        data = row.get("data") or {}
        print(f"\n[{row['seq']:>2}] {row['stage'].upper():<10} {row.get('label','')}")
        st = row["stage"]
        if st == "collect" and "articles" in data:
            for a in data.get("articles", []):
                print(f"        · {a.get('title','')[:80]}")
        elif st == "mmr":
            for p in data.get("selected", []) or []:
                if isinstance(p, dict):
                    print(
                        f"        #{p.get('rank','?')} rel={p.get('relevance','?')} "
                        f"mmr={p.get('mmr_score','?')}  {str(p.get('title',''))[:70]}"
                    )
        elif st == "relevance":
            for d in data.get("dropped_facts", []) or []:
                print(f"        DROPPED sim={d.get('sim')}  {d.get('text','')[:75]}")
        elif st == "harvest" and "facts" in data:
            for f in data.get("facts", []):
                print(f"        · {str(f)[:85]}")
        elif st == "judge":
            print(
                f"        {data.get('decision','')}  sim={data.get('similarity_score','')}  "
                f"date={data.get('event_date','')}"
            )

    # ---- article publish dates (parsed from harvester prompts) -----------
    llm = (
        db.table("llm_call_log")
        .select("stage, model, input_tokens, output_tokens, cost_usd, prompt, response")
        .eq("pipeline_run_id", rid)
        .execute()
    )
    print("\n" + "=" * 90)
    print("LLM CALLS  +  ARTICLE PUBLISH DATES (the freshness question)")
    print("=" * 90)
    pat = re.compile(r"ARTICLE PUBLISHED DATE:\s*([0-9]{4}-[0-9]{2}-[0-9]{2}|Unknown)")
    for c in llm.data or []:
        stage = c.get("stage")
        toks = f"{c.get('input_tokens',0)}→{c.get('output_tokens',0)}"
        line = f"  {stage:<14} {c.get('model',''):<22} {toks:<12} ${c.get('cost_usd',0):.6f}"
        if stage == "harvester" and c.get("prompt"):
            m = pat.search(c["prompt"])
            pub = m.group(1) if m else "?"
            line += f"   pub={pub} ({_age(pub, now)} old)"
        print(line)
        # show event_dates the harvester assigned, from its JSON response
        if stage == "harvester" and c.get("response"):
            try:
                facts = json.loads(re.search(r"\[.*\]", c["response"], re.S).group(0))
                for f in facts:
                    print(
                        f"        → event_date={f.get('event_date','?')} "
                        f"class={f.get('event_class','?'):<12} {str(f.get('alpha_text',''))[:60]}"
                    )
            except Exception:
                pass

    # ---- stored fact freshness for the topic -----------------------------
    if run.get("topic_id"):
        kf = (
            db.table("known_facts")
            .select("alpha_text, event_date, first_seen_at, event_class")
            .eq("topic_id", run["topic_id"])
            .order("event_date", desc=True)
            .limit(40)
            .execute()
        )
        print("\n" + "=" * 90)
        print("STORED FACTS — freshness distribution (event_date desc, top 40)")
        print("=" * 90)
        print(f"  {'event_date':<12} {'age':<6} {'class':<13} text")
        for f in kf.data or []:
            print(
                f"  {str(f.get('event_date','?')):<12} {_age(f.get('event_date'), now):<6} "
                f"{str(f.get('event_class') or '-'):<13} {str(f.get('alpha_text',''))[:60]}"
            )


if __name__ == "__main__":
    main()
