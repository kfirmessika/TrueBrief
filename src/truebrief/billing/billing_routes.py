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
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request, Depends
from pydantic import BaseModel

from config.settings import settings
from truebrief.billing.paddle_service import PaddleService
from truebrief.models.tier import TIER_LIMITS, Tier
from truebrief.auth.dependencies import User, get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)
_paddle = PaddleService()


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
    """Create a Paddle checkout transaction. Returns a URL the client redirects to."""
    if req.tier not in ("pro", "power"):
        raise HTTPException(status_code=400, detail="tier must be 'pro' or 'power'")

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
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portal")
def create_portal_session(req: PortalRequest, user: User = Depends(get_current_user)):
    """Create a Paddle Customer Portal session for managing subscriptions."""
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
        raise HTTPException(status_code=500, detail=str(e))


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
    sub = _paddle.get_subscription(user.id)
    tier_str = sub.get("tier", "free") if sub else "free"
    limits = TIER_LIMITS[Tier(tier_str)]

    return {
        "user_id": user.id,
        "tier": tier_str,
        "status": sub.get("status", "active") if sub else "active",
        "paddle_customer_id": sub.get("paddle_customer_id") if sub else None,
        "current_period_end": sub.get("current_period_end") if sub else None,
        "limits": {
            "max_topics": limits.max_topics,
            "min_interval_hours": limits.min_interval_hours,
            "sources": limits.sources,
            "private_topics": limits.private_topics,
        },
    }
