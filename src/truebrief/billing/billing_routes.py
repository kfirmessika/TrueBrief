"""
Billing API Routes - billing/billing_routes.py

Stripe subscription management endpoints.

Endpoints:
  GET  /billing/tiers               - Public tier definitions
  POST /billing/checkout            - Create Stripe Checkout session
  POST /billing/portal              - Create Stripe Customer Portal session
  POST /billing/webhook             - Stripe webhook receiver (raw body required)
  GET  /billing/status/{user_id}    - Current tier & limits for a user
"""

import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request, Depends
from pydantic import BaseModel

from config.settings import settings
from truebrief.billing.stripe_service import StripeService
from truebrief.models.tier import TIER_LIMITS, Tier
from truebrief.auth.dependencies import User, get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)
_stripe = StripeService()


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

@router.get("/tiers")
def get_tiers():
    """Return tier definitions — public, no auth needed."""
    return {
        tier.value: {
            "max_topics": limits.max_topics,
            "min_interval_hours": limits.min_interval_hours,
            "sources": limits.sources,
            "private_topics": limits.private_topics,
        }
        for tier, limits in TIER_LIMITS.items()
    }


@router.post("/checkout")
def create_checkout_session(req: CheckoutRequest, user: User = Depends(get_current_user)):
    """Create a Stripe Checkout session. Returns a URL the client redirects to."""
    if req.tier not in ("pro", "power"):
        raise HTTPException(status_code=400, detail="tier must be 'pro' or 'power'")

    price_id = settings.STRIPE_PRICE_PRO if req.tier == "pro" else settings.STRIPE_PRICE_POWER
    if not price_id:
        raise HTTPException(status_code=503, detail="Stripe price ID not configured")

    try:
        session = _stripe.create_checkout_session(
            user_id=user.id,
            email=user.email,
            price_id=price_id,
            success_url=req.success_url,
            cancel_url=req.cancel_url,
        )
        return {"checkout_url": session.url, "session_id": session.id}
    except Exception as e:
        logger.error("Stripe checkout error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portal")
def create_portal_session(req: PortalRequest, user: User = Depends(get_current_user)):
    """Create a Stripe Customer Portal session for managing subscriptions."""
    try:
        url = _stripe.create_portal_session(
            user_id=user.id,
            return_url=req.return_url,
        )
        return {"portal_url": url}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Stripe portal error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="stripe-signature"),
):
    """
    Stripe sends POST here on subscription events.
    Must use raw body — do NOT let FastAPI parse JSON first.
    """
    payload = await request.body()
    try:
        _stripe.handle_webhook(payload, stripe_signature)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Webhook processing error: %s", e)
        raise HTTPException(status_code=500, detail="Webhook processing failed")


@router.get("/status")
def get_subscription_status(user: User = Depends(get_current_user)):
    """Return the current tier, Stripe status, and enforced limits for a user."""
    sub = _stripe.get_subscription(user.id)
    tier_str = sub.get("tier", "free") if sub else "free"
    limits = TIER_LIMITS[Tier(tier_str)]

    return {
        "user_id": user.id,
        "tier": tier_str,
        "status": sub.get("status", "active") if sub else "active",
        "stripe_customer_id": sub.get("stripe_customer_id") if sub else None,
        "current_period_end": sub.get("current_period_end") if sub else None,
        "limits": {
            "max_topics": limits.max_topics,
            "min_interval_hours": limits.min_interval_hours,
            "sources": limits.sources,
            "private_topics": limits.private_topics,
        },
    }
