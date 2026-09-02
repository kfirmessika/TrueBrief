"""
Billing API Routes - billing/billing_routes.py

Paddle subscription management endpoints.

Endpoints:
  GET  /billing/tiers       - Public tier definitions
  POST /billing/checkout    - Create Paddle checkout transaction
  POST /billing/portal      - Create Paddle Customer Portal session
  POST /billing/webhook     - Paddle webhook receiver (raw body required)
  GET  /billing/status      - Current tier & limits for authenticated user
"""

import logging
import os
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Header, HTTPException, Request, Depends
from pydantic import BaseModel

from config.settings import settings
from truebrief.billing.paddle_service import PaddleService
from truebrief.models.tier import TIER_LIMITS, Tier
from truebrief.auth.dependencies import User, get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)
_paddle = PaddleService()


def _allowed_origins() -> set[str]:
    raw = os.getenv("FRONTEND_URL", "http://localhost:3000")
    origins = set()
    for o in raw.split(","):
        o = o.strip()
        if not o:
            continue
        p = urlparse(o)
        if p.scheme and p.netloc:
            origins.add(f"{p.scheme}://{p.netloc}")
    return origins


def _require_same_origin(url: str, field: str) -> None:
    """Reject redirect URLs that don't point at our own frontend origin.

    success_url/cancel_url/return_url are user-supplied and handed to Paddle;
    without this an attacker could craft an open-redirect off the checkout flow.
    """
    p = urlparse(url or "")
    origin = f"{p.scheme}://{p.netloc}" if p.scheme and p.netloc else ""
    if origin not in _allowed_origins():
        raise HTTPException(status_code=400, detail=f"{field} must point to the app origin")


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CheckoutRequest(BaseModel):
    tier: str        # "pro" | "power"
    success_url: str
    cancel_url: str


class PortalRequest(BaseModel):
    return_url: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

_DISPLAY_PRICE_USD = {
    "free": 0.0,
    "pro": lambda: float(settings.PRICE_PRO_USD or 0.0),
    "power": lambda: float(settings.PRICE_POWER_USD or 0.0),
}


def _price_for(tier_value: str) -> float:
    p = _DISPLAY_PRICE_USD.get(tier_value, 0.0)
    return p() if callable(p) else p


@router.get("/tiers")
def get_tiers():
    """Return tier definitions — public, no auth needed."""
    return {
        tier.value: {
            "max_topics": limits.max_topics,
            "min_interval_hours": limits.min_interval_hours,
            "sources": limits.sources,
            "private_topics": limits.private_topics,
            "api_calls_per_day": limits.api_calls_per_day,
            "max_scans_per_day": limits.max_scans_per_day,
            "price_usd_month": _price_for(tier.value),
        }
        for tier, limits in TIER_LIMITS.items()
    }


@router.post("/checkout")
def create_checkout_session(req: CheckoutRequest, user: User = Depends(get_current_user)):
    """Create a Paddle checkout transaction. Returns a URL the client redirects to."""
    if req.tier not in ("pro", "power"):
        raise HTTPException(status_code=400, detail="tier must be 'pro' or 'power'")
    _require_same_origin(req.success_url, "success_url")
    _require_same_origin(req.cancel_url, "cancel_url")

    price_id = settings.PADDLE_PRICE_PRO if req.tier == "pro" else settings.PADDLE_PRICE_POWER
    if not price_id:
        raise HTTPException(status_code=503, detail="Paddle price ID not configured")

    try:
        result = _paddle.create_checkout_session(
            user_id=user.id,
            email=user.email,
            price_id=price_id,
            success_url=req.success_url,
            cancel_url=req.cancel_url,
        )
        return {"checkout_url": result["checkout_url"], "transaction_id": result["transaction_id"]}
    except Exception as e:
        logger.error("Paddle checkout error: %s", e)
        raise HTTPException(status_code=500, detail="Could not start checkout.")


@router.post("/portal")
def create_portal_session(req: PortalRequest, user: User = Depends(get_current_user)):
    """Create a Paddle Customer Portal session for managing subscriptions."""
    _require_same_origin(req.return_url, "return_url")
    try:
        url = _paddle.create_portal_session(
            user_id=user.id,
            return_url=req.return_url,
        )
        return {"portal_url": url}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Paddle portal error: %s", e)
        raise HTTPException(status_code=500, detail="Could not open billing portal.")


@router.post("/webhook")
async def paddle_webhook(
    request: Request,
    paddle_signature: Optional[str] = Header(None, alias="paddle-signature"),
):
    """
    Paddle sends POST here on subscription events.
    Must use raw body — do NOT let FastAPI parse JSON first.
    """
    payload = await request.body()
    try:
        _paddle.handle_webhook(payload, paddle_signature)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Webhook processing error: %s", e)
        raise HTTPException(status_code=500, detail="Webhook processing failed")


@router.get("/status")
def get_subscription_status(user: User = Depends(get_current_user)):
    """Return the current tier, Paddle status, and enforced limits for a user."""
    from truebrief.billing.tiers import resolve_effective_tier

    sub = _paddle.get_subscription(user.id)
    billed_tier = sub.get("tier", "free") if sub else "free"
    status = sub.get("status", "active") if sub else "active"
    # Limits follow the *effective* tier: a past-due-beyond-grace or canceled
    # subscription is enforced as free even while `tier` still reads "pro".
    effective_tier = resolve_effective_tier(sub)
    limits = TIER_LIMITS[Tier(effective_tier)]

    return {
        "user_id": user.id,
        "tier": effective_tier,
        "billed_tier": billed_tier,
        "status": status,
        "past_due_since": sub.get("past_due_since") if sub else None,
        "paddle_customer_id": sub.get("paddle_customer_id") if sub else None,
        "current_period_end": sub.get("current_period_end") if sub else None,
        "limits": {
            "max_topics": limits.max_topics,
            "min_interval_hours": limits.min_interval_hours,
            "sources": limits.sources,
            "private_topics": limits.private_topics,
            "api_calls_per_day": limits.api_calls_per_day,
            "max_scans_per_day": limits.max_scans_per_day,
            "price_usd_month": _price_for(effective_tier),
        },
    }
