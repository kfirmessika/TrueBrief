"""
Quota Alert System — ledger/quota_alerts.py

Real-time detection of a pipeline provider failing, hooked directly into every
multi-provider dispatch/fallback point in llm/client.py: the Gemini primary/backup/Groq
chain in call() and call_gemini_with_grounding(), the Linkup/Brave/Gemini grounding
fallback loop in collector_search(), and the OpenAI embedding path. Built 2026-08-12
after a live incident where the Gemini primary key silently hit its daily grounding cap
and the backup key permanently 404'd ("model no longer available") for the same model —
nobody found out until a downstream symptom (empty briefs) was noticed by chance.
Generalized 2026-09-05 beyond Gemini: once SEARCH_PROVIDER moved off "gemini", every
other provider's failure in these same fallback chains was silently absorbed with only a
logger.warning — a break in the actually-configured provider was invisible until every
fallback also failed. `provider` (migration 038) says which provider the event is about;
Gemini's own primary/backup key rotation keeps its existing, more specific key_type.

Severity:
    yellow — a provider failed on this call and the code is about to try a fallback
             (Gemini's own backup key, or a different provider entirely). Informational:
             the pipeline should still work, but worth knowing what just broke.
    red    — nothing was left to fall back to and this call failed outright (both Gemini
             keys quota-exhausted, a fallback provider also errored, or there's no backup
             configured at all). Actionable: something needs the founder's attention.

Two responsibilities per flag event, both fire-and-forget (never raise, never block the
LLM call whose failure they're reporting on):
  1. Persist to `quota_alerts` (migration 030) — the audit trail, survives even if the
     push notification below fails to deliver.
  2. Push a real-time notification to the founder's own subscribed device(s), reusing the
     existing web-push infrastructure (truebrief.push.client.send_push) rather than
     building anything new. Founder identity is resolved from settings.FOUNDER_EMAIL /
     settings.ADMIN_EMAILS (same allowlist api/routes.py's _is_admin() already trusts),
     looked up against the `users` table to get a user_id, then against
     `push_subscriptions` (enabled=true) for that user_id. If the founder has no active
     push subscription, the event is still persisted — just not pushed.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_YELLOW_TITLE = "⚠️ Provider warning"
_RED_TITLE = "\U0001f534 Provider critical"


def flag_quota_event(
    severity: str,
    step_name: str,
    model: str,
    key_type: str,
    error: Exception,
    provider: str = "gemini",
) -> None:
    """Persist + push-notify a provider flag event. Never raises.

    Called synchronously at the exact point of detection in llm/client.py so the flag
    fires immediately (no batching, no delay) — but every step inside here is wrapped so
    a DB outage or a broken push subscription can never propagate back into the LLM call
    path this is reporting on.

    provider defaults to "gemini" for backward compatibility with the original call sites
    (Gemini's own primary/backup key rotation); pass the real provider name ("linkup",
    "brave", "groq", "openai", ...) when flagging any other provider's failure.
    """
    if severity not in ("yellow", "red"):
        logger.debug("[QUOTA-ALERT] Ignoring unknown severity %r", severity)
        return

    error_detail = _clip(str(error))

    try:
        db = _get_db()
    except Exception as exc:
        logger.error("[QUOTA-ALERT] Could not reach DB to persist flag event: %s", exc)
        db = None

    notified = False
    if db is not None:
        # Notify first so the persisted row's `notified` column reflects the real outcome
        # in a single insert — but persistence below is unconditional either way, so the
        # audit trail exists even if this raises.
        try:
            notified = _notify_founder(db, severity, step_name, model, error_detail, provider, key_type)
        except Exception as exc:
            logger.error("[QUOTA-ALERT] Failed to push-notify founder (step=%s): %s", step_name, exc)

        try:
            _persist(db, severity, step_name, model, key_type, error_detail, notified=notified, provider=provider)
        except Exception as exc:
            logger.error("[QUOTA-ALERT] Failed to persist flag event (step=%s): %s", step_name, exc)

    logger.warning(
        "[QUOTA-ALERT] severity=%s provider=%s step=%s model=%s key=%s notified=%s",
        severity, provider, step_name, model, key_type, notified,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _get_db():
    from truebrief.ledger.database import get_supabase
    return get_supabase()


def _clip(s: str, limit: int = 1500) -> str:
    return s if len(s) <= limit else s[:limit] + f"…[truncated {len(s) - limit} chars]"


def _persist(
    db, severity: str, step_name: str, model: str, key_type: str, error_detail: str, notified: bool,
    provider: str = "gemini",
) -> None:
    db.table("quota_alerts").insert({
        "severity": severity,
        "step_name": step_name,
        "model": model,
        "key_type": key_type,
        "error_detail": error_detail,
        "notified": notified,
        "provider": provider,
    }).execute()


def _founder_user_id(db) -> Optional[str]:
    """Resolve the founder's `users.id` row from FOUNDER_EMAIL / ADMIN_EMAILS.

    Same allowlist api/routes.py's _is_admin() trusts. FOUNDER_EMAIL wins if set; else the
    first entry in the comma-separated ADMIN_EMAILS list.
    """
    from config.settings import settings

    email = (getattr(settings, "FOUNDER_EMAIL", "") or "").strip().lower()
    if not email:
        emails = [e.strip().lower() for e in (getattr(settings, "ADMIN_EMAILS", "") or "").split(",") if e.strip()]
        email = emails[0] if emails else ""
    if not email:
        return None

    res = db.table("users").select("id").eq("email", email).limit(1).execute()
    rows = res.data or []
    return rows[0]["id"] if rows else None


def _notify_founder(
    db, severity: str, step_name: str, model: str, error_detail: str,
    provider: str = "gemini", key_type: str = "",
) -> bool:
    """Push a real-time notification to every active subscription the founder has.

    Returns True if at least one push was delivered successfully.
    """
    user_id = _founder_user_id(db)
    if not user_id:
        logger.warning("[QUOTA-ALERT] No founder user_id resolvable (FOUNDER_EMAIL/ADMIN_EMAILS) — skipping push.")
        return False

    res = (
        db.table("push_subscriptions")
        .select("id, endpoint, p256dh, auth")
        .eq("user_id", user_id)
        .eq("enabled", True)
        .execute()
    )
    subs = res.data or []
    if not subs:
        logger.warning("[QUOTA-ALERT] Founder has no active push subscription — flag persisted but not pushed.")
        return False

    # "gemini primary key" / "gemini backup key" keeps the original, specific wording for
    # Gemini's own dual-key rotation; any other provider (or key_type="single") just names
    # the provider — Linkup/Brave/Groq/OpenAI have no primary/backup concept.
    where = f"{provider} {key_type} key" if key_type in ("primary", "backup") else provider
    if severity == "red":
        title = _RED_TITLE
        body = f"{where} failed for {step_name}/{model} — no working fallback left, call is failing/degraded."
    else:
        title = _YELLOW_TITLE
        body = f"{where} failed for {step_name}/{model} — a fallback covered it, call still succeeded."

    from truebrief.push.client import send_push

    any_sent = False
    for row in subs:
        try:
            ok = send_push(
                subscription_info={
                    "endpoint": row["endpoint"],
                    "keys": {"p256dh": row["p256dh"], "auth": row["auth"]},
                },
                title=title,
                body=body,
                url="/admin",
            )
        except Exception as exc:
            logger.error("[QUOTA-ALERT] send_push raised for subscription %s: %s", row.get("id"), exc)
            ok = False
        any_sent = any_sent or ok

    return any_sent


def recent_alerts(hours: int = 48, limit: int = 100) -> list:
    """Return recent quota_alerts rows (newest first) for the admin panel.

    Never raises — returns [] if the table doesn't exist yet (pre-migration-030) or the
    DB is unreachable, matching the fail-soft pattern the rest of /admin/metrics uses.
    """
    try:
        db = _get_db()
        res = (
            db.table("quota_alerts")
            .select("id, created_at, severity, step_name, model, key_type, error_detail, notified, provider")
            .gte("created_at", _hours_ago_iso(hours))
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as exc:
        logger.debug("[QUOTA-ALERT] recent_alerts() failed (non-fatal): %s", exc)
        return []


def _hours_ago_iso(hours: int) -> str:
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
