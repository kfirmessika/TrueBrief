"""
API Routes - api/routes.py

Topic CRUD and pipeline triggers.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import List, Optional
import logging
import re
from datetime import datetime
from uuid import UUID

_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE,
)

def _require_uuid(value: str, name: str = "id") -> str:
    if not _UUID_RE.match(value):
        raise HTTPException(status_code=422, detail=f"Invalid {name}: must be a valid UUID")
    return value

from truebrief.ledger.database import get_supabase
from truebrief.billing.tiers import enforce_topic_limit, enforce_speed_limit
from truebrief.auth.dependencies import User, get_current_user, get_optional_user
from truebrief.api.rate_limit import limiter
from supabase import Client

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Pydantic Models for API ---
class TopicCreate(BaseModel):
    raw_query: str
    poll_interval_seconds: int = 3600   # Default: scan every hour

class TopicResponse(BaseModel):
    id: str
    raw_query: str
    frequency: str
    is_active: bool
    last_scan_at: Optional[str] = None

class BriefResponse(BaseModel):
    id: str
    topic_id: str
    content: str
    delivered_at: str

# --- Endpoints ---

@router.post("/topics", response_model=TopicResponse)
@limiter.limit("20/hour")
def create_topic(request: Request, topic: TopicCreate, user: User = Depends(get_current_user)):
    """
    Create a new tracking topic or subscribe to an existing one.
    If a topic with the same raw_query already exists, returns the existing
    topic and creates a subscription for the user.
    Enforces per-tier topic count limits (HTTP 402 if at cap).
    """
    db = get_supabase()

    val_uuid = user.id

    # --- Tier Enforcement: topic cap ---
    sub_res = (
        db.table("user_subscriptions")
        .select("tier")
        .eq("user_id", val_uuid)
        .execute()
    )
    tier_str = sub_res.data[0]["tier"] if sub_res.data else "free"

    # Count topics this user is already subscribed to
    count_res = (
        db.table("topic_subscriptions")
        .select("topic_id", count="exact")
        .eq("user_id", val_uuid)
        .execute()
    )
    current_count = count_res.count or 0
    enforce_topic_limit(val_uuid, tier_str, current_count)

    # 1. Check if topic already exists (case-insensitive)
    existing = db.table("topics").select("*").ilike("raw_query", topic.raw_query).execute()
    if existing.data:
        topic_record = existing.data[0]
        logger.info(f"Topic '{topic.raw_query}' already exists. Subscribing user.")
    else:
        # 2. Create new topic
        data = {
            "raw_query": topic.raw_query,
            "poll_interval_seconds": topic.poll_interval_seconds,
            "user_id": val_uuid
        }

        try:
            res = db.table("topics").insert(data).execute()
            if not res.data:
                raise HTTPException(status_code=500, detail="Database failed to return the created topic.")
            topic_record = res.data[0]
            
            # Schedule the first scan immediately
            try:
                from truebrief.tasks.scheduler import set_next_run
                set_next_run(topic_record["id"], interval_seconds=0)
            except Exception as sched_err:
                logger.warning(f"Could not auto-schedule first scan: {sched_err}")
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error creating topic: {error_msg}")
            raise HTTPException(status_code=400, detail=f"Database error: {error_msg}")

    # 3. Create subscription
    try:
        db.table("topic_subscriptions").insert({
            "user_id": val_uuid,
            "topic_id": topic_record["id"]
        }).execute()
    except Exception as sub_err:
        # Ignore unique constraint violations (already subscribed)
        if "duplicate key value" not in str(sub_err).lower() and "unique constraint" not in str(sub_err).lower():
            logger.warning(f"Failed to create topic subscription: {sub_err}")

    return topic_record


@router.get("/topics", response_model=List[TopicResponse])
def list_topics(user: Optional[User] = Depends(get_optional_user)):
    """
    List topics. If authenticated, returns only topics
    that the user is subscribed to. Otherwise returns all topics.
    """
    db = get_supabase()
    
    if user:
        val_uuid = user.id
        # Two-step fetch to avoid complex joins in Supabase python client
        subs = db.table("topic_subscriptions").select("topic_id").eq("user_id", val_uuid).execute()
        if not subs.data:
            return []
            
        topic_ids = [sub["topic_id"] for sub in subs.data]
        res = db.table("topics").select("*").in_("id", topic_ids).execute()
        return res.data
    else:
        # Return all topics (admin/debug mode)
        res = db.table("topics").select("*").execute()
        return res.data

@router.get("/topics/{topic_id}", response_model=TopicResponse)
def get_topic(topic_id: str):
    """Get a specific topic."""
    _require_uuid(topic_id, "topic_id")
    db = get_supabase()
    res = db.table("topics").select("*").eq("id", topic_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Topic not found")
    return res.data[0]

@router.delete("/topics/{topic_id}")
@limiter.limit("30/hour")
def delete_topic(request: Request, topic_id: str, user: User = Depends(get_current_user)):
    """Delete a topic."""
    _require_uuid(topic_id, "topic_id")
    db = get_supabase()
    res = db.table("topics").delete().eq("id", topic_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Topic not found")
    return {"status": "deleted"}

@router.post("/topics/{topic_id}/scan")
@limiter.limit("10/hour")
def trigger_scan(request: Request, topic_id: str, user: User = Depends(get_current_user)):
    """
    Queue the intelligence pipeline for a topic as a background task.

    Returns immediately with a task_id. Poll GET /scan-status/{task_id}
    to check progress and retrieve the brief once complete.

    Enforces per-tier scan frequency (HTTP 429 if scanning too soon).
    """
    db = get_supabase()
    res = db.table("topics").select("id, raw_query, last_scan_at").eq("id", topic_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Topic not found")

    topic_row = res.data[0]
    raw_query = topic_row["raw_query"]

    # --- Tier Enforcement: scan frequency ---
    val_uuid = user.id
    try:
        sub_res = (
            db.table("user_subscriptions")
            .select("tier")
            .eq("user_id", val_uuid)
            .execute()
        )
        tier_str = sub_res.data[0]["tier"] if sub_res.data else "free"

        last_scan_at: Optional[datetime] = None
        raw_last = topic_row.get("last_scan_at")
        if raw_last:
            try:
                last_scan_at = datetime.fromisoformat(raw_last.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                pass

        enforce_speed_limit(val_uuid, tier_str, last_scan_at)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Speed limit check skipped due to error: %s", e)

    from truebrief.tasks.pipeline_task import run_pipeline_task
    task = run_pipeline_task.delay(topic_id=topic_id, raw_query=raw_query)

    logger.info(f"Scan queued: topic_id={topic_id} task_id={task.id}")
    return {
        "status": "queued",
        "task_id": task.id,
        "topic_id": topic_id,
        "message": f"Pipeline running in background. Poll /api/v1/scan-status/{task.id} for results.",
    }


@router.get("/scan-status/{task_id}")
def get_scan_status(task_id: str):
    """
    Poll the status of a queued scan task.

    States:
      PENDING  - queued, not yet started
      STARTED  - pipeline is running
      SUCCESS  - complete, result contains the brief
      FAILURE  - pipeline crashed, result contains the error
    """
    from truebrief.tasks.celery_app import celery_app
    from celery.result import AsyncResult

    result = AsyncResult(task_id, app=celery_app)
    state = result.state

    response: dict = {"task_id": task_id, "state": state}

    if state == "PENDING":
        response["message"] = "Task is queued and waiting for a worker."

    elif state == "STARTED":
        response["message"] = "Pipeline is running..."

    elif state == "SUCCESS":
        response["message"] = "Pipeline complete."
        response["result"] = result.result  # dict: {status, content, brief_id}

    elif state == "FAILURE":
        response["message"] = "Pipeline failed."
        response["error"] = str(result.result)

    else:
        response["message"] = f"Unknown state: {state}"

    return response

@router.get("/topics/{topic_id}/briefs", response_model=List[BriefResponse])
def list_topic_briefs(topic_id: str):
    """Get all briefs for a topic."""
    _require_uuid(topic_id, "topic_id")
    db = get_supabase()
    res = db.table("briefs").select("*").eq("topic_id", topic_id).order("delivered_at", desc=True).execute()
    return res.data

class BriefHistoryResponse(BaseModel):
    topic_id: str
    topic_name: str
    brief_id: str
    created_at: str
    summary_preview: str

@router.get("/briefs/history", response_model=List[BriefHistoryResponse])
def get_briefs_history(user: User = Depends(get_current_user)):
    """Get all briefs for the current user across all topics, sorted newest-first."""
    db = get_supabase()
    val_uuid = user.id

    # Get all topic IDs the user is subscribed to
    subs = db.table("topic_subscriptions").select("topic_id").eq("user_id", val_uuid).execute()
    if not subs.data:
        return []

    topic_ids = [sub["topic_id"] for sub in subs.data]

    briefs = (
        db.table("briefs")
        .select("id, topic_id, content, delivered_at")
        .in_("topic_id", topic_ids)
        .order("delivered_at", desc=True)
        .limit(50)
        .execute()
    )

    topics_res = db.table("topics").select("id, raw_query").in_("id", topic_ids).execute()
    topic_map = {t["id"]: t["raw_query"] for t in topics_res.data}

    result = []
    for brief in briefs.data:
        preview = brief["content"].replace("#", "").replace("*", "").replace("`", "").replace("_", "").replace("\n", " ").strip()[:200]
        result.append({
            "topic_id": brief["topic_id"],
            "topic_name": topic_map.get(brief["topic_id"], "Unknown"),
            "brief_id": brief["id"],
            "created_at": brief["delivered_at"],
            "summary_preview": preview
        })

    return result

@router.get("/briefs/{brief_id}", response_model=BriefResponse)
def get_brief(brief_id: str):
    """Get a specific brief."""
    _require_uuid(brief_id, "brief_id")
    db = get_supabase()
    res = db.table("briefs").select("*").eq("id", brief_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Brief not found")
    return res.data[0]


class PublicBriefResponse(BaseModel):
    brief_id: str
    content: str
    delivered_at: str
    topic_name: str

@router.get("/share/{brief_id}", response_model=PublicBriefResponse)
def get_shared_brief(brief_id: str):
    """Public endpoint — no auth. Returns brief content for shareable links."""
    _require_uuid(brief_id, "brief_id")
    db = get_supabase()
    brief_res = db.table("briefs").select("*").eq("id", brief_id).execute()
    if not brief_res.data:
        raise HTTPException(status_code=404, detail="Brief not found")
    brief = brief_res.data[0]

    topic_res = db.table("topics").select("raw_query").eq("id", brief["topic_id"]).execute()
    topic_name = topic_res.data[0]["raw_query"] if topic_res.data else "Intelligence Brief"

    return {
        "brief_id": brief["id"],
        "content": brief["content"],
        "delivered_at": brief["delivered_at"],
        "topic_name": topic_name,
    }


class UserStatsResponse(BaseModel):
    total_briefs: int
    articles_scanned: int
    time_saved_minutes: int

@router.get("/users/me/stats", response_model=UserStatsResponse)
def get_user_stats(user: User = Depends(get_current_user)):
    """Return aggregate stats for the current user: briefs delivered, articles scanned, time saved."""
    db = get_supabase()

    subs = db.table("topic_subscriptions").select("topic_id").eq("user_id", user.id).execute()
    if not subs.data:
        return {"total_briefs": 0, "articles_scanned": 0, "time_saved_minutes": 0}

    topic_ids = [s["topic_id"] for s in subs.data]

    briefs_res = (
        db.table("briefs")
        .select("id", count="exact")
        .in_("topic_id", topic_ids)
        .execute()
    )
    total_briefs = briefs_res.count or 0

    facts_res = (
        db.table("known_facts")
        .select("id", count="exact")
        .in_("topic_id", topic_ids)
        .execute()
    )
    articles_scanned = facts_res.count or 0

    # Avg 4 min/article saved vs 2 min/brief to read
    time_saved = max(0, articles_scanned * 4 - total_briefs * 2)

    return {
        "total_briefs": total_briefs,
        "articles_scanned": articles_scanned,
        "time_saved_minutes": time_saved,
    }


@router.delete("/users/me")
def delete_account(user: User = Depends(get_current_user)):
    """
    Permanently delete the current user's account and all associated data.
    Cascades via FK: topics → known_facts, briefs, story_nodes, subscriptions.
    """
    db = get_supabase()
    try:
        db.table("users").delete().eq("id", user.id).execute()
    except Exception as exc:
        logger.error("Failed to delete user %s: %s", user.id, exc)
        raise HTTPException(status_code=500, detail="Account deletion failed")
    return {"status": "deleted"}


@router.get("/topics/{topic_id}/ayr")
def get_topic_ayr(topic_id: str, days: int = 30):
    """
    Get Alpha Yield Rate (AYR) stats for a topic.

    Returns overall yield rate (what % of scanned articles produced new facts),
    per-source-domain breakdown, and the recommended polling interval.

    Query params:
      days: Lookback window in days (default 30).

    Example response:
      {
        "topic_id": "...",
        "days": 30,
        "total": 42,
        "alphas": 18,
        "duplicates": 24,
        "ayr": 0.4286,
        "trusted": true,
        "recommended_interval_s": 3600,
        "by_domain": [
          {"source_domain": "reuters.com", "total": 15, "alphas": 9, "ayr": 0.6},
          ...
        ]
      }
    """
    # Verify topic exists first
    db = get_supabase()
    res = db.table("topics").select("id, raw_query, poll_interval_seconds").eq("id", topic_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Topic not found")

    topic = res.data[0]

    try:
        from truebrief.ledger.ayr_engine import calculate_topic_ayr
        stats = calculate_topic_ayr(topic_id, days=days)
    except Exception as exc:
        logger.error(f"AYR calculation failed for topic {topic_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"AYR calculation failed: {exc}")

    # Enrich with current topic info
    stats["raw_query"] = topic["raw_query"]
    stats["current_interval_s"] = topic["poll_interval_seconds"]

    return stats


@router.get("/topics/{topic_id}/query-variants")
def get_query_variants(topic_id: str):
    """
    List all search query variants for a topic.

    Shows which queries are active, how many times each was used,
    how many alphas each produced, and the current AYR per variant.

    Useful for debugging keyword rotation and understanding which search
    angles are producing the most novel information.

    Example response:
      [
        {
          "id": "...",
          "query_text": "TSMC semiconductor production",
          "scans_used": 8,
          "alphas_yielded": 5,
          "ayr": 0.625,
          "is_active": true,
          "generation": 0,
          "last_used_at": "2026-04-30T..."
        },
        ...
      ]
    """
    db = get_supabase()
    topic_res = db.table("topics").select("id").eq("id", topic_id).execute()
    if not topic_res.data:
        raise HTTPException(status_code=404, detail="Topic not found")

    res = (
        db.table("topic_query_variants")
        .select("id, query_text, scans_used, alphas_yielded, ayr, is_active, generation, created_at, last_used_at")
        .eq("topic_id", topic_id)
        .order("ayr", desc=True)
        .execute()
    )
    return res.data or []


@router.get("/topics/{topic_id}/stories")
def get_topic_stories(topic_id: str, limit: int = 50):
    """
    List all story nodes for a topic, newest-updated first.
    Each story includes summary, fact count, and last-update timestamp.
    """
    _require_uuid(topic_id, "topic_id")
    db = get_supabase()
    topic_res = db.table("topics").select("id").eq("id", topic_id).execute()
    if not topic_res.data:
        raise HTTPException(status_code=404, detail="Topic not found")

    res = (
        db.table("story_nodes")
        .select("id, topic_id, summary, status, fact_count, created_at, updated_at")
        .eq("topic_id", topic_id)
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


@router.get("/topics/{topic_id}/stories/{story_id}/facts")
def get_story_facts(topic_id: str, story_id: str):
    """
    List all facts (alphas) attached to a specific story node, newest first.
    """
    db = get_supabase()
    res = (
        db.table("known_facts")
        .select("id, alpha_text, confidence, source_url, source_domain, first_seen_at, event_date")
        .eq("topic_id", topic_id)
        .eq("story_node_id", story_id)
        .order("first_seen_at", desc=True)
        .execute()
    )
    return res.data or []


# ---------------------------------------------------------------------------
# Admin: Cost & Latency Telemetry (A.1.4)
# ---------------------------------------------------------------------------

class CostSummaryResponse(BaseModel):
    period_days: int
    total_runs: int
    total_cost_usd: float
    avg_cost_per_run_usd: float
    total_input_tokens: int
    total_output_tokens: int
    by_stage: List[dict]
    by_day: List[dict]


@router.get("/admin/cost-summary", response_model=CostSummaryResponse)
def get_cost_summary(
    days: int = 30,
    _user: User = Depends(get_current_user),
):
    """
    Admin endpoint: aggregated LLM cost & latency for the last N days.
    Returns totals, per-stage breakdown, and per-day cost series.
    Accessible to any authenticated user (founder-only enforcement via Clerk roles is future work).
    """
    db = get_supabase()

    # -- Per-stage aggregation from llm_call_log --
    try:
        stage_res = db.rpc(
            "llm_cost_by_stage",
            {"days_back": days},
        ).execute()
        by_stage = stage_res.data or []
    except Exception:
        # RPC may not exist yet (before migration runs); fall back to empty
        by_stage = []

    # -- Per-day aggregation --
    try:
        day_res = db.rpc(
            "llm_cost_by_day",
            {"days_back": days},
        ).execute()
        by_day = day_res.data or []
    except Exception:
        by_day = []

    # -- Totals from pipeline_run --
    try:
        run_res = db.rpc("pipeline_run_summary", {"days_back": days}).execute()
        totals = run_res.data[0] if run_res.data else {}
    except Exception:
        totals = {}

    total_cost = sum(float(r.get("total_cost_usd", 0)) for r in by_stage)
    total_in = sum(int(r.get("total_input_tokens", 0)) for r in by_stage)
    total_out = sum(int(r.get("total_output_tokens", 0)) for r in by_stage)
    total_runs = int(totals.get("total_runs", 0))
    avg_cost = (total_cost / total_runs) if total_runs > 0 else 0.0

    return {
        "period_days": days,
        "total_runs": total_runs,
        "total_cost_usd": round(total_cost, 6),
        "avg_cost_per_run_usd": round(avg_cost, 6),
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "by_stage": by_stage,
        "by_day": by_day,
    }


# ---------------------------------------------------------------------------
# Shared topics search (for New Topic suggestion pills)
# ---------------------------------------------------------------------------

class SharedTopicResult(BaseModel):
    id: str
    name: str
    subscriber_count: int

@router.get("/shared-topics", response_model=List[SharedTopicResult])
def search_shared_topics(q: str = ""):
    """Search existing topics by name substring — used for suggestion pills on New Topic page."""
    db = get_supabase()
    if q and len(q) >= 2:
        res = db.table("topics").select("id, raw_query").ilike("raw_query", f"%{q}%").limit(5).execute()
    else:
        res = db.table("topics").select("id, raw_query").limit(5).execute()
    return [{"id": t["id"], "name": t["raw_query"], "subscriber_count": 0} for t in res.data or []]


# ---------------------------------------------------------------------------
# Dashboard endpoint
# ---------------------------------------------------------------------------

class DashboardItem(BaseModel):
    topic_id: str
    topic_name: str
    frequency: str
    last_scanned_at: Optional[str]
    new_count: int
    update_count: int
    preview_text: str


@router.get("/dashboard", response_model=List[DashboardItem])
def get_dashboard(user: User = Depends(get_current_user)):
    """Return topics with unread updates for the dashboard feed."""
    db = get_supabase()

    subs = db.table("topic_subscriptions").select("topic_id").eq("user_id", user.id).execute()
    if not subs.data:
        return []

    topic_ids = [sub["topic_id"] for sub in subs.data]
    topics_res = db.table("topics").select("*").in_("id", topic_ids).execute()

    result = []
    for topic in topics_res.data:
        briefs_res = (
            db.table("briefs")
            .select("id, content, delivered_at")
            .eq("topic_id", topic["id"])
            .eq("is_read", False)
            .order("delivered_at", desc=True)
            .execute()
        )
        new_count = len(briefs_res.data)
        if new_count == 0:
            continue

        latest = briefs_res.data[0]
        raw = latest["content"].replace("#", "").replace("*", "").replace("`", "").replace("_", "").strip()
        sentences = [s.strip() for s in raw.replace("\n", " ").split(".") if len(s.strip()) > 10]
        preview = (sentences[0] + ".") if sentences else raw[:200]

        result.append({
            "topic_id": topic["id"],
            "topic_name": topic["raw_query"],
            "frequency": topic.get("frequency", "Auto"),
            "last_scanned_at": topic.get("last_checked_at"),
            "new_count": new_count,
            "update_count": 0,
            "preview_text": preview,
        })

    result.sort(key=lambda x: x["last_scanned_at"] or "", reverse=True)
    return result


# ---------------------------------------------------------------------------
# Topic facts (for the thread-based topic view)
# ---------------------------------------------------------------------------

class FactSourceResponse(BaseModel):
    name: str
    domain: str
    url: Optional[str] = None
    original_sentence: Optional[str] = None


class FactResponse(BaseModel):
    id: str
    alpha_text: str
    published_at: str
    sources: List[FactSourceResponse]


@router.get("/topics/{topic_id}/facts", response_model=List[FactResponse])
def get_topic_facts(topic_id: str, user: User = Depends(get_current_user)):
    """Return all known facts for a topic sorted oldest-first for the thread view."""
    _require_uuid(topic_id, "topic_id")
    db = get_supabase()

    res = (
        db.table("known_facts")
        .select("id, alpha_text, source_url, source_domain, first_seen_at")
        .eq("topic_id", topic_id)
        .order("first_seen_at", desc=False)
        .execute()
    )

    facts = []
    for fact in res.data or []:
        sources = []
        if fact.get("source_domain"):
            sources.append({
                "name": fact["source_domain"],
                "domain": fact["source_domain"],
                "url": fact.get("source_url"),
                "original_sentence": None,
            })
        facts.append({
            "id": fact["id"],
            "alpha_text": fact["alpha_text"],
            "published_at": fact["first_seen_at"],
            "sources": sources,
        })
    return facts


@router.delete("/facts/{fact_id}/dismiss")
def dismiss_fact(fact_id: str, user: User = Depends(get_current_user)):
    """Remove a fact from the user's view (hard delete — dedup uses embeddings)."""
    _require_uuid(fact_id, "fact_id")
    db = get_supabase()
    db.table("known_facts").delete().eq("id", fact_id).execute()
    return {"ok": True}
