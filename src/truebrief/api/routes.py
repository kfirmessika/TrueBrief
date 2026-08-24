"""
API Routes - api/routes.py

Topic CRUD and pipeline triggers.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field, model_validator
from typing import List, Optional
import json
import logging
import math
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
from truebrief.billing.tiers import enforce_topic_limit, enforce_speed_limit, _get_limits
from truebrief.auth.dependencies import User, get_current_user, get_optional_user
from truebrief.api.rate_limit import limiter
from truebrief.llm.client import LLMClient
from truebrief.llm.prompts import (
    build_dashboard_summary_prompt,
    build_story_stitch_batch_prompt,
    build_story_stitch_pair_prompt,
    build_topic_finisher_combined_prompt,
    DASHBOARD_SUMMARY_SYSTEM,
    STORY_STITCH_SYSTEM,
    TOPIC_FINISHER_COMBINED_SYSTEM,
)
from config.settings import settings


def _require_subscription(db, topic_id: str, user_id: str) -> None:
    """Raise 403 if the user is not subscribed to the topic."""
    sub = (
        db.table("topic_subscriptions")
        .select("topic_id")
        .eq("user_id", user_id)
        .eq("topic_id", topic_id)
        .execute()
    )
    if not sub.data:
        raise HTTPException(status_code=403, detail="Not subscribed to this topic")


def _require_topic_owner(db, topic_id: str, user_id: str) -> None:
    """Raise 403 if the user is not the creator of the topic."""
    topic = (
        db.table("topics")
        .select("user_id")
        .eq("id", topic_id)
        .execute()
    )
    if not topic.data or topic.data[0].get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this topic")


def _finish_topic_fields(raw_query: str) -> tuple[str, str]:
    """Derive (name, search_prompt) for a newly-created topic via the topic_finisher
    LLM step. Fails SOFT on any error (quota, malformed JSON, timeout, etc.) — falls
    back to (raw_query, raw_query), today's exact behavior, so topic creation is never
    blocked by an LLM hiccup. Logs the fallback at WARNING level."""
    try:
        llm = LLMClient()
        prompt = build_topic_finisher_combined_prompt(raw_query)
        raw_response = llm.call(
            step_name="topic_finisher_combined",
            prompt=prompt,
            system_prompt=TOPIC_FINISHER_COMBINED_SYSTEM,
            json_mode=True,
        )
        parsed = json.loads(raw_response)
        name = parsed.get("name")
        search_prompt = parsed.get("search_prompt")
        if not name or not isinstance(name, str) or not name.strip():
            raise ValueError(f"topic_finisher_combined returned no usable 'name': {parsed!r}")
        if not search_prompt or not isinstance(search_prompt, str) or not search_prompt.strip():
            raise ValueError(f"topic_finisher_combined returned no usable 'search_prompt': {parsed!r}")
        return name.strip(), search_prompt.strip()
    except Exception as exc:
        logger.warning(
            "topic_finisher_combined failed for raw_query=%r — falling back to raw_query "
            "for both name and search_prompt. Reason: %s",
            raw_query, exc,
        )
        return raw_query, raw_query


def _require_founder(user: User) -> None:
    """Raise 403 unless the user is the configured founder.

    Fails CLOSED: if FOUNDER_EMAIL is unset, nobody is the founder. An unset
    admin gate must never grant access to every authenticated user.
    """
    if not settings.FOUNDER_EMAIL:
        logger.error("FOUNDER_EMAIL is not set — denying admin access (fail-closed).")
        raise HTTPException(status_code=403, detail="Not authorized")
    if user.email != settings.FOUNDER_EMAIL:
        raise HTTPException(status_code=403, detail="Not authorized")


def _require_admin(user: User) -> None:
    """Raise 403 unless the user is an admin per billing.tiers.is_admin
    (settings.ADMIN_EMAILS). Fails CLOSED: an unset/empty allowlist admits nobody."""
    from truebrief.billing.tiers import is_admin
    if not is_admin(user.email):
        raise HTTPException(status_code=403, detail="Not authorized")

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Pydantic Models for API ---
class TopicCreate(BaseModel):
    # Bounded: raw_query flows into LLM prompts, search queries, and embeddings.
    # A cap limits prompt-injection surface and oversized/costly inputs.
    raw_query: str = Field(min_length=1, max_length=200)
    poll_interval_seconds: Optional[int] = None  # None = use tier default

    @model_validator(mode="after")
    def _strip_control_chars(self):
        # Remove control chars (keep normal whitespace) that could smuggle prompt
        # structure into the LLM steps.
        cleaned = "".join(
            ch for ch in self.raw_query if ch == " " or ch == "\t" or ord(ch) >= 0x20
        ).strip()
        if not cleaned:
            raise ValueError("raw_query must contain visible characters")
        self.raw_query = cleaned
        return self

def _scan_is_recent(started_at, max_minutes: int = 15) -> bool:
    """True if scan_started_at is set and within max_minutes (staleness guard: a
    crashed run that never cleared its stamp must not show 'scanning' forever)."""
    if not started_at:
        return False
    try:
        dt = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)
        return (datetime.utcnow() - dt).total_seconds() < max_minutes * 60
    except Exception:
        return False


class TopicResponse(BaseModel):
    id: str
    raw_query: str
    name: Optional[str] = None
    search_prompt: Optional[str] = None
    frequency: Optional[str] = None
    is_active: bool
    last_scan_at: Optional[str] = None
    scan_started_at: Optional[str] = None
    is_scanning: bool = False
    is_public: bool = False

    @model_validator(mode='before')
    @classmethod
    def _derive_fields(cls, data):
        if isinstance(data, dict):
            data = dict(data)
            if 'last_run_at' in data and 'last_scan_at' not in data:
                data['last_scan_at'] = data.get('last_run_at')
            # Live scan state, with a staleness guard so a crashed run never sticks "on".
            data['is_scanning'] = _scan_is_recent(data.get('scan_started_at'))
        return data

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
    from truebrief.billing.tiers import is_admin
    if not is_admin(user.email):
        enforce_topic_limit(val_uuid, tier_str, current_count)

    # 1. Check if topic already exists (canonical match on lowercased raw_query)
    normalized_query = topic.raw_query.strip().lower()
    existing = db.table("topics").select("*").eq("raw_query", normalized_query).execute()
    if existing.data:
        topic_record = existing.data[0]
        logger.info(f"Topic '{normalized_query}' already exists. Subscribing user.")
    else:
        # 2. Create new shared topic — no user_id, the subscription table owns ownership.
        # V5 (docs/core/architecture_v5.md §7): manual alarm-clock scheduling replaces
        # AYR-managed poll_interval_seconds. A new topic gets zero topic_schedule_times
        # rows (= the one-run/day default, see ledger/alarm_schedule.py); the user adds
        # specific times via PUT /topics/{id}/schedule.
        _name, _search_prompt = _finish_topic_fields(normalized_query)
        data = {
            "raw_query": normalized_query,
            "name": _name,
            "search_prompt": _search_prompt,
            "user_id": val_uuid,  # kept as original-creator metadata only
        }

        try:
            res = db.table("topics").insert(data).execute()
            if not res.data:
                raise HTTPException(status_code=500, detail="Database failed to return the created topic.")
            topic_record = res.data[0]

            try:
                from truebrief.tasks.scheduler import set_next_run
                set_next_run(topic_record["id"])
            except Exception as sched_next_err:
                logger.warning("Could not set initial next_run_at: %s", sched_next_err)

            # Embed the raw_query so relevance scores can be computed for its facts.
            try:
                _llm = LLMClient()
                _embedding = _llm.embed(normalized_query)
                db.table("topics").update({"topic_embedding": _embedding}).eq("id", topic_record["id"]).execute()
            except Exception as _emb_err:
                logger.warning("Topic embedding failed (non-fatal): %s", _emb_err)

            # Fire the first scan immediately
            _first_task_id = None
            try:
                from truebrief.tasks.pipeline_task import enqueue_pipeline
                _task = enqueue_pipeline(
                    topic_id=topic_record["id"],
                    raw_query=topic_record.get("search_prompt") or topic_record["raw_query"],
                )
                _first_task_id = _task.id
                logger.info(f"First scan enqueued for new topic {topic_record['id']} task={_first_task_id}")
                # Stamp scanning immediately so the new topic shows a live state at once.
                try:
                    db.table("topics").update(
                        {"scan_started_at": datetime.utcnow().isoformat()}
                    ).eq("id", topic_record["id"]).execute()
                except Exception:
                    pass
            except Exception as sched_err:
                logger.warning(f"Could not enqueue first scan: {sched_err}")
            # Attach task_id to response so frontend can show progress bar
            topic_record = dict(topic_record)
            topic_record["scan_task_id"] = _first_task_id

        except Exception as e:
            logger.error(f"Error creating topic: {e}")
            raise HTTPException(status_code=400, detail="Could not create topic.")

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


class AdminTopicCreate(BaseModel):
    # Same bound as TopicCreate — raw_query flows into LLM prompts/search/embeddings.
    raw_query: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _strip_control_chars(self):
        cleaned = "".join(
            ch for ch in self.raw_query if ch == " " or ch == "\t" or ord(ch) >= 0x20
        ).strip()
        if not cleaned:
            raise ValueError("raw_query must contain visible characters")
        self.raw_query = cleaned
        return self


@router.post("/admin/public-topics", response_model=TopicResponse)
@limiter.limit("20/hour")
def create_public_topic(request: Request, topic: AdminTopicCreate, user: User = Depends(get_current_user)):
    """
    Admin-only: create (or promote) a topic and mark it is_public=true.
    Regular users can never set is_public — this is the only path that flips it on
    a newly-created topic. Bypasses tier topic-cap enforcement (admin).
    """
    _require_admin(user)
    db = get_supabase()
    val_uuid = user.id

    normalized_query = topic.raw_query.strip().lower()
    existing = db.table("topics").select("*").eq("raw_query", normalized_query).execute()
    if existing.data:
        topic_record = existing.data[0]
        if not topic_record.get("is_public"):
            upd = db.table("topics").update({"is_public": True}).eq("id", topic_record["id"]).execute()
            topic_record = upd.data[0] if upd.data else {**topic_record, "is_public": True}
        logger.info(f"Admin {user.email}: topic '{normalized_query}' already exists, marked public.")
    else:
        _name, _search_prompt = _finish_topic_fields(normalized_query)
        data = {
            "raw_query": normalized_query,
            "name": _name,
            "search_prompt": _search_prompt,
            "user_id": val_uuid,  # original-creator metadata only
            "is_public": True,
        }
        try:
            res = db.table("topics").insert(data).execute()
            if not res.data:
                raise HTTPException(status_code=500, detail="Database failed to return the created topic.")
            topic_record = res.data[0]

            try:
                from truebrief.tasks.scheduler import set_next_run
                set_next_run(topic_record["id"])
            except Exception as sched_next_err:
                logger.warning("Could not set initial next_run_at: %s", sched_next_err)

            try:
                _llm = LLMClient()
                _embedding = _llm.embed(normalized_query)
                db.table("topics").update({"topic_embedding": _embedding}).eq("id", topic_record["id"]).execute()
            except Exception as _emb_err:
                logger.warning("Topic embedding failed (non-fatal): %s", _emb_err)

            _first_task_id = None
            try:
                from truebrief.tasks.pipeline_task import enqueue_pipeline
                _task = enqueue_pipeline(
                    topic_id=topic_record["id"],
                    raw_query=topic_record.get("search_prompt") or topic_record["raw_query"],
                )
                _first_task_id = _task.id
                logger.info(f"First scan enqueued for new public topic {topic_record['id']} task={_first_task_id}")
                try:
                    db.table("topics").update(
                        {"scan_started_at": datetime.utcnow().isoformat()}
                    ).eq("id", topic_record["id"]).execute()
                except Exception:
                    pass
            except Exception as sched_err:
                logger.warning(f"Could not enqueue first scan: {sched_err}")
            topic_record = dict(topic_record)
            topic_record["scan_task_id"] = _first_task_id

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating public topic: {e}")
            raise HTTPException(status_code=400, detail="Could not create topic.")

    try:
        db.table("topic_subscriptions").insert({
            "user_id": val_uuid,
            "topic_id": topic_record["id"]
        }).execute()
    except Exception as sub_err:
        if "duplicate key value" not in str(sub_err).lower() and "unique constraint" not in str(sub_err).lower():
            logger.warning(f"Failed to create admin subscription to public topic: {sub_err}")

    return topic_record


class TopicVisibilityUpdate(BaseModel):
    is_public: bool


@router.patch("/admin/topics/{topic_id}/public", response_model=TopicResponse)
@limiter.limit("30/hour")
def set_topic_visibility(
    request: Request,
    topic_id: str,
    body: TopicVisibilityUpdate,
    user: User = Depends(get_current_user),
):
    """Admin-only: toggle an existing topic's is_public flag."""
    _require_admin(user)
    _require_uuid(topic_id, "topic_id")
    db = get_supabase()
    res = db.table("topics").select("*").eq("id", topic_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Topic not found")
    upd = db.table("topics").update({"is_public": body.is_public}).eq("id", topic_id).execute()
    return upd.data[0] if upd.data else {**res.data[0], "is_public": body.is_public}


@router.get("/topics", response_model=List[TopicResponse])
def list_topics(user: User = Depends(get_current_user)):
    """List topics the authenticated user is subscribed to."""
    db = get_supabase()
    res = (
        db.table("topic_subscriptions")
        .select("topics(*)")
        .eq("user_id", user.id)
        .execute()
    )
    return [row["topics"] for row in (res.data or []) if row.get("topics")]

@router.get("/topics/{topic_id}", response_model=TopicResponse)
def get_topic(topic_id: str, user: User = Depends(get_current_user)):
    """Get a specific topic the user is subscribed to."""
    _require_uuid(topic_id, "topic_id")
    db = get_supabase()
    _require_subscription(db, topic_id, user.id)
    res = db.table("topics").select("*").eq("id", topic_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Topic not found")
    return res.data[0]

@router.get("/topics/{topic_id}/known-facts")
def get_known_facts(topic_id: str, user: User = Depends(get_current_user)):
    """Return all known_facts for a topic (source domain, URL, text snippet, date)."""
    _require_uuid(topic_id, "topic_id")
    db = get_supabase()
    _require_subscription(db, topic_id, user.id)
    # IC4 columns (contradicts_id, contradiction_note) come from migration 015.
    # Fall back to the base columns if that migration hasn't been applied yet, so
    # the source-chip tooltips never break on a pre-015 database.
    base_cols = "source_domain, source_url, alpha_text, first_seen_at, context, event_class, event_date, verified_count, relevance"
    try:
        res = (
            db.table("known_facts")
            .select(base_cols + ", contradicts_id, contradiction_note")
            .eq("topic_id", topic_id)
            .order("first_seen_at", desc=True)
            .limit(300)
            .execute()
        )
    except Exception:
        res = (
            db.table("known_facts")
            .select(base_cols)
            .eq("topic_id", topic_id)
            .order("first_seen_at", desc=True)
            .limit(300)
            .execute()
        )
    return res.data


@router.get("/topics/{topic_id}/state-of-play")
def get_state_of_play(topic_id: str, user: User = Depends(get_current_user)):
    """Return the IC7 state-of-play block for a topic, or null if none yet."""
    _require_uuid(topic_id, "topic_id")
    db = get_supabase()
    _require_subscription(db, topic_id, user.id)
    from truebrief.ledger.state_of_play_store import load_state_of_play
    return {"state_of_play": load_state_of_play(topic_id)}


@router.get("/topics/{topic_id}/history")
def get_history(topic_id: str, user: User = Depends(get_current_user)):
    """Return the V3 history doc (§7.2) — the topic's no-LLM 'story so far' timeline.

    Reads the stored doc when present, falling back to a live build so it works even
    before the pipeline has rebuilt it (or if migration 018 isn't applied yet)."""
    _require_uuid(topic_id, "topic_id")
    db = get_supabase()
    from truebrief.ledger.history_doc import get_history_doc
    return get_history_doc(topic_id, db=db, user_id=user.id)


@router.delete("/topics/{topic_id}")
@limiter.limit("30/hour")
def delete_topic(request: Request, topic_id: str, user: User = Depends(get_current_user)):
    """
    Unsubscribe the calling user from a topic.
    The topic row itself is only deleted when no subscribers remain.
    """
    _require_uuid(topic_id, "topic_id")
    db = get_supabase()
    _require_subscription(db, topic_id, user.id)

    # Remove this user's subscription
    db.table("topic_subscriptions").delete().eq("user_id", user.id).eq("topic_id", topic_id).execute()

    # Delete the topic only if it now has zero subscribers
    remaining = (
        db.table("topic_subscriptions")
        .select("topic_id", count="exact")
        .eq("topic_id", topic_id)
        .execute()
    )
    if (remaining.count or 0) == 0:
        db.table("topics").delete().eq("id", topic_id).execute()
        logger.info(f"Topic {topic_id} deleted (no subscribers remaining).")

    return {"status": "unsubscribed"}

class ScheduleTime(BaseModel):
    hour: int    # 0-23, UTC
    minute: int = 0  # 0-59, UTC

class ScheduleTimesUpdate(BaseModel):
    times: list[ScheduleTime]  # empty list = default (one run/day)

class SummaryRequest(BaseModel):
    facts: list[str]  # up to 20 fact texts to summarise


class StoryRequest(BaseModel):
    facts: list[str]  # ordered fact texts (chronological); connectors bridge adjacent pairs
    # V4-4: optional fact IDs (same order as facts). When provided and V4_STORY_STITCHING is
    # enabled, the endpoint looks up cached stitches from fact_stitches before calling the LLM.
    fact_ids: Optional[list[str]] = None


@router.get("/topics/{topic_id}/schedule")
@limiter.limit("60/hour")
def get_topic_schedule(request: Request, topic_id: str, user: User = Depends(get_current_user)):
    """
    V5 (docs/core/architecture_v5.md §7): a topic's configured daily alarm-clock run
    times (UTC). Empty list = default, one run/day (ledger/alarm_schedule.py).
    """
    _require_uuid(topic_id, "topic_id")
    db = get_supabase()
    _require_subscription(db, topic_id, user.id)

    from truebrief.ledger.alarm_schedule import DEFAULT_HOUR, DEFAULT_MINUTE, get_schedule_times

    times = get_schedule_times(db, topic_id)
    is_default = not times
    if is_default:
        times = [(DEFAULT_HOUR, DEFAULT_MINUTE)]

    return {
        "times": [{"hour": h, "minute": m} for h, m in times],
        "is_default": is_default,
    }


@router.put("/topics/{topic_id}/schedule")
@limiter.limit("30/hour")
def put_topic_schedule(
    request: Request,
    topic_id: str,
    body: ScheduleTimesUpdate,
    user: User = Depends(get_current_user),
):
    """
    Replace a topic's alarm-clock run times. Sends times=[] to reset to the default
    (one run/day). Enforces the user's tier floor as MINIMUM SPACING between any two
    times (reuses models/tier.py TIER_LIMITS.min_interval_hours — the existing "this
    tier can't scan faster than X" meaning — rather than a separate max-count limit).
    """
    _require_uuid(topic_id, "topic_id")
    db = get_supabase()
    _require_subscription(db, topic_id, user.id)

    from truebrief.ledger.alarm_schedule import min_spacing_hours_ok, set_schedule_times
    from truebrief.tasks.scheduler import set_next_run

    sub_res = db.table("user_subscriptions").select("tier").eq("user_id", user.id).execute()
    tier_str = sub_res.data[0]["tier"] if sub_res.data else "free"
    floor_hours = _get_limits(tier_str).min_interval_hours

    times = [(t.hour, t.minute) for t in body.times]
    for h, m in times:
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise HTTPException(status_code=422, detail=f"Invalid time {h:02d}:{m:02d}.")

    if not min_spacing_hours_ok(times, floor_hours):
        raise HTTPException(
            status_code=402,
            detail=f"Your plan requires at least {floor_hours}h between scheduled run times.",
        )

    set_schedule_times(db, topic_id, times)
    set_next_run(topic_id)

    logger.info(f"Topic {topic_id} schedule updated: {times}")
    return {"times": [{"hour": h, "minute": m} for h, m in times]}


class TopicRenameRequest(BaseModel):
    # Same bound as raw_query — this text becomes both the display name and the
    # literal search_prompt, so it flows into LLM prompts/search/embeddings too.
    name: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _strip_control_chars(self):
        cleaned = "".join(
            ch for ch in self.name if ch == " " or ch == "\t" or ord(ch) >= 0x20
        ).strip()
        if not cleaned:
            raise ValueError("name must contain visible characters")
        self.name = cleaned
        return self


@router.patch("/topics/{topic_id}", response_model=TopicResponse)
@limiter.limit("30/hour")
def rename_topic(
    request: Request,
    topic_id: str,
    body: TopicRenameRequest,
    user: User = Depends(get_current_user),
):
    """
    Owner-only: rename a topic. Sets BOTH `name` and `search_prompt` to the submitted
    text verbatim — no LLM finishing call on rename (intentional simplification).
    `raw_query` (used for exact-match dedup on topic creation) is never touched.
    """
    _require_uuid(topic_id, "topic_id")
    db = get_supabase()
    _require_topic_owner(db, topic_id, user.id)

    upd = (
        db.table("topics")
        .update({"name": body.name, "search_prompt": body.name})
        .eq("id", topic_id)
        .execute()
    )
    if not upd.data:
        raise HTTPException(status_code=404, detail="Topic not found")

    logger.info(f"Topic {topic_id} renamed to '{body.name}' by {user.email}")
    return upd.data[0]


@router.post("/topics/{topic_id}/scan")
@limiter.limit("60/hour")   # coarse per-IP abuse guard; per-user tier limit is the real throttle (admins bypass it)
def trigger_scan(request: Request, topic_id: str, user: User = Depends(get_current_user)):
    """
    Queue the intelligence pipeline for a topic as a background task.

    Returns immediately with a task_id. Poll GET /scan-status/{task_id}
    to check progress and retrieve the brief once complete.

    Enforces per-tier scan frequency (HTTP 429 if scanning too soon).
    """
    db = get_supabase()
    _require_subscription(db, topic_id, user.id)
    res = db.table("topics").select("id, raw_query, search_prompt, last_run_at").eq("id", topic_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Topic not found")

    topic_row = res.data[0]
    raw_query = topic_row.get("search_prompt") or topic_row["raw_query"]

    # --- Tier Enforcement: scan frequency (admins bypass entirely) ---
    val_uuid = user.id
    from truebrief.billing.tiers import is_admin
    if is_admin(user.email):
        logger.info("Admin %s — bypassing scan speed limit.", user.email)
    else:
        try:
            sub_res = (
                db.table("user_subscriptions")
                .select("tier")
                .eq("user_id", val_uuid)
                .execute()
            )
            tier_str = sub_res.data[0]["tier"] if sub_res.data else "free"

            last_scan_at: Optional[datetime] = None
            raw_last = topic_row.get("last_run_at")
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

    from truebrief.tasks.pipeline_task import enqueue_pipeline
    task = enqueue_pipeline(topic_id=topic_id, raw_query=raw_query)

    # Stamp scanning immediately so the UI shows a live state before the worker
    # picks the task up (the task clears it when the run ends).
    try:
        db.table("topics").update(
            {"scan_started_at": datetime.utcnow().isoformat()}
        ).eq("id", topic_id).execute()
    except Exception:
        pass

    logger.info(f"Scan queued: topic_id={topic_id} task_id={task.id}")
    return {
        "status": "queued",
        "task_id": task.id,
        "topic_id": topic_id,
        "message": f"Pipeline running in background. Poll /api/v1/scan-status/{task.id} for results.",
    }


@router.get("/scan-status/{task_id}")
def get_scan_status(task_id: str, user: User = Depends(get_current_user)):
    """
    Poll the status of a queued scan task.

    States:
      PENDING  - queued, not yet started
      STARTED  - pipeline is running
      SUCCESS  - complete, result contains the brief
      FAILURE  - pipeline crashed, result contains the error
    """
    from truebrief.tasks.pipeline_task import get_thread_task_state, get_task_topic_id

    # Ownership check: task_id alone must not be enough to read another
    # user's scan result. If we know which topic this task belongs to,
    # require a subscription (raises 403 for non-subscribers). If the
    # mapping is unknown (e.g. the process restarted since enqueue), fall
    # back to state-only below — the result/error payload is only ever
    # returned once ownership is verified.
    db = get_supabase()
    owner_topic_id = get_task_topic_id(task_id)
    if owner_topic_id is not None:
        _require_subscription(db, owner_topic_id, user.id)

    # Thread-based tasks (no Redis) take priority
    thread_state = get_thread_task_state(task_id)
    if thread_state is not None:
        state = thread_state["state"]
        response: dict = {"task_id": task_id, "state": state}
        if state == "PENDING":
            response["message"] = "Task is queued and waiting."
        elif state == "STARTED":
            response["message"] = "Pipeline is running..."
        elif state == "SUCCESS":
            response["message"] = "Pipeline complete."
            if owner_topic_id is not None:
                response["result"] = thread_state.get("result")
        elif state == "FAILURE":
            response["message"] = "Pipeline failed."
            if owner_topic_id is not None:
                response["error"] = str(thread_state.get("result", {}).get("error", ""))
        return response

    # Celery-based tasks (Redis available)
    from truebrief.tasks.celery_app import celery_app
    from celery.result import AsyncResult

    result = AsyncResult(task_id, app=celery_app)
    state = result.state

    response = {"task_id": task_id, "state": state}

    if state == "PENDING":
        response["message"] = "Task is queued and waiting for a worker."
    elif state == "STARTED":
        response["message"] = "Pipeline is running..."
    elif state == "SUCCESS":
        response["message"] = "Pipeline complete."
        if owner_topic_id is not None:
            response["result"] = result.result
    elif state == "FAILURE":
        response["message"] = "Pipeline failed."
        if owner_topic_id is not None:
            response["error"] = str(result.result)
    else:
        response["message"] = f"Unknown state: {state}"

    return response

@router.get("/topics/{topic_id}/briefs", response_model=List[BriefResponse])
def list_topic_briefs(topic_id: str, user: User = Depends(get_current_user)):
    """Get all briefs for a topic the user is subscribed to."""
    _require_uuid(topic_id, "topic_id")
    db = get_supabase()
    _require_subscription(db, topic_id, user.id)
    # V5 only — pre-cutover briefs came from the frozen V4 pipeline and are hidden
    # from the UI (config/settings.py V5_CUTOVER_DATE). Rows stay in the DB.
    from config.settings import V5_CUTOVER_DATE
    res = (
        db.table("briefs")
        .select("*")
        .eq("topic_id", topic_id)
        .gte("delivered_at", V5_CUTOVER_DATE)
        .order("delivered_at", desc=True)
        .execute()
    )
    return res.data


@router.post("/topics/{topic_id}/briefs/mark-read")
def mark_topic_briefs_read(topic_id: str, user: User = Depends(get_current_user)):
    """Mark all unread briefs for a topic as read. Called when user opens the topic page."""
    _require_uuid(topic_id, "topic_id")
    db = get_supabase()
    _require_subscription(db, topic_id, user.id)
    db.table("briefs").update({"is_read": True}).eq("topic_id", topic_id).eq("is_read", False).execute()
    return {"status": "ok"}

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

    topics_res = db.table("topics").select("id, raw_query, name").in_("id", topic_ids).execute()
    topic_map = {t["id"]: (t.get("name") or t["raw_query"]) for t in topics_res.data}

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
def get_brief(brief_id: str, user: User = Depends(get_current_user)):
    """Get a specific brief the user has access to."""
    _require_uuid(brief_id, "brief_id")
    db = get_supabase()
    res = db.table("briefs").select("*").eq("id", brief_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Brief not found")
    brief = res.data[0]
    _require_subscription(db, brief["topic_id"], user.id)
    return brief


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

    topic_res = db.table("topics").select("raw_query, name").eq("id", brief["topic_id"]).execute()
    topic_name = (
        (topic_res.data[0].get("name") or topic_res.data[0]["raw_query"])
        if topic_res.data else "Intelligence Brief"
    )

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
    # Lets the sidebar decide whether to show the Admin link at all, instead of showing
    # it to every user and letting non-admins hit a 403 on click. Piggybacks on this
    # endpoint (already fetched by Settings) rather than adding a new one just for a
    # boolean. /admin/* itself is still independently gated server-side by _is_admin —
    # this field only controls whether the LINK is shown, never access on its own.
    is_admin: bool = False

@router.get("/users/me/stats", response_model=UserStatsResponse)
def get_user_stats(user: User = Depends(get_current_user)):
    """Return aggregate stats for the current user: briefs delivered, articles scanned, time saved."""
    db = get_supabase()
    is_admin_user = _is_admin(user)

    subs = db.table("topic_subscriptions").select("topic_id").eq("user_id", user.id).execute()
    if not subs.data:
        return {"total_briefs": 0, "articles_scanned": 0, "time_saved_minutes": 0, "is_admin": is_admin_user}

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
        "is_admin": is_admin_user,
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
def get_topic_ayr(topic_id: str, days: int = 30, user: User = Depends(get_current_user)):
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
    db = get_supabase()
    _require_subscription(db, topic_id, user.id)
    res = db.table("topics").select("id, raw_query, poll_interval_seconds").eq("id", topic_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Topic not found")

    topic = res.data[0]

    try:
        from truebrief.ledger.ayr_engine import calculate_topic_ayr
        stats = calculate_topic_ayr(topic_id, days=days)
    except Exception as exc:
        logger.error(f"AYR calculation failed for topic {topic_id}: {exc}")
        raise HTTPException(status_code=500, detail="AYR calculation failed.")

    # Enrich with current topic info
    stats["raw_query"] = topic["raw_query"]
    stats["current_interval_s"] = topic["poll_interval_seconds"]

    return stats


@router.get("/topics/{topic_id}/query-variants")
def get_query_variants(topic_id: str, user: User = Depends(get_current_user)):
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
    _require_subscription(db, topic_id, user.id)
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
def get_topic_stories(topic_id: str, limit: int = 50, user: User = Depends(get_current_user)):
    """
    List all story nodes for a topic, newest-updated first.
    Each story includes summary, fact count, and last-update timestamp.
    """
    _require_uuid(topic_id, "topic_id")
    db = get_supabase()
    _require_subscription(db, topic_id, user.id)
    topic_res = db.table("topics").select("id").eq("id", topic_id).execute()
    if not topic_res.data:
        raise HTTPException(status_code=404, detail="Topic not found")

    res = (
        db.table("story_nodes")
        .select("id, topic_id, title, summary, status, fact_count, created_at, updated_at")
        .eq("topic_id", topic_id)
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


@router.get("/topics/{topic_id}/stories/{story_id}/facts")
def get_story_facts(topic_id: str, story_id: str, user: User = Depends(get_current_user)):
    """
    List all facts (alphas) attached to a specific story node, newest first.
    """
    db = get_supabase()
    _require_subscription(db, topic_id, user.id)
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
    user: User = Depends(get_current_user),
):
    """
    Admin endpoint: aggregated LLM cost & latency for the last N days.
    Restricted to the founder email configured via FOUNDER_EMAIL env var.
    """
    _require_founder(user)
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


def _with_subscriber_counts(db, topics: list[dict]) -> List[dict]:
    """Attach a real subscriber_count (topic_subscriptions rows) to each topic dict."""
    out = []
    for t in topics:
        count_res = (
            db.table("topic_subscriptions")
            .select("user_id", count="exact")
            .eq("topic_id", t["id"])
            .execute()
        )
        out.append({
            "id": t["id"],
            "name": t.get("name") or t["raw_query"],
            "subscriber_count": count_res.count or 0,
        })
    return out


@router.get("/shared-topics", response_model=List[SharedTopicResult])
def search_shared_topics(q: str = "", user: Optional[User] = Depends(get_optional_user)):
    """Search PUBLIC topics — suggestion pills on the New Topic page.

    Hybrid search: runs ilike (catches partial words while typing) AND semantic
    embedding (catches misspellings + intent) in parallel, then merges — semantic
    results ranked first, ilike-only additions appended. Either layer enriches the
    other so both partial inputs and misspelled-but-complete words surface correctly.
    """
    db = get_supabase()
    q = (q or "").strip()

    # Short / empty query — return most popular topics instead of searching.
    if len(q) < 2:
        res = db.table("topics").select("id, raw_query, name").eq("is_public", True).limit(10).execute()
        rows = _with_subscriber_counts(db, res.data or [])
        rows.sort(key=lambda r: r["subscriber_count"], reverse=True)
        return rows[:5]

    # --- ilike layer (always runs — fast, catches partial words) ---
    ilike_res = db.table("topics").select("id, raw_query, name").eq("is_public", True) \
        .or_(f"raw_query.ilike.%{q}%,name.ilike.%{q}%").limit(8).execute()
    ilike_rows = {r["id"]: r for r in (ilike_res.data or [])}

    # --- Semantic layer (embedding cosine similarity — catches misspellings + intent) ---
    sem_ordered_ids: list[str] = []
    if len(q) >= 3:
        try:
            _llm = LLMClient()
            q_embedding = _llm.embed(q)
            sem_res = db.rpc(
                "match_public_topics",
                {"query_embedding": q_embedding, "match_count": 5},
            ).execute()
            sem_ordered_ids = [r["id"] for r in (sem_res.data or [])]
        except Exception as _sem_err:
            logger.debug("Semantic topic search failed: %s", _sem_err)

    # --- Merge: semantic order first, then ilike-only extras ---
    seen: set[str] = set()
    merged_ids: list[str] = []
    for _id in sem_ordered_ids:
        if _id not in seen:
            seen.add(_id)
            merged_ids.append(_id)
    for _id in ilike_rows:
        if _id not in seen:
            seen.add(_id)
            merged_ids.append(_id)
    merged_ids = merged_ids[:5]

    if not merged_ids:
        return []

    full = db.table("topics").select("id, raw_query, name").in_("id", merged_ids).execute()
    ordered = sorted(full.data or [], key=lambda t: merged_ids.index(t["id"]))
    return _with_subscriber_counts(db, ordered)


@router.post("/admin/backfill-topic-embeddings")
def backfill_topic_embeddings(user: User = Depends(get_current_user)):
    """Admin-only: embed any public topics that are missing topic_embedding."""
    _require_admin(user)
    db = get_supabase()
    res = db.table("topics").select("id, raw_query, name").eq("is_public", True).execute()
    topics_to_embed = [t for t in (res.data or []) if t.get("raw_query")]
    # Fetch which ones already have embeddings
    ids = [t["id"] for t in topics_to_embed]
    if not ids:
        return {"backfilled": 0, "skipped": 0, "errors": []}
    emb_res = db.table("topics").select("id, topic_embedding").in_("id", ids).execute()
    has_embedding = {r["id"] for r in (emb_res.data or []) if r.get("topic_embedding") is not None}
    llm = LLMClient()
    backfilled, errors = 0, []
    for t in topics_to_embed:
        if t["id"] in has_embedding:
            continue
        try:
            embedding = llm.embed(t["raw_query"])
            db.table("topics").update({"topic_embedding": embedding}).eq("id", t["id"]).execute()
            backfilled += 1
            logger.info("Backfilled embedding for topic %s (%s)", t["id"], t["raw_query"])
        except Exception as e:
            errors.append({"id": t["id"], "name": t.get("name"), "error": str(e)})
            logger.warning("Backfill embedding failed for %s: %s", t["id"], e)
    return {"backfilled": backfilled, "skipped": len(has_embedding), "errors": errors}


@router.get("/public-topics", response_model=List[SharedTopicResult])
def list_public_topics():
    """List all PUBLIC topics — no auth required. Lets a signed-out visitor browse
    admin-curated public topics before signing in. Nothing is persisted for the caller;
    "adding" one is a client-side/ephemeral action until they sign in (see report)."""
    db = get_supabase()
    res = db.table("topics").select("id, raw_query, name").eq("is_public", True).order("raw_query").execute()
    return _with_subscriber_counts(db, res.data or [])


@router.get("/public-topics/{topic_id}/briefs")
def list_public_topic_briefs(topic_id: str):
    """Return recent briefs for a public topic — no auth required.

    Only topics with ``is_public=True`` are accessible. Briefs are filtered to
    the last 24 hours and after V5_CUTOVER_DATE, ordered newest-first.
    """
    _require_uuid(topic_id, "topic_id")
    db = get_supabase()

    topic_res = db.table("topics").select("id, name, raw_query, is_public").eq("id", topic_id).execute()
    topic_rows = topic_res.data or []
    if not topic_rows or not topic_rows[0].get("is_public"):
        raise HTTPException(status_code=404, detail="Topic not found")
    topic = topic_rows[0]

    from config.settings import V5_CUTOVER_DATE
    from datetime import timezone, timedelta
    cutoff_24h = (datetime.now(tz=timezone.utc) - timedelta(hours=24)).isoformat()
    cutoff = max(V5_CUTOVER_DATE, cutoff_24h)

    briefs_res = (
        db.table("briefs")
        .select("id, content, delivered_at")
        .eq("topic_id", topic_id)
        .gte("delivered_at", cutoff)
        .order("delivered_at", desc=True)
        .execute()
    )

    return {
        "topic": {"id": topic["id"], "name": topic["name"], "raw_query": topic["raw_query"]},
        "briefs": briefs_res.data or [],
    }


# ---------------------------------------------------------------------------
# Dashboard endpoint
# ---------------------------------------------------------------------------

# A brief line is "structural" (header/badge/divider/section title) — not prose —
# if it matches any of these. We skip them when building the dashboard preview so
# the card shows a real sentence, not "━━━ NEW STORIES (3)".
_DIVIDER_CHARS = set("━—–-=_")


def _clean_brief_line(line: str, max_len: int) -> str:
    """Strip attribution + markdown from one brief line and cap its length."""
    # Strip the trailing "→ Sources: [name](url), ..." attribution
    line = re.split(r'\s*→\s*Sources?\s*:', line)[0].strip()
    # Strip leading bullet markers / list numbering, then markdown emphasis
    line = re.sub(r'^[•\-\*\d\.\)\s]+', '', line)
    line = line.replace('*', '').replace('#', '').replace('`', '').replace('_', '').strip()
    if len(line) > max_len:
        return line[:max_len].rsplit(' ', 1)[0] + '…'
    return line


def _brief_preview(content: str, max_len: int = 200) -> str:
    """
    Extract a readable preview from a brief's markdown for the dashboard card.

    Prefers the first real bullet (the actual story line); falls back to the first
    non-structural line (e.g. a section title) if there are no bullets. Strips the
    📋 TrueBrief header, 🆕/📈 section badges, ━━━ dividers, leading bullet markers,
    markdown emphasis, and the trailing "→ Sources: [...]" attribution.
    """
    if not content:
        return ""

    # Lede-first: the "📌 Bottom line" sentence is the single best preview, so
    # prefer it over the first bullet when present.
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if "Bottom line" in line and ("📌" in line or line.lstrip("*").startswith("📌")):
            cleaned = _clean_brief_line(re.sub(r'^\**\s*📌?\s*Bottom line:?\**\s*', '', line), max_len)
            if cleaned:
                return cleaned

    fallback = ""
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # Header line: "📋 TrueBrief | Topic | Date"
        if "TrueBrief" in line or line.startswith("📋"):
            continue
        # Bottom-line lede is handled above; skip it in the bullet/fallback scan.
        if "Bottom line" in line and "📌" in line:
            continue
        # Divider line: only divider / box-drawing chars
        if all(ch in _DIVIDER_CHARS or ch.isspace() for ch in line):
            continue
        # Section badge: "🆕 NEW STORIES (3)", "📈 UPDATES (2)"
        if re.match(r'^[^\w\s]*\s*(NEW STORIES|UPDATES|NEW|UPDATE)\b.*\(\d+\)\s*$', line, re.IGNORECASE):
            continue

        # A real bullet starts with "• ", "- ", "* ", or "1. "/"1) " — but NOT
        # "**bold**" (markdown emphasis) or "--" (a divider), so require a space
        # after a dash/asterisk marker.
        is_bullet = (
            line[0] == '•'
            or re.match(r'^[-*]\s', line) is not None
            or re.match(r'^\d+[.)]\s', line) is not None
        )
        cleaned = _clean_brief_line(line, max_len)
        if not cleaned:
            continue
        if is_bullet:
            return cleaned           # the actual story line — best preview
        if not fallback:
            fallback = cleaned       # remember first prose/title line as a backstop

    return fallback


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

        # Find the most recent brief that isn't an error/empty
        usable = next(
            (b for b in briefs_res.data
             if b["content"] and not b["content"].strip().lower().startswith("error")),
            None,
        )
        if not usable:
            continue

        preview = _brief_preview(usable["content"])

        result.append({
            "topic_id": topic["id"],
            "topic_name": topic.get("name") or topic["raw_query"],
            "frequency": topic.get("frequency", "Auto"),
            "last_scanned_at": topic.get("last_run_at"),
            "new_count": new_count,
            "update_count": 0,
            "preview_text": preview,
        })

    result.sort(key=lambda x: x["last_scanned_at"] or "", reverse=True)
    return result


# ---------------------------------------------------------------------------
# Per-user delta feed (architecture §8 — the V3 home & daily summary engine)
# ---------------------------------------------------------------------------

class SeenRequest(BaseModel):
    topic_ids: Optional[List[str]] = None   # None = mark all subscribed topics seen


@router.get("/feed")
def get_feed(user: User = Depends(get_current_user)):
    """The cross-topic 'what's new since you looked' feed (live window, §8).

    $0 LLM — pure delta over known_facts vs each topic's last_seen_at. Returns
    `all_quiet: true` when there's nothing new (the 'all caught up' hero state)."""
    from truebrief.ledger.delta_engine import get_delta_feed
    return get_delta_feed(user.id, anchor="seen")


@router.post("/feed/seen")
def mark_feed_seen(body: SeenRequest = SeenRequest(), user: User = Depends(get_current_user)):
    """Advance last_seen_at (default: all subscribed topics) so the next look shows
    'all caught up'. Called on view / 'mark all caught up'."""
    from truebrief.ledger.delta_engine import advance_seen
    advance_seen(user.id, body.topic_ids)
    return {"ok": True}


@router.get("/feed/digest")
def get_feed_digest(user: User = Depends(get_current_user)):
    """The same delta feed in the DIGEST envelope (§13) — everything new since the
    user's last digest (last_digest_at), for the in-app dated digest card. Read-only:
    viewing the mirror does not advance the anchor (the email send does)."""
    from datetime import datetime as _dt, timezone as _tz
    from truebrief.ledger.delta_engine import get_delta_feed
    feed = get_delta_feed(user.id, anchor="digest")
    feed["date_label"] = _dt.now(_tz.utc).strftime("%a %b %d")
    return feed


# ---------------------------------------------------------------------------
# Dashboard summary (V4-5)
# ---------------------------------------------------------------------------

def _select_m_facts(facts: list[str]) -> list[str]:
    """Return the top M(N) facts for the summary.

    Facts arrive already ranked by salience from the delta engine (significance ×
    recency × relevance), so truncation is the pre-filter — the most important
    ones lead. The curve is logarithmic so a short daily visit gets all facts and
    a month-long absence caps at ~50 instead of dumping the entire backlog.
    Constants are a starting point — calibrate against real summaries post-launch.
    """
    n = len(facts)
    if n <= 10:
        return facts
    m = round(8 + 6 * math.log2(1 + n / 8))
    return facts[:m]


def _adaptive_window(m: int) -> tuple[int, int]:
    """Logarithmically-scaled sentence budget for M selected facts.

    Grows from ~2-4 sentences for a handful of facts to ~8-12 for a busy week,
    plateauing so a very long absence still produces a readable digest, not an essay.
    Constants to be calibrated after user testing.
    """
    log_val = math.log2(max(m, 1) + 2)
    s_min = max(2, round(log_val + 0.5))
    s_max = min(20, max(s_min + 2, round(2.2 * log_val + 1)))
    return s_min, s_max


@router.post("/topics/{topic_id}/summary")
@limiter.limit("60/hour")
def get_topic_summary(
    request: Request,
    topic_id: str,
    body: SummaryRequest,
    user: User = Depends(get_current_user),
):
    """Generate an adaptive editorial summary of the supplied facts.

    Three-layer pipeline (see docs/roadmap.md §V4-5):
    1. Pre-filter  — _select_m_facts() takes top M(N) from the salience-ordered list.
    2. Budget      — _adaptive_window() injects a logarithmically-scaled sentence
                     target: 2-4 for a quiet day, 8-12 for a busy week, plateauing
                     so a month-long absence still produces a readable digest.
    3. Editorial   — lede-first, directional language, facts merged by theme,
                     ruthless omission of minor/routine/repetitive items.
    Returns {"summary": null} on empty input or LLM failure — non-fatal by design.
    """
    _require_uuid(topic_id, "topic_id")

    if not body.facts:
        return {"summary": None}

    db = get_supabase()
    _require_subscription(db, topic_id, user.id)

    topic_res = db.table("topics").select("raw_query").eq("id", topic_id).execute()
    if not topic_res.data:
        raise HTTPException(status_code=404, detail="Topic not found")
    raw_query = topic_res.data[0]["raw_query"]

    # Layer 1: select top M facts (already salience-ordered from delta engine)
    selected = _select_m_facts(body.facts[:40])
    m = len(selected)
    bullet_list = "\n".join(f"- {f}" for f in selected)

    # Layer 2: sentence budget scales with information volume
    s_min, s_max = _adaptive_window(m)

    # Layer 3: editorial presentation — lede-first, directional, merges related facts
    prompt = build_dashboard_summary_prompt(raw_query, bullet_list, s_min, s_max)

    try:
        llm = LLMClient()
        summary = llm.call(
            step_name="dashboard_summary",
            prompt=prompt,
            system_prompt=DASHBOARD_SUMMARY_SYSTEM,
        )
        return {"summary": summary.strip()}
    except Exception as exc:
        logger.warning("dashboard_summary LLM call failed (non-fatal): %s", exc)
        return {"summary": None}


@router.post("/topics/{topic_id}/story")
@limiter.limit("60/hour")
def get_topic_story(
    request: Request,
    topic_id: str,
    body: StoryRequest,
    user: User = Depends(get_current_user),
):
    """Story view (V4): connective tissue between adjacent alphas.

    Given N facts in chronological order, returns N-1 short bridge sentences —
    connectors[i] links facts[i] → facts[i+1]. The alphas stay the skeleton; the
    story is what these bridges build on top. Returns {"connectors": []} on empty
    input, a single fact, or LLM failure — non-fatal by design (UI shows raw alphas).
    """
    _require_uuid(topic_id, "topic_id")

    facts = [f for f in (body.facts or []) if f and f.strip()]
    if len(facts) < 2:
        return {"connectors": []}

    db = get_supabase()
    _require_subscription(db, topic_id, user.id)

    topic_res = db.table("topics").select("raw_query").eq("id", topic_id).execute()
    if not topic_res.data:
        raise HTTPException(status_code=404, detail="Topic not found")
    raw_query = topic_res.data[0]["raw_query"]

    facts = facts[:25]  # cap for cost/latency
    fact_ids = (body.fact_ids or [])[:25] if body.fact_ids else []
    n_pairs = len(facts) - 1

    # V4-4: cache-first path — only active when the flag is on AND the caller provided IDs.
    if settings.V4_STORY_STITCHING and len(fact_ids) == len(facts):
        try:
            stitch_rows = (
                db.table("fact_stitches")
                .select("before_fact_id, after_fact_id, passage")
                .eq("topic_id", topic_id)
                .execute()
            )
            stitch_cache: dict[tuple[str, str], str] = {
                (r["before_fact_id"], r["after_fact_id"]): r["passage"]
                for r in (stitch_rows.data or [])
            }
        except Exception as cache_err:
            logger.warning("fact_stitches lookup failed (non-fatal): %s", cache_err)
            stitch_cache = {}

        connectors: list[str] = []
        pairs_needing_llm: list[tuple[int, str, str]] = []  # (index, before_text, after_text)

        for i in range(n_pairs):
            key = (fact_ids[i], fact_ids[i + 1])
            if key in stitch_cache:
                connectors.append(stitch_cache[key])
            else:
                connectors.append("")  # placeholder; filled by LLM below
                pairs_needing_llm.append((i, facts[i], facts[i + 1]))

        # Fall back to individual LLM calls only for the cache-miss pairs.
        if pairs_needing_llm:
            llm = LLMClient()
            for idx, before_text, after_text in pairs_needing_llm:
                try:
                    pair_prompt = build_story_stitch_pair_prompt(
                        topic_name=raw_query,
                        fact_a=before_text,
                        fact_b=after_text,
                    )
                    raw = llm.call(
                        step_name="story_stitch",
                        prompt=pair_prompt,
                        json_mode=True,
                        system_prompt=STORY_STITCH_SYSTEM,
                    )
                    parsed = json.loads(raw)
                    connectors[idx] = str(parsed.get("passage", "")).strip()
                except Exception as pair_exc:
                    logger.warning("story_stitch fallback LLM call failed (non-fatal): %s", pair_exc)

        return {"connectors": connectors}

    # Legacy path: one LLM call for all N-1 pairs (used when flag is off or no IDs provided).
    numbered = "\n".join(f"{i + 1}. {f}" for i, f in enumerate(facts))
    prompt = build_story_stitch_batch_prompt(raw_query, numbered, n_pairs)

    try:
        llm = LLMClient()
        raw = llm.call(
            step_name="story_stitch",
            prompt=prompt,
            json_mode=True,
            system_prompt=STORY_STITCH_SYSTEM,
        )
        return {"connectors": _parse_story_connectors(raw, n_pairs)}
    except Exception as exc:
        logger.warning("story_stitch LLM call failed (non-fatal): %s", exc)
        return {"connectors": []}


def _parse_story_connectors(raw: str, n_pairs: int) -> list[str]:
    """Parse the story_stitch LLM response into exactly n_pairs bridge strings.

    Groq's json_object mode forces a top-level object, so the model returns
    {"connectors": [...]} — but accept a bare array and common alt keys too.
    Always returns a list of length n_pairs (padded with "") so the client
    can index safely; returns all-empty on unparseable shapes.
    """
    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        connectors = parsed.get("connectors") or parsed.get("bridges") or parsed.get("passages") or []
    elif isinstance(parsed, list):
        connectors = parsed
    else:
        connectors = []
    if not isinstance(connectors, list):
        connectors = []
    out = [str(c).strip() for c in connectors if c][:n_pairs]
    return out + [""] * (n_pairs - len(out))


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
    _require_subscription(db, topic_id, user.id)

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
    """Remove a fact from the user's view (hard delete — dedup uses embeddings).

    Access control: the caller must be subscribed to the fact's topic. Without
    this check any authenticated user could delete ANY fact in the shared
    known_facts table by enumerating UUIDs (cross-tenant destruction).
    """
    _require_uuid(fact_id, "fact_id")
    db = get_supabase()
    fact = (
        db.table("known_facts")
        .select("topic_id")
        .eq("id", fact_id)
        .execute()
    )
    if not fact.data:
        raise HTTPException(status_code=404, detail="Fact not found")
    _require_subscription(db, fact.data[0]["topic_id"], user.id)
    db.table("known_facts").delete().eq("id", fact_id).execute()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Admin Metrics (A.6)
# ---------------------------------------------------------------------------

def _is_admin(user: User) -> bool:
    """True only if the user is in ADMIN_USER_IDS. Fails CLOSED.

    Also honors ADMIN_EMAILS (the founder allowlist already used elsewhere) so a
    single source of truth works. An unset allowlist grants NOBODY admin — an
    empty gate must never expose every user's scraped content + LLM logs.
    """
    import os
    ids = {x.strip() for x in os.getenv("ADMIN_USER_IDS", "").split(",") if x.strip()}
    if user.id in ids:
        return True
    admin_emails = {
        e.strip().lower()
        for e in getattr(settings, "ADMIN_EMAILS", "").split(",")
        if e.strip()
    }
    if settings.FOUNDER_EMAIL:
        admin_emails.add(settings.FOUNDER_EMAIL.strip().lower())
    if user.email and user.email.strip().lower() in admin_emails:
        return True
    if not ids and not admin_emails:
        logger.error("No ADMIN_USER_IDS/ADMIN_EMAILS/FOUNDER_EMAIL set — denying admin (fail-closed).")
    return False


@router.get("/admin/metrics")
def get_admin_metrics(user: User = Depends(get_current_user)):
    """
    Pipeline health dashboard for admins.
    Protected by ADMIN_USER_IDS env var (comma-separated Supabase auth user IDs).
    If the env var is not set, any authenticated user can access (dev mode).
    """
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required.")

    db = get_supabase()

    # ── Pipeline runs ────────────────────────────────────────────────────────
    runs: list = []
    try:
        runs_res = (
            db.table("pipeline_run")
            .select("id, topic_id, started_at, duration_ms, exit_status, brief_length, "
                    "decisions_new, decisions_update, decisions_duplicate, error_message")
            .order("started_at", desc=True)
            .limit(200)
            .execute()
        )
        runs = runs_res.data or []
    except Exception:
        pass  # table may not exist yet

    by_status: dict = {}
    total_dur = 0
    dur_count = 0
    for r in runs:
        s = r.get("exit_status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
        d = r.get("duration_ms")
        if d:
            total_dur += d
            dur_count += 1

    avg_duration_ms = int(total_dur / dur_count) if dur_count else 0

    recent_runs = [
        {
            "id": r["id"],
            "topic_id": r.get("topic_id"),
            "started_at": r.get("started_at"),
            "duration_s": round(r["duration_ms"] / 1000, 1) if r.get("duration_ms") else None,
            "exit_status": r.get("exit_status"),
            "brief_length": r.get("brief_length", 0),
            "new": r.get("decisions_new", 0),
            "update": r.get("decisions_update", 0),
            "dupe": r.get("decisions_duplicate", 0),
            "error": r.get("error_message"),
        }
        for r in runs[:25]
    ]

    # ── LLM costs ────────────────────────────────────────────────────────────
    # V5 production (GeminiSearchRunner, pipeline/v5_runner.py) only ever calls these
    # stages. Anything else (harvester, query_builder, signal_scorer, story_stitch, ...)
    # is V4's PipelineRunner, which production never runs — it only fires from
    # scripts/quality_benchmark.py's A/B comparison arm, on throwaway topics. Both write
    # to the same llm_call_log table, so without this split the benchmark's cost silently
    # dominates the "production spend" total and misreads as live cost.
    V5_STAGES = {
        "gemini_search", "gemini_extract", "arbiter", "briefer", "embedding",
    }
    total_cost_usd = 0.0
    cost_by_stage: dict = {}
    benchmark_cost_usd = 0.0
    benchmark_cost_by_stage: dict = {}
    total_tokens = 0

    # Uses the llm_cost_by_stage RPC (migration 027) rather than a raw unbounded select
    # on llm_call_log. That table has 11,000+ rows; PostgREST silently caps an unordered,
    # unlimited select at 1000, so a hand-summed total here was reading only an arbitrary
    # slice of the table (verified live 2026-07-29: it landed on rows from before the
    # 2026-07-22 pricing fix, so the dashboard read exactly $0.0000 despite real spend
    # existing). days_back=3650 (~10y) so this stays a true cumulative total, not a
    # rolling window — this dashboard has always shown all-time spend.
    try:
        cost_res = db.rpc("llm_cost_by_stage", {"days_back": 3650}).execute()
        for row in (cost_res.data or []):
            c = float(row.get("total_cost_usd") or 0.0)
            stage = row.get("stage", "unknown")
            if stage in V5_STAGES:
                total_cost_usd += c
                cost_by_stage[stage] = c
                total_tokens += int(row.get("total_input_tokens") or 0) + int(row.get("total_output_tokens") or 0)
            else:
                benchmark_cost_usd += c
                benchmark_cost_by_stage[stage] = c
    except Exception:
        pass  # RPC may not exist yet (pre-migration-027 environments)

    # ── Global counts ─────────────────────────────────────────────────────────
    total_topics = 0
    total_briefs = 0
    total_facts = 0
    try:
        total_topics = (db.table("topics").select("id", count="exact").execute().count or 0)
        total_briefs = (db.table("briefs").select("id", count="exact").execute().count or 0)
        total_facts  = (db.table("known_facts").select("id", count="exact").execute().count or 0)
    except Exception:
        pass

    return {
        "totals": {
            "topics": total_topics,
            "briefs": total_briefs,
            "facts": total_facts,
            "pipeline_runs": len(runs),
            "total_cost_usd": round(total_cost_usd, 4),
            "total_tokens": total_tokens,
            "avg_duration_s": round(avg_duration_ms / 1000, 1),
        },
        "runs_by_status": by_status,
        "cost_by_stage": {
            k: round(v, 6)
            for k, v in sorted(cost_by_stage.items(), key=lambda x: -x[1])
        },
        "benchmark_cost_usd": round(benchmark_cost_usd, 4),
        "benchmark_cost_by_stage": {
            k: round(v, 6)
            for k, v in sorted(benchmark_cost_by_stage.items(), key=lambda x: -x[1])
        },
        "recent_runs": recent_runs,
    }


@router.get("/admin/quota-alerts")
def get_admin_quota_alerts(hours: int = 48, user: User = Depends(get_current_user)):
    """
    Recent Gemini quota-exhaustion flag events (yellow = primary exhausted, on backup;
    red = backup also failed / no backup / fell through to Groq — call is degraded or
    failing). Persisted by truebrief.ledger.quota_alerts.flag_quota_event() at the exact
    point llm/client.py catches a 429/RESOURCE_EXHAUSTED error. Push notifications to the
    founder are best-effort (see `notified` per row); this endpoint is the durable record.
    """
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required.")

    from truebrief.ledger.quota_alerts import recent_alerts

    hours = min(max(hours, 1), 24 * 30)  # cap at 30 days
    alerts = recent_alerts(hours=hours, limit=200)
    return {
        "alerts": alerts,
        "red_count": sum(1 for a in alerts if a.get("severity") == "red"),
        "yellow_count": sum(1 for a in alerts if a.get("severity") == "yellow"),
    }


# ---------------------------------------------------------------------------
# Admin Pipeline Trace / Observability (A.7)
# ---------------------------------------------------------------------------

def _topic_names(db, topic_ids: list) -> dict:
    """Map topic_id → raw_query for a set of ids (best-effort)."""
    ids = [t for t in {x for x in topic_ids if x}]
    if not ids:
        return {}
    try:
        res = db.table("topics").select("id, raw_query").in_("id", ids).execute()
        return {r["id"]: r.get("raw_query") for r in (res.data or [])}
    except Exception:
        return {}


@router.get("/admin/runs")
def list_pipeline_runs(
    limit: int = 50,
    topic_id: Optional[str] = None,
    status: Optional[str] = None,
    user: User = Depends(get_current_user),
):
    """
    Admin: list recent pipeline runs (newest first) for the trace panel.
    Optional filters: topic_id, status (success|no_update|rejected|error|running).
    """
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required.")

    db = get_supabase()
    try:
        q = (
            db.table("pipeline_run")
            .select("id, topic_id, started_at, duration_ms, exit_status, brief_length, "
                    "articles_collected, articles_selected, alphas_extracted, "
                    "decisions_new, decisions_update, decisions_duplicate, error_message")
            .order("started_at", desc=True)
            .limit(min(max(limit, 1), 200))
        )
        if topic_id:
            q = q.eq("topic_id", topic_id)
        if status:
            q = q.eq("exit_status", status)
        runs = (q.execute().data) or []
    except Exception as exc:
        logger.warning("list_pipeline_runs failed: %s", exc)
        runs = []

    names = _topic_names(db, [r.get("topic_id") for r in runs])
    return {
        "runs": [
            {
                "id": r["id"],
                "topic_id": r.get("topic_id"),
                "topic_name": names.get(r.get("topic_id")) or "—",
                "started_at": r.get("started_at"),
                "duration_s": round(r["duration_ms"] / 1000, 1) if r.get("duration_ms") else None,
                "exit_status": r.get("exit_status"),
                "brief_length": r.get("brief_length", 0),
                "articles_collected": r.get("articles_collected", 0),
                "articles_selected": r.get("articles_selected", 0),
                "new": r.get("decisions_new", 0),
                "update": r.get("decisions_update", 0),
                "dupe": r.get("decisions_duplicate", 0),
                "error": r.get("error_message"),
            }
            for r in runs
        ]
    }


@router.get("/admin/runs/{run_id}")
def get_pipeline_run_trace(run_id: str, user: User = Depends(get_current_user)):
    """
    Admin: full trace of a single pipeline run — the whole story of the scan.

    Merges the structured stage trace (pipeline_trace) with every LLM call's actual
    prompt/response (llm_call_log) into one time-ordered timeline so a bad/odd update
    can be pinpointed to the exact stage it came from.
    """
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required.")
    _require_uuid(run_id, "run_id")

    db = get_supabase()

    # ── The run row itself ────────────────────────────────────────────────────
    run = None
    try:
        rr = db.table("pipeline_run").select("*").eq("id", run_id).single().execute()
        run = rr.data
    except Exception:
        run = None
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")

    topic_name = _topic_names(db, [run.get("topic_id")]).get(run.get("topic_id"))

    # ── Structured stage trace ────────────────────────────────────────────────
    trace_events: list = []
    try:
        tr = (
            db.table("pipeline_trace")
            .select("seq, stage, label, data, created_at")
            .eq("pipeline_run_id", run_id)
            .order("seq", desc=False)
            .execute()
        )
        for e in (tr.data or []):
            trace_events.append({
                "kind": "stage",
                "seq": e.get("seq", 0),
                "stage": e.get("stage"),
                "label": e.get("label"),
                "data": e.get("data") or {},
                "created_at": e.get("created_at"),
            })
    except Exception as exc:
        logger.debug("pipeline_trace fetch failed (table may be pre-012): %s", exc)

    # ── Every LLM call with prompt/response ───────────────────────────────────
    llm_events: list = []
    try:
        lr = (
            db.table("llm_call_log")
            .select("*")
            .eq("pipeline_run_id", run_id)
            .order("created_at", desc=False)
            .execute()
        )
        for c in (lr.data or []):
            llm_events.append({
                "kind": "llm",
                "seq": 0,
                "stage": c.get("stage"),
                "model": c.get("model"),
                "input_tokens": c.get("input_tokens"),
                "output_tokens": c.get("output_tokens"),
                "cost_usd": c.get("cost_usd"),
                "duration_ms": c.get("duration_ms"),
                "system_prompt": c.get("system_prompt"),
                "prompt": c.get("prompt"),
                "response": c.get("response"),
                "created_at": c.get("created_at"),
            })
    except Exception as exc:
        logger.debug("llm_call_log fetch failed: %s", exc)

    # ── Merge into one timeline (by created_at, then seq) ─────────────────────
    timeline = trace_events + llm_events
    timeline.sort(key=lambda x: (x.get("created_at") or "", x.get("seq") or 0))

    llm_cost = sum(float(e.get("cost_usd") or 0) for e in llm_events)

    return {
        "run": {
            "id": run["id"],
            "topic_id": run.get("topic_id"),
            "topic_name": topic_name or "—",
            "started_at": run.get("started_at"),
            "duration_s": round(run["duration_ms"] / 1000, 1) if run.get("duration_ms") else None,
            "exit_status": run.get("exit_status"),
            "brief_length": run.get("brief_length", 0),
            "articles_collected": run.get("articles_collected", 0),
            "articles_selected": run.get("articles_selected", 0),
            "alphas_extracted": run.get("alphas_extracted", 0),
            "new": run.get("decisions_new", 0),
            "update": run.get("decisions_update", 0),
            "dupe": run.get("decisions_duplicate", 0),
            "error": run.get("error_message"),
            "llm_calls": len(llm_events),
            "llm_cost_usd": round(llm_cost, 6),
        },
        "timeline": timeline,
    }


# ---------------------------------------------------------------------------
# Admin: per-topic / per-user drill-down (public/private topics list screen +
# a dedicated per-user usage screen, splitting these out of the single /admin
# screen). Gated with _is_admin (not _require_admin/tiers.is_admin, which the
# /admin/public-topics + PATCH .../public endpoints use) — these three expose
# every user's data, so they sit on the same stricter gate as /admin/metrics
# and /admin/runs above rather than a separate allowlist.
# ---------------------------------------------------------------------------

class AdminTopicListItem(BaseModel):
    id: str
    raw_query: str
    is_public: bool = False
    owner_id: Optional[str] = None
    owner_email: Optional[str] = None
    subscriber_count: int = 0
    is_active: bool = True
    last_run_at: Optional[str] = None
    created_at: Optional[str] = None


@router.get("/admin/topics", response_model=List[AdminTopicListItem])
def list_admin_topics(user: User = Depends(get_current_user)):
    """Admin: every topic with its owner + subscriber count, for the topics admin screen."""
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required.")
    db = get_supabase()

    topics = (
        db.table("topics")
        .select("id, raw_query, is_public, user_id, is_active, last_run_at, created_at")
        .order("created_at", desc=True)
        .execute()
    ).data or []

    owner_ids = list({t["user_id"] for t in topics if t.get("user_id")})
    owner_emails: dict = {}
    if owner_ids:
        owner_res = db.table("users").select("id, email").in_("id", owner_ids).execute()
        owner_emails = {o["id"]: o.get("email") for o in (owner_res.data or [])}

    # Batch subscriber counts in one query rather than one count() per topic. This app is
    # pre-launch scale, so a plain select well under PostgREST's ~1000-row default cap is
    # fine; if topic_subscriptions grows past that, switch to a dedicated group-by RPC (the
    # same fix already applied to LLM cost totals — see admin_stats.get_cost_for_topics).
    topic_ids = [t["id"] for t in topics]
    subscriber_counts: dict = {}
    if topic_ids:
        sub_res = (
            db.table("topic_subscriptions")
            .select("topic_id")
            .in_("topic_id", topic_ids)
            .limit(10000)
            .execute()
        )
        for row in (sub_res.data or []):
            tid = row.get("topic_id")
            if tid:
                subscriber_counts[tid] = subscriber_counts.get(tid, 0) + 1

    return [
        {
            "id": t["id"],
            "raw_query": t.get("raw_query"),
            "is_public": bool(t.get("is_public")),
            "owner_id": t.get("user_id"),
            "owner_email": owner_emails.get(t.get("user_id")),
            "subscriber_count": subscriber_counts.get(t["id"], 0),
            "is_active": t.get("is_active", True),
            "last_run_at": t.get("last_run_at"),
            "created_at": t.get("created_at"),
        }
        for t in topics
    ]


class AdminUserListItem(BaseModel):
    id: str
    email: str
    tier: str = "free"
    created_at: Optional[str] = None
    topics_created: int = 0
    subscriptions: int = 0


@router.get("/admin/users", response_model=List[AdminUserListItem])
def list_admin_users(user: User = Depends(get_current_user)):
    """Admin: every user with billing tier + topic/subscription counts.

    Deliberately cheap — no cost aggregation here, that belongs to the per-user
    drill-down (GET /admin/users/{user_id}). Tier is read from user_subscriptions.tier
    (the live table Paddle/Stripe billing writes to), not users.plan — that column exists
    in schema.sql but nothing in the codebase reads or writes it, so it would only ever
    show its default and silently misreport every paid user as free.
    """
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required.")
    db = get_supabase()

    users_rows = (
        db.table("users").select("id, email, created_at").order("created_at", desc=True).execute()
    ).data or []
    user_ids = [u["id"] for u in users_rows]

    tiers: dict = {}
    if user_ids:
        tier_res = db.table("user_subscriptions").select("user_id, tier").in_("user_id", user_ids).execute()
        tiers = {r["user_id"]: r.get("tier", "free") for r in (tier_res.data or [])}

    topics_created: dict = {}
    if user_ids:
        topics_res = db.table("topics").select("user_id").in_("user_id", user_ids).limit(10000).execute()
        for row in (topics_res.data or []):
            uid = row.get("user_id")
            if uid:
                topics_created[uid] = topics_created.get(uid, 0) + 1

    subscriptions: dict = {}
    if user_ids:
        subs_res = (
            db.table("topic_subscriptions").select("user_id").in_("user_id", user_ids).limit(10000).execute()
        )
        for row in (subs_res.data or []):
            uid = row.get("user_id")
            if uid:
                subscriptions[uid] = subscriptions.get(uid, 0) + 1

    return [
        {
            "id": u["id"],
            "email": u.get("email"),
            "tier": tiers.get(u["id"], "free"),
            "created_at": u.get("created_at"),
            "topics_created": topics_created.get(u["id"], 0),
            "subscriptions": subscriptions.get(u["id"], 0),
        }
        for u in users_rows
    ]


@router.get("/admin/users/{user_id}")
def get_admin_user_detail(user_id: str, user: User = Depends(get_current_user)):
    """Admin: full per-user drill-down — profile, created topics, subscribed (watch-list)
    topics, recent pipeline runs, and usage/cost.

    Cost and run attribution go through topics.user_id (creator) only, never subscribers.
    Topics can be shared/public, so attributing a run's cost to every subscriber would
    double- (or N-) count a single pipeline run across everyone watching that topic.
    """
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required.")
    _require_uuid(user_id, "user_id")
    db = get_supabase()

    profile_res = db.table("users").select("id, email, created_at").eq("id", user_id).execute()
    if not profile_res.data:
        raise HTTPException(status_code=404, detail="User not found")
    profile = profile_res.data[0]

    tier_res = db.table("user_subscriptions").select("tier").eq("user_id", user_id).execute()
    tier = tier_res.data[0]["tier"] if tier_res.data else "free"

    created_res = (
        db.table("topics")
        .select("id, raw_query, is_public, last_run_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    created_topics = created_res.data or []
    created_topic_ids = [t["id"] for t in created_topics]

    sub_res = db.table("topic_subscriptions").select("topic_id").eq("user_id", user_id).execute()
    subscribed_topic_ids = [r["topic_id"] for r in (sub_res.data or []) if r.get("topic_id")]
    watch_list = []
    if subscribed_topic_ids:
        wl_res = (
            db.table("topics")
            .select("id, raw_query, is_public, last_run_at")
            .in_("id", subscribed_topic_ids)
            .execute()
        )
        watch_list = wl_res.data or []

    recent_runs: list = []
    if created_topic_ids:
        try:
            runs_res = (
                db.table("pipeline_run")
                .select("id, topic_id, started_at, duration_ms, exit_status, brief_length, "
                        "articles_collected, articles_selected, alphas_extracted, "
                        "decisions_new, decisions_update, decisions_duplicate, error_message")
                .in_("topic_id", created_topic_ids)
                .order("started_at", desc=True)
                .limit(25)
                .execute()
            )
            runs = runs_res.data or []
        except Exception as exc:
            logger.warning("get_admin_user_detail: pipeline_run fetch failed: %s", exc)
            runs = []
        names = _topic_names(db, [r.get("topic_id") for r in runs])
        recent_runs = [
            {
                "id": r["id"],
                "topic_id": r.get("topic_id"),
                "topic_name": names.get(r.get("topic_id")) or "—",
                "started_at": r.get("started_at"),
                "duration_s": round(r["duration_ms"] / 1000, 1) if r.get("duration_ms") else None,
                "exit_status": r.get("exit_status"),
                "brief_length": r.get("brief_length", 0),
                "articles_collected": r.get("articles_collected", 0),
                "articles_selected": r.get("articles_selected", 0),
                "new": r.get("decisions_new", 0),
                "update": r.get("decisions_update", 0),
                "dupe": r.get("decisions_duplicate", 0),
                "error": r.get("error_message"),
            }
            for r in runs
        ]

    from truebrief.ledger.admin_stats import get_cost_for_topics
    usage = get_cost_for_topics(created_topic_ids)

    return {
        "user": {
            "id": profile["id"],
            "email": profile.get("email"),
            "tier": tier,
            "created_at": profile.get("created_at"),
        },
        "created_topics": created_topics,
        "watch_list": watch_list,
        "recent_runs": recent_runs,
        "usage": usage,
    }
