"""
Stripe Service - billing/stripe_service.py

Core Stripe operations: customers, checkout sessions, portal, webhooks.
All subscription state is mirrored to the user_subscriptions table in Supabase.
"""

import datetime
import logging
from typing import Optional

import stripe

from config.settings import settings
from truebrief.ledger.database import get_supabase
from truebrief.models.tier import Tier

logger = logging.getLogger(__name__)

# Set once at import time; all stripe.* calls inherit it.
stripe.api_key = settings.STRIPE_SECRET_KEY


def _price_to_tier(price_id: str) -> Tier:
    if price_id == settings.STRIPE_PRICE_PRO:
        return Tier.PRO
    if price_id == settings.STRIPE_PRICE_POWER:
        return Tier.POWER
    return Tier.FREE


class StripeService:

    def _db(self):
        return get_supabase()

    def _get_customer_id(self, user_id: str) -> Optional[str]:
        res = (
            self._db()
            .table("user_subscriptions")
            .select("stripe_customer_id")
            .eq("user_id", user_id)
            .execute()
        )
        return res.data[0]["stripe_customer_id"] if res.data else None

    def _already_processed(self, event_id: str) -> bool:
        """Check if this event has already been handled."""
        res = (
            self._db()
            .table("processed_stripe_events")
            .select("event_id")
            .eq("event_id", event_id)
            .execute()
        )
        return len(res.data) > 0

    def _record_event(self, event_id: str, event_type: str) -> None:
        """Mark this event as processed."""
        self._db().table("processed_stripe_events").insert(
            {"event_id": event_id, "event_type": event_type}
        ).execute()

    def _extract_period_end(self, sub: dict) -> Optional[int]:
        """
        Defensively extract current_period_end from a subscription object.
        Checks both the root and the first item (modern API style).
        """
        # Try root first
        period_end = sub.get("current_period_end")
        if period_end:
            return period_end

        # Try items[0]
        items = sub.get("items", {}).get("data", [])
        if items:
            return items[0].get("current_period_end")

        return None

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
    ):
        """
        Find or create a Stripe Customer for this user, then open a
        Checkout session for the requested price.
        """
        customer_id = self._get_customer_id(user_id)

        if not customer_id:
            customer = stripe.Customer.create(
                email=email,
                metadata={"user_id": user_id},
            )
            customer_id = customer.id
            # Seed the subscriptions row so the webhook can find it later.
            self._db().table("user_subscriptions").upsert(
                {
                    "user_id": user_id,
                    "stripe_customer_id": customer_id,
                    "tier": "free",
                    "status": "active",
                },
                on_conflict="user_id",
            ).execute()

        return stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"user_id": user_id},
        )

    # ------------------------------------------------------------------
    # Customer Portal
    # ------------------------------------------------------------------

    def create_portal_session(self, user_id: str, return_url: str) -> str:
        customer_id = self._get_customer_id(user_id)
        if not customer_id:
            raise ValueError(f"No Stripe customer found for user {user_id}")

        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return session.url

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

    def handle_webhook(self, payload: bytes, sig_header: Optional[str]) -> None:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except Exception as e:
            raise ValueError(f"Webhook verification failed: {e}")

        etype = event["type"]
        eid = event["id"]

        if self._already_processed(eid):
            logger.info(f"Stripe event {eid} already processed, skipping.")
            return

        self._record_event(eid, etype)
        logger.info(f"Stripe webhook received: {etype} ({eid})")

        obj = event["data"]["object"]
        if etype in ("customer.subscription.created", "customer.subscription.updated"):
            self._sync_subscription(obj)
        elif etype == "customer.subscription.deleted":
            self._cancel_subscription(obj)
        elif etype == "invoice.payment_failed":
            self._mark_past_due(obj)
        elif etype == "checkout.session.completed":
            logger.info(
                "Checkout complete for user %s",
                obj.get("metadata", {}).get("user_id"),
            )

    def _sync_subscription(self, sub: dict) -> None:
        customer_id = sub["customer"]
        items = sub.get("items", {}).get("data", [])
        price_id = items[0]["price"]["id"] if items else None
        tier = _price_to_tier(price_id).value if price_id else "free"

        period_end = self._extract_period_end(sub)
        period_end_iso = (
            datetime.datetime.utcfromtimestamp(period_end).isoformat()
            if period_end
            else None
        )

        res = (
            self._db()
            .table("user_subscriptions")
            .select("user_id")
            .eq("stripe_customer_id", customer_id)
            .execute()
        )
        if not res.data:
            logger.warning("No user found for Stripe customer %s", customer_id)
            return

        user_id = res.data[0]["user_id"]
        self._db().table("user_subscriptions").upsert(
            {
                "user_id": user_id,
                "stripe_customer_id": customer_id,
                "stripe_subscription_id": sub["id"],
                "tier": tier,
                "status": sub["status"],
                "current_period_end": period_end_iso,
            },
            on_conflict="user_id",
        ).execute()
        logger.info("Subscription synced: user=%s tier=%s status=%s", user_id, tier, sub["status"])

    def _cancel_subscription(self, sub: dict) -> None:
        customer_id = sub["customer"]
        self._db().table("user_subscriptions").update(
            {"tier": "free", "status": "canceled", "stripe_subscription_id": None}
        ).eq("stripe_customer_id", customer_id).execute()
        logger.info("Subscription canceled for customer %s", customer_id)

    def _mark_past_due(self, invoice: dict) -> None:
        customer_id = invoice["customer"]
        self._db().table("user_subscriptions").update(
            {"status": "past_due"}
        ).eq("stripe_customer_id", customer_id).execute()
        logger.info("Subscription past_due for customer %s", customer_id)
