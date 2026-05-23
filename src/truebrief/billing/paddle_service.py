"""
Paddle Service - billing/paddle_service.py

Paddle Billing operations: customers, transactions (checkout), portal, webhooks.
All subscription state is mirrored to the user_subscriptions table in Supabase.

Paddle REST API docs: https://developer.paddle.com
Webhook verification: https://developer.paddle.com/webhooks/signature-verification
"""

import datetime
import hashlib
import hmac
import json
import logging
from typing import Optional

import httpx

from config.settings import settings
from truebrief.ledger.database import get_supabase
from truebrief.models.tier import Tier

logger = logging.getLogger(__name__)

_PADDLE_BASE = (
    "https://api.paddle.com"
    if settings.ENV == "production"
    else "https://sandbox-api.paddle.com"
)


def _price_to_tier(price_id: str) -> Tier:
    if price_id == settings.PADDLE_PRICE_PRO:
        return Tier.PRO
    if price_id == settings.PADDLE_PRICE_POWER:
        return Tier.POWER
    return Tier.FREE


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.PADDLE_API_KEY}",
        "Content-Type": "application/json",
    }


class PaddleService:

    def _db(self):
        return get_supabase()

    def _get_customer_id(self, user_id: str) -> Optional[str]:
        res = (
            self._db()
            .table("user_subscriptions")
            .select("paddle_customer_id")
            .eq("user_id", user_id)
            .execute()
        )
        return res.data[0]["paddle_customer_id"] if res.data else None

    def _already_processed(self, event_id: str) -> bool:
        res = (
            self._db()
            .table("processed_paddle_events")
            .select("event_id")
            .eq("event_id", event_id)
            .execute()
        )
        return len(res.data) > 0

    def _record_event(self, event_id: str, event_type: str) -> None:
        self._db().table("processed_paddle_events").insert(
            {"event_id": event_id, "event_type": event_type}
        ).execute()

    # ------------------------------------------------------------------
    # Checkout
    # ------------------------------------------------------------------

    def create_checkout_session(
        self,
        user_id: str,
        email: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
    ) -> dict:
        customer_id = self._get_customer_id(user_id)

        if not customer_id:
            resp = httpx.post(
                f"{_PADDLE_BASE}/customers",
                headers=_headers(),
                json={"email": email, "custom_data": {"user_id": user_id}},
                timeout=10.0,
            )
            resp.raise_for_status()
            customer_id = resp.json()["data"]["id"]
            self._db().table("user_subscriptions").upsert(
                {
                    "user_id": user_id,
                    "paddle_customer_id": customer_id,
                    "tier": "free",
                    "status": "active",
                },
                on_conflict="user_id",
            ).execute()

        resp = httpx.post(
            f"{_PADDLE_BASE}/transactions",
            headers=_headers(),
            json={
                "items": [{"price_id": price_id, "quantity": 1}],
                "customer_id": customer_id,
                "checkout": {"url": success_url},
                "custom_data": {"user_id": user_id},
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        return {
            "checkout_url": data["checkout"]["url"],
            "transaction_id": data["id"],
        }

    # ------------------------------------------------------------------
    # Customer Portal
    # ------------------------------------------------------------------

    def create_portal_session(self, user_id: str, return_url: str) -> str:
        customer_id = self._get_customer_id(user_id)
        if not customer_id:
            raise ValueError(f"No Paddle customer found for user {user_id}")

        resp = httpx.post(
            f"{_PADDLE_BASE}/customers/{customer_id}/auth-token",
            headers=_headers(),
            timeout=10.0,
        )
        resp.raise_for_status()
        token = resp.json()["data"]["customer_auth_token"]
        return f"https://customer.paddle.com/?customer_auth_token={token}"

    # ------------------------------------------------------------------
    # Subscription state (read from DB)
    # ------------------------------------------------------------------

    def get_subscription(self, user_id: str) -> Optional[dict]:
        res = (
            self._db()
            .table("user_subscriptions")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        return res.data[0] if res.data else None

    # ------------------------------------------------------------------
    # Webhook
    # ------------------------------------------------------------------

    def handle_webhook(self, payload: bytes, signature_header: Optional[str]) -> None:
        if not signature_header:
            raise ValueError("Missing Paddle-Signature header")

        self._verify_signature(payload, signature_header)

        event = json.loads(payload)
        event_type = event.get("event_type", "")
        event_id = event.get("notification_id", "")

        if self._already_processed(event_id):
            logger.info("Paddle event %s already processed, skipping.", event_id)
            return

        self._record_event(event_id, event_type)
        logger.info("Paddle webhook: %s (%s)", event_type, event_id)

        data = event.get("data", {})
        if event_type in ("subscription.created", "subscription.updated"):
            self._sync_subscription(data)
        elif event_type == "subscription.canceled":
            self._cancel_subscription(data)
        elif event_type == "transaction.payment_failed":
            self._mark_past_due(data)
        elif event_type == "transaction.completed":
            logger.info("Transaction completed: %s", data.get("id"))

    def _verify_signature(self, payload: bytes, signature_header: str) -> None:
        """Paddle webhook signature: ts=<timestamp>;h1=<hmac-sha256-hex>"""
        try:
            parts = dict(p.split("=", 1) for p in signature_header.split(";"))
            ts = parts["ts"]
            h1 = parts["h1"]
        except (KeyError, ValueError) as e:
            raise ValueError(f"Malformed Paddle-Signature header: {e}")

        signed = f"{ts}:{payload.decode()}"
        expected = hmac.new(
            settings.PADDLE_WEBHOOK_SECRET.encode(),
            signed.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, h1):
            raise ValueError("Webhook signature mismatch")

    def _sync_subscription(self, sub: dict) -> None:
        customer_id = sub.get("customer_id")
        items = sub.get("items", [])
        price_id = items[0]["price"]["id"] if items else None
        tier = _price_to_tier(price_id).value if price_id else "free"

        period_end = sub.get("current_billing_period", {}).get("ends_at")

        res = (
            self._db()
            .table("user_subscriptions")
            .select("user_id")
            .eq("paddle_customer_id", customer_id)
            .execute()
        )
        if not res.data:
            logger.warning("No user found for Paddle customer %s", customer_id)
            return

        user_id = res.data[0]["user_id"]
        self._db().table("user_subscriptions").upsert(
            {
                "user_id": user_id,
                "paddle_customer_id": customer_id,
                "paddle_subscription_id": sub["id"],
                "tier": tier,
                "status": sub.get("status", "active"),
                "current_period_end": period_end,
            },
            on_conflict="user_id",
        ).execute()
        logger.info(
            "Subscription synced: user=%s tier=%s status=%s",
            user_id, tier, sub.get("status"),
        )

    def _cancel_subscription(self, sub: dict) -> None:
        customer_id = sub.get("customer_id")
        self._db().table("user_subscriptions").update(
            {"tier": "free", "status": "canceled", "paddle_subscription_id": None}
        ).eq("paddle_customer_id", customer_id).execute()
        logger.info("Subscription canceled for customer %s", customer_id)

    def _mark_past_due(self, data: dict) -> None:
        customer_id = data.get("customer_id")
        self._db().table("user_subscriptions").update(
            {"status": "past_due"}
        ).eq("paddle_customer_id", customer_id).execute()
        logger.info("Subscription past_due for customer %s", customer_id)
