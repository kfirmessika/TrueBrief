"""
API Routes - api/routes.py

Topic CRUD and pipeline triggers.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import logging
from datetime import datetime
from uuid import UUID

from truebrief.ledger.database import get_supabase
from truebrief.billing.tiers import enforce_topic_limit, enforce_speed_limit
from truebrief.auth.dependencies import User, get_current_user, get_optional_user
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

class BriefResponse(BaseModel):
    id: str
    topic_id: str
    content: str
    delivered_at: str

# --- Endpoints ---

@router.post("/topics", response_model=TopicResponse)
def create_topic(topic: TopicCreate, user: User = Depends(get_current_user)):
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
    db = get_supabase()
    res = db.table("topics").select("*").eq("id", topic_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Topic not found")
    return res.data[0]

@router.delete("/topics/{topic_id}")
def delete_topic(topic_id: str, user: User = Depends(get_current_user)):
    """Delete a topic."""
    db = get_supabase()
    res = db.table("topics").delete().eq("id", topic_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Topic not found")
    return {"status": "deleted"}

@router.post("/topics/{topic_id}/scan")
def trigger_scan(topic_id: str, user: User = Depends(get_current_user)):
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
    db = get_supabase()
    res = db.table("briefs").select("*").eq("topic_id", topic_id).order("delivered_at", desc=True).execute()
    return res.data

@router.get("/briefs/{brief_id}", response_model=BriefResponse)
def get_brief(brief_id: str):
    """Get a specific brief."""
    db = get_supabase()
    res = db.table("briefs").select("*").eq("id", brief_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Brief not found")
    return res.data[0]


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
