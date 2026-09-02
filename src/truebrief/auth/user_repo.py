from __future__ import annotations

import json
import logging
from uuid import uuid4

from truebrief.ledger.database import get_supabase
from truebrief.auth.models import User

logger = logging.getLogger(__name__)

# Every authenticated request resolves the caller through here. Un-cached, that was
# 1 SELECT + 1 UPDATE on `users` per request — and a dashboard load fires 6-8 API
# calls, so ~8 reads and ~8 writes for one page view (audit, Gate 3). Cache the
# resolved User briefly, and stamp last_seen_at at most once per window per user.
_USER_CACHE_TTL_SECONDS = 60
_LAST_SEEN_THROTTLE_SECONDS = 900  # 15 min


def _redis():
    try:
        from truebrief.api.cache import _get_redis
        return _get_redis()
    except Exception:
        return None


def _cache_get_user(auth_uid: str) -> User | None:
    r = _redis()
    if r is None:
        return None
    try:
        raw = r.get(f"user:{auth_uid}")
        return User(**json.loads(raw)) if raw else None
    except Exception:
        return None


def _cache_put_user(auth_uid: str, user: User) -> None:
    r = _redis()
    if r is None:
        return
    try:
        r.setex(f"user:{auth_uid}", _USER_CACHE_TTL_SECONDS, json.dumps(user.model_dump()))
    except Exception:
        pass


def invalidate_user_cache(auth_uid: str) -> None:
    """Drop the cached User for an auth identity (e.g. right after account deletion)."""
    r = _redis()
    if r is None:
        return
    try:
        r.delete(f"user:{auth_uid}")
    except Exception:
        pass


def _should_stamp_last_seen(user_id: str) -> bool:
    """True at most once per _LAST_SEEN_THROTTLE_SECONDS per user. Without Redis,
    always True (keeps the old every-request behaviour in dev)."""
    r = _redis()
    if r is None:
        return True
    try:
        # SET NX EX — returns True only for the first caller in the window.
        return bool(r.set(f"last_seen_stamped:{user_id}", "1", nx=True, ex=_LAST_SEEN_THROTTLE_SECONDS))
    except Exception:
        return True


def _stamp_last_seen(db, user_id: str) -> None:
    if not _should_stamp_last_seen(user_id):
        return
    try:
        db.table("users").update({"last_seen_at": "now()"}).eq("id", user_id).execute()
    except Exception as exc:
        logger.debug("last_seen_at stamp failed (non-fatal): %s", exc)


def get_or_create_user(auth_uid: str, email: str) -> User:
    cached = _cache_get_user(auth_uid)
    if cached is not None:
        _stamp_last_seen(get_supabase(), cached.id)
        return cached

    db = get_supabase()

    # (a) Normal path — user already linked to this Supabase auth identity.
    res = db.table("users").select("*").eq("auth_uid", auth_uid).execute()
    if res.data:
        row = res.data[0]
        user = User(**row)
        _cache_put_user(auth_uid, user)
        _stamp_last_seen(db, row["id"])
        return user

    # (b) Adoption path — ONE-TIME Clerk→Supabase migration affordance. The pre-existing
    # account (created under Clerk auth) has a NULL auth_uid; if a row with a matching
    # email exists, adopt it by stamping in the new Supabase auth_uid instead of creating
    # a duplicate account and orphaning that user's topics. Safe to remove once every row
    # in `users` has a non-null auth_uid.
    adopt_res = (
        db.table("users")
        .select("*")
        .eq("email", email)
        .is_("auth_uid", "null")
        .execute()
    )
    if adopt_res.data:
        row = adopt_res.data[0]
        db.table("users").update({
            "auth_uid": auth_uid,
            "last_seen_at": "now()",
        }).eq("id", row["id"]).execute()
        row["auth_uid"] = auth_uid
        user = User(**row)
        _cache_put_user(auth_uid, user)
        return user

    # (c) First login — create paired rows
    new_id = str(uuid4())
    db.table("users").insert({
        "id": new_id,
        "auth_uid": auth_uid,
        "email": email,
    }).execute()
    db.table("user_subscriptions").insert({
        "user_id": new_id,
        "tier": "free",
        "status": "active",
    }).execute()
    user = User(id=new_id, auth_uid=auth_uid, email=email)
    _cache_put_user(auth_uid, user)
    return user
