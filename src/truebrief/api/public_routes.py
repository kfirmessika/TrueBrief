"""
Public Developer API — api/public_routes.py

The API product: programmatic access to a user's monitored topics and their
verified fact stream. Authenticated by API key (NOT Supabase Auth) — pass the key as
`Authorization: Bearer tb_live_...` or `X-API-Key: tb_live_...`.

Mounted under /v1 (the Supabase-Auth-authed app API lives under /api/v1 — different
audience, different auth, deliberately separate prefix).

Every data endpoint meters usage and enforces the tier's daily quota.

Routes:
  GET /v1/topics                  → topics the key's owner is subscribed to
  GET /v1/topics/{id}/facts       → recent verified facts (the alpha stream)
  GET /v1/topics/{id}/history     → full date-grouped timeline
  GET /v1/usage                   → today's usage vs quota (not metered)
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from truebrief.apikeys.service import (
    ApiKeyIdentity,
    get_usage_today,
    meter_and_enforce,
    verify_api_key,
)
from truebrief.ledger.database import get_supabase

router = APIRouter(tags=["public-api"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

async def get_api_identity(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> ApiKeyIdentity:
    key = ""
    if authorization and authorization.startswith("Bearer "):
        key = authorization[7:].strip()
    elif x_api_key:
        key = x_api_key.strip()
    if not key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Pass 'Authorization: Bearer tb_live_...' or 'X-API-Key'.",
        )
    db = get_supabase()
    return verify_api_key(db, key)


def _require_uuid(value: str, field: str) -> None:
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail=f"{field} must be a valid UUID")


def _require_topic_access(db, topic_id: str, user_id: str) -> dict:
    """The key's owner must be subscribed to the topic. Returns the topic row."""
    sub = (
        db.table("topic_subscriptions")
        .select("topic_id")
        .eq("topic_id", topic_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not sub.data:
        raise HTTPException(status_code=404, detail="Topic not found.")
    topic = db.table("topics").select("id, raw_query, last_scan_at").eq("id", topic_id).execute()
    if not topic.data:
        raise HTTPException(status_code=404, detail="Topic not found.")
    return topic.data[0]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/topics")
def api_list_topics(identity: ApiKeyIdentity = Depends(get_api_identity)):
    db = get_supabase()
    meter_and_enforce(db, identity)

    subs = (
        db.table("topic_subscriptions")
        .select("topic_id")
        .eq("user_id", identity.user_id)
        .execute()
    )
    topic_ids = [s["topic_id"] for s in (subs.data or [])]
    if not topic_ids:
        return {"topics": []}

    topics = (
        db.table("topics")
        .select("id, raw_query, last_scan_at")
        .in_("id", topic_ids)
        .execute()
    )
    # fact_count lives on history_docs (one row per topic), not on topics.
    counts: dict[str, int] = {}
    try:
        hd = (
            db.table("history_docs")
            .select("topic_id, fact_count")
            .in_("topic_id", topic_ids)
            .execute()
        )
        counts = {r["topic_id"]: r.get("fact_count", 0) for r in (hd.data or [])}
    except Exception:
        pass
    return {
        "topics": [
            {
                "id": t["id"],
                "query": t["raw_query"],
                "last_scan_at": t.get("last_scan_at"),
                "fact_count": counts.get(t["id"], 0),
            }
            for t in (topics.data or [])
        ]
    }


@router.get("/topics/{topic_id}/facts")
def api_get_facts(
    topic_id: str,
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=50, ge=1, le=200),
    identity: ApiKeyIdentity = Depends(get_api_identity),
):
    """The core product: the verified, deduplicated, signal-scored fact stream."""
    _require_uuid(topic_id, "topic_id")
    db = get_supabase()
    meter_and_enforce(db, identity)
    _require_topic_access(db, topic_id, identity.user_id)

    import datetime as _dt
    cutoff = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=days)).isoformat()

    res = (
        db.table("known_facts")
        .select("id, alpha_text, source_url, source_domain, first_seen_at, event_class, signal_score, signal_class")
        .eq("topic_id", topic_id)
        .gte("first_seen_at", cutoff)
        .order("first_seen_at", desc=True)
        .limit(limit)
        .execute()
    )
    return {
        "topic_id": topic_id,
        "days": days,
        "facts": [
            {
                "id": f["id"],
                "text": f["alpha_text"],
                "source_url": f.get("source_url"),
                "source_domain": f.get("source_domain"),
                "first_seen_at": f.get("first_seen_at"),
                "event_class": f.get("event_class"),
                "signal_score": f.get("signal_score"),
                "signal_class": f.get("signal_class"),
            }
            for f in (res.data or [])
        ],
    }


@router.get("/topics/{topic_id}/history")
def api_get_history(
    topic_id: str,
    identity: ApiKeyIdentity = Depends(get_api_identity),
):
    """Full date-grouped timeline — same doc the app's topic page renders."""
    _require_uuid(topic_id, "topic_id")
    db = get_supabase()
    meter_and_enforce(db, identity)
    _require_topic_access(db, topic_id, identity.user_id)

    from truebrief.ledger.history_doc import get_history_doc
    return get_history_doc(topic_id, db=db)


@router.get("/usage")
def api_get_usage(identity: ApiKeyIdentity = Depends(get_api_identity)):
    """Today's usage vs the tier quota. Free to call (not metered)."""
    db = get_supabase()
    return get_usage_today(db, identity)
