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
import time
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
        elif event_type == "adjustment.created":
            self._handle_adjustment(data)
        else:
            logger.info("Paddle webhook: no handler for event_type=%s", event_type)

    _WEBHOOK_MAX_AGE_SECONDS = 300  # Reject webhooks older than 5 minutes

    def _verify_signature(self, payload: bytes, signature_header: str) -> None:
        """Paddle webhook signature: ts=<timestamp>;h1=<hmac-sha256-hex>"""
        try:
            parts = dict(p.split("=", 1) for p in signature_header.split(";"))
            ts = parts["ts"]
            h1 = parts["h1"]
        except (KeyError, ValueError) as e:
            raise ValueError(f"Malformed Paddle-Signature header: {e}")

        if abs(time.time() - int(ts)) > self._WEBHOOK_MAX_AGE_SECONDS:
            raise ValueError("Webhook timestamp too old — possible replay attack")

        if not settings.PADDLE_WEBHOOK_SECRET:
            # Fail CLOSED: an empty secret must never make every signature valid.
            logger.error("PADDLE_WEBHOOK_SECRET is not set — rejecting webhook (fail-closed).")
            raise ValueError("Webhook secret is not configured")

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
        status = sub.get("status", "active")

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
        record = {
            "user_id": user_id,
            "paddle_customer_id": customer_id,
            "paddle_subscription_id": sub["id"],
            "tier": tier,
            "status": status,
            "current_period_end": period_end,
        }
        # A recovered payment (status back to active/trialing) clears the past-due
        # grace clock so the paid tier is enforced again in full.
        if status in ("active", "trialing"):
            record["past_due_since"] = None
        try:
            self._db().table("user_subscriptions").upsert(
                record, on_conflict="user_id"
            ).execute()
        except Exception:
            record.pop("past_due_since", None)  # migration 036 not applied
            self._db().table("user_subscriptions").upsert(
                record, on_conflict="user_id"
            ).execute()
        logger.info("Subscription synced: user=%s tier=%s status=%s", user_id, tier, status)

    def _cancel_subscription(self, sub: dict) -> None:
        customer_id = sub.get("customer_id")
        self._db().table("user_subscriptions").update(
            {"tier": "free", "status": "canceled", "paddle_subscription_id": None}
        ).eq("paddle_customer_id", customer_id).execute()
        logger.info("Subscription canceled for customer %s", customer_id)

    def _mark_past_due(self, data: dict) -> None:
        customer_id = data.get("customer_id")
        try:
            row = (
                self._db()
                .table("user_subscriptions")
                .select("past_due_since")
                .eq("paddle_customer_id", customer_id)
                .execute()
            )
            already = row.data[0].get("past_due_since") if row.data else None
        except Exception:
            already = None  # migration 036 not applied yet
        update = {"status": "past_due"}
        # The FIRST failed payment starts the grace clock; later dunning retries
        # for the same lapse must not keep pushing the deadline out.
        if not already:
            update["past_due_since"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            self._db().table("user_subscriptions").update(update).eq(
                "paddle_customer_id", customer_id
            ).execute()
        except Exception:
            # migration 036 not applied — at least record the status
            self._db().table("user_subscriptions").update({"status": "past_due"}).eq(
                "paddle_customer_id", customer_id
            ).execute()
        logger.warning(
            "Subscription past_due for customer %s (grace started %s)",
            customer_id, update.get("past_due_since", already),
        )

    def _handle_adjustment(self, data: dict) -> None:
        """Paddle `adjustment.created` — refunds, credits, chargebacks. Downgrade on a
        refund/chargeback and log loudly (goes to the error stream) so a real dispute
        is never silent, matching the audit's 'at minimum alert on them'."""
        action = (data.get("action") or "").lower()
        customer_id = data.get("customer_id")
        adj_id = data.get("id")
        if action in ("refund", "chargeback", "chargeback_reverse", "credit_reverse"):
            logger.error(
                "Paddle adjustment %s=%s for customer %s — downgrading to free. "
                "Review in the Paddle dashboard.",
                action, adj_id, customer_id,
            )
            if customer_id:
                self._db().table("user_subscriptions").update(
                    {"tier": "free", "status": "canceled"}
                ).eq("paddle_customer_id", customer_id).execute()
        else:
            logger.info("Paddle adjustment %s=%s (customer %s) — no tier change", action, adj_id, customer_id)
