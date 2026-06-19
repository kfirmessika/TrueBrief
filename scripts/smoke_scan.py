#!/usr/bin/env python
"""
Layer 2 — End-to-end pipeline SMOKE test (real LLM / real Supabase).

Drives the actual PipelineRunner the same way the Celery task does (opens a
pipeline_run, sets the trace context, runs, finalizes), then reads the trace
back and asserts quality invariants. This is the real pre-deploy check that a
scan still produces a sane brief — dates, relevance, dedup, and cost all behave.

    python scripts/smoke_scan.py --dry-run          # wiring only, no scan, $0
    python scripts/smoke_scan.py --limit 2          # real scan on 2 topics
    python scripts/smoke_scan.py --topic-id <uuid>  # real scan on one topic
    python scripts/smoke_scan.py --all              # every topic

Exit 0 = quality invariants held. Exit 1 = a QUALITY violation (deploy-blocking).
Infra/quota problems are reported as ERROR but distinguished from quality fails.

See docs/testing.md for the full plan.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (_ROOT, _ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# ── thresholds ────────────────────────────────────────────────────────────────
COST_TARGET_USD = 0.02     # architecture target cost/brief — warn above
COST_CEILING_USD = 0.10    # runaway — hard fail above
MIN_BRIEF_LEN = 50         # a "real" brief

PASS, FAIL, WARN, INFO, ERROR = "PASS", "FAIL", "WARN", "INFO", "ERROR"
_ICON = {PASS: "+", FAIL: "x", WARN: "!", INFO: "-", ERROR: "E"}


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(_ROOT / ".env", override=False)
    except Exception:
        pass


def _say(status: str, msg: str) -> None:
    print(f"    {_ICON.get(status, '-')} [{status:5}] {msg}")


# ── dry run (wiring only) ─────────────────────────────────────────────────────
def dry_run() -> int:
    print("Smoke: dry-run (wiring only, no scan)")
    ok = True
    try:
        from truebrief.ledger.database import get_supabase
        get_supabase().table("topics").select("id").limit(1).execute()
        _say(PASS, "Supabase reachable")
    except Exception as exc:
        _say(FAIL, f"Supabase: {exc}")
        ok = False
    for table, col in (("pipeline_trace", "id"), ("llm_call_log", "prompt")):
        try:
            from truebrief.ledger.database import get_supabase
            get_supabase().table(table).select(col).limit(1).execute()
            _say(PASS, f"migration 012: {table}.{col}")
        except Exception as exc:
            _say(FAIL, f"migration 012 missing: {table}.{col} ({str(exc)[:60]})")
            ok = False
    try:
        from truebrief.pipeline.runner import PipelineRunner
        runner = PipelineRunner()
        _say(PASS, f"PipelineRunner wired ({len(runner.sources)} sources: "
                   f"{', '.join(s.name for s in runner.sources)})")
    except Exception as exc:
        _say(FAIL, f"PipelineRunner construct failed: {exc}")
        ok = False
    print("=" * 64)
    print("DRY-RUN OK" if ok else "DRY-RUN FAILED")
    return 0 if ok else 1


# ── real scan ─────────────────────────────────────────────────────────────────
def _resolve_topics(args) -> list[tuple[str, str]]:
    from truebrief.ledger.database import get_supabase
    db = get_supabase()
    if args.topic_id:
        res = db.table("topics").select("id, raw_query").in_("id", args.topic_id).execute()
    else:
        q = db.table("topics").select("id, raw_query").order("created_at", desc=True)
        if not args.all:
            q = q.limit(args.limit)
        res = q.execute()
    return [(t["id"], t["raw_query"]) for t in (res.data or [])]


def _run_pipeline(topic_id: str, query: str) -> str | None:
    """Replicate the Celery task wrapper so a real trace is produced."""
    from truebrief.ledger.telemetry import get_telemetry
    from truebrief.llm.client import pipeline_run_id_var
    from truebrief.pipeline.runner import PipelineRunner

    tel = get_telemetry()
    run_id = tel.start_run(topic_id=topic_id) if tel else None
    token = pipeline_run_id_var.set(run_id)
    started = time.monotonic()
    try:
        brief = PipelineRunner().run(query, topic_id=topic_id)
        if tel and run_id:
            tel.finish_run(
                run_id,
                duration_ms=int((time.monotonic() - started) * 1000),
                brief_length=len(brief or ""),
                exit_status="success" if (brief or "").strip() else "no_update",
            )
        return run_id
    except Exception as exc:
        if tel and run_id:
            tel.finish_run(
                run_id, duration_ms=int((time.monotonic() - started) * 1000),
                exit_status="error", error_message=str(exc),
            )
        print(f"    {_ICON[ERROR]} [ERROR] pipeline raised: {exc}")
        return run_id
    finally:
        pipeline_run_id_var.reset(token)


def _read_metrics(run_id: str) -> dict:
    """Aggregate pipeline_run + llm_call_log + pipeline_trace for one run."""
    from truebrief.ledger.database import get_supabase
    db = get_supabase()
    m: dict = {"run_id": run_id}

    run = db.table("pipeline_run").select("*").eq("id", run_id).execute()
    m["run"] = (run.data or [{}])[0]

    calls = db.table("llm_call_log").select("stage, cost_usd").eq("pipeline_run_id", run_id).execute()
    m["llm_calls"] = len(calls.data or [])
    m["cost_usd"] = sum(float(c.get("cost_usd") or 0) for c in (calls.data or []))

    tr = db.table("pipeline_trace").select("stage, label, data").eq(
        "pipeline_run_id", run_id).order("seq").execute()
    events = tr.data or []
    m["trace_events"] = len(events)
    by_stage: dict[str, list] = {}
    for e in events:
        by_stage.setdefault(e["stage"], []).append(e)
    m["by_stage"] = by_stage

    # Derive quality signals from the trace.
    m["articles"] = sum(len((e.get("data") or {}).get("articles", [])) for e in by_stage.get("collect", []))
    m["harvest_facts"] = sum(len((e.get("data") or {}).get("facts", [])) for e in by_stage.get("harvest", []))
    rel = by_stage.get("relevance", [])
    m["relevance_ran"] = bool(rel)
    m["relevance_dropped"] = sum((e.get("data") or {}).get("dropped", 0) for e in rel)
    decisions = [(e.get("data") or {}) for e in by_stage.get("judge", [])]
    m["decisions"] = decisions
    m["dec_new"] = sum(1 for d in decisions if str(d.get("decision")).upper() == "NEW")
    m["dec_update"] = sum(1 for d in decisions if str(d.get("decision")).upper() == "UPDATE")
    m["dec_dupe"] = sum(1 for d in decisions if str(d.get("decision")).upper() in ("DUPLICATE", "MERGE"))
    return m


def _parse_date(s: str):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).date()
    except Exception:
        try:
            return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
        except Exception:
            return None


def _validate(m: dict) -> list[tuple[str, str, str]]:
    """Return (check, status, detail). FAIL = deploy-blocking quality violation."""
    out: list[tuple[str, str, str]] = []
    run = m.get("run", {})
    status = run.get("exit_status")
    brief_len = run.get("brief_length") or 0

    # completed
    if status == "error":
        out.append(("completed", FAIL, f"exit_status=error: {run.get('error_message')}"))
    elif status == "no_update":
        out.append(("completed", WARN, "no_update (0 new facts — quiet scan or quota/collection issue)"))
    else:
        out.append(("completed", PASS, f"exit_status={status}"))

    # collection
    if m["articles"] == 0:
        out.append(("collection", WARN, "0 articles collected — likely a source/quota outage"))
    else:
        out.append(("collection", PASS, f"{m['articles']} articles, {m['harvest_facts']} facts harvested"))

    # brief present
    if m["harvest_facts"] > 0 and status == "success" and brief_len < MIN_BRIEF_LEN:
        out.append(("brief present", FAIL, f"facts harvested but brief is {brief_len} chars"))
    else:
        out.append(("brief present", PASS, f"brief {brief_len} chars"))

    # date sanity (the §8B red light)
    today = date.today()
    future = []
    for d in m["decisions"]:
        ed = _parse_date(d.get("event_date", ""))
        if ed and ed > today:
            future.append((d.get("alpha_text", "")[:50], str(ed)))
    if future:
        out.append(("date sanity", FAIL, f"{len(future)} fact(s) dated in the FUTURE, e.g. {future[0]}"))
    else:
        out.append(("date sanity", PASS, "no future-dated facts"))

    # relevance gate
    from config.settings import settings
    if getattr(settings, "V3_RELEVANCE_GATE", False):
        if m["relevance_ran"]:
            out.append(("relevance gate", PASS, f"ran; dropped {m['relevance_dropped']}"))
        else:
            out.append(("relevance gate", WARN, "flag on but no relevance stage in trace"))

    # dedup sanity
    total_dec = m["dec_new"] + m["dec_update"] + m["dec_dupe"]
    if total_dec:
        out.append(("dedup", PASS,
                    f"NEW {m['dec_new']} / UPD {m['dec_update']} / DUP {m['dec_dupe']}"))
    else:
        out.append(("dedup", INFO, "no judge decisions (nothing reached the arbiter)"))

    # cost
    cost = m["cost_usd"]
    if cost > COST_CEILING_USD:
        out.append(("cost", FAIL, f"${cost:.5f} over ${COST_CEILING_USD} ceiling ({m['llm_calls']} calls)"))
    elif cost > COST_TARGET_USD:
        out.append(("cost", WARN, f"${cost:.5f} over ${COST_TARGET_USD} target ({m['llm_calls']} calls)"))
    else:
        out.append(("cost", PASS, f"${cost:.5f} ({m['llm_calls']} LLM calls)"))

    return out


def real_scan(args) -> int:
    _load_dotenv()
    topics = _resolve_topics(args)
    if not topics:
        print("No topics found to scan. Create one or pass --topic-id.")
        return 1

    print(f"Smoke: real scan on {len(topics)} topic(s)\n" + "=" * 64)
    any_fail = False
    for topic_id, query in topics:
        print(f"\n[ topic ] {query}  ({topic_id})")
        run_id = _run_pipeline(topic_id, query)
        if not run_id:
            print(f"    {_ICON[ERROR]} [ERROR] no run_id (telemetry/DB down) — cannot validate")
            any_fail = True
            continue
        m = _read_metrics(run_id)
        for check, status, detail in _validate(m):
            _say(status, f"{check}: {detail}")
            if status == FAIL:
                any_fail = True
        print(f"    -> trace: {m['trace_events']} events  (/admin/runs/{run_id})")

    print("\n" + "=" * 64)
    print("SMOKE FAILED — quality violation above; do not deploy." if any_fail
          else "SMOKE OK — quality invariants held.")
    return 1 if any_fail else 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="TrueBrief E2E pipeline smoke test.")
    ap.add_argument("--dry-run", action="store_true", help="wiring/config only, no scan")
    ap.add_argument("--topic-id", action="append", help="scan this topic id (repeatable)")
    ap.add_argument("--limit", type=int, default=2, help="scan the N most recent topics (default 2)")
    ap.add_argument("--all", action="store_true", help="scan every topic")
    args = ap.parse_args()
    _load_dotenv()
    return dry_run() if args.dry_run else real_scan(args)


if __name__ == "__main__":
    raise SystemExit(main())
