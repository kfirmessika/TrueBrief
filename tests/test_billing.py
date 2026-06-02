import json
import hashlib
import hmac
import time
import pytest
from unittest.mock import MagicMock, patch
from truebrief.billing.paddle_service import PaddleService, _price_to_tier
from truebrief.models.tier import Tier
from config.settings import settings

MOCK_EVENT_ID = "ntf_123"
MOCK_CUSTOMER_ID = "ctm_123"
MOCK_SUB_ID = "sub_123"
MOCK_PRICE_PRO = "pri_pro"
MOCK_PRICE_POWER = "pri_power"


@pytest.fixture
def mock_settings(monkeypatch):
    monkeypatch.setattr(settings, "PADDLE_PRICE_PRO", MOCK_PRICE_PRO)
    monkeypatch.setattr(settings, "PADDLE_PRICE_POWER", MOCK_PRICE_POWER)
    monkeypatch.setattr(settings, "PADDLE_WEBHOOK_SECRET", "test_secret")
    return settings


@pytest.fixture
def paddle_service():
    service = PaddleService()
    service._db = MagicMock()
    return service


# ---------------------------------------------------------------------------
# Tier Mapping
# ---------------------------------------------------------------------------

def test_price_to_tier_pro(mock_settings):
    assert _price_to_tier(MOCK_PRICE_PRO) == Tier.PRO

def test_price_to_tier_power(mock_settings):
    assert _price_to_tier(MOCK_PRICE_POWER) == Tier.POWER

def test_price_to_tier_unknown_falls_back_to_free(mock_settings):
    assert _price_to_tier("unknown") == Tier.FREE


# ---------------------------------------------------------------------------
# Checkout Logic
# ---------------------------------------------------------------------------

@patch("httpx.post")
def test_create_checkout_first_time_creates_customer(mock_post, paddle_service):
    paddle_service._get_customer_id = MagicMock(return_value=None)

    # First call: create customer; second call: create transaction
    mock_post.side_effect = [
        MagicMock(status_code=200, json=lambda: {"data": {"id": MOCK_CUSTOMER_ID}}),
        MagicMock(status_code=200, json=lambda: {
            "data": {"id": "txn_1", "checkout": {"url": "https://pay.paddle.com/checkout/xxx"}}
        }),
    ]

    result = paddle_service.create_checkout_session(
        user_id="user_1",
        email="test@example.com",
        price_id=MOCK_PRICE_PRO,
        success_url="http://success",
        cancel_url="http://cancel",
    )

    assert result["checkout_url"].startswith("https://")
    paddle_service._db().table("user_subscriptions").upsert.assert_called_once()


@patch("httpx.post")
def test_create_checkout_reuses_existing_customer(mock_post, paddle_service):
    paddle_service._get_customer_id = MagicMock(return_value=MOCK_CUSTOMER_ID)

    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "data": {"id": "txn_1", "checkout": {"url": "https://pay.paddle.com/checkout/xxx"}}
        },
    )

    paddle_service.create_checkout_session(
        user_id="user_1",
        email="test@example.com",
        price_id=MOCK_PRICE_PRO,
        success_url="http://success",
        cancel_url="http://cancel",
    )

    # Only one httpx.post call (the transaction), not two (no customer create)
    assert mock_post.call_count == 1
    paddle_service._db().table("user_subscriptions").upsert.assert_not_called()


# ---------------------------------------------------------------------------
# Webhook Signature Verification
# ---------------------------------------------------------------------------

def _make_signature(payload: bytes, secret: str, ts: str = None) -> str:
    if ts is None:
        ts = str(int(time.time()))
    signed = f"{ts}:{payload.decode()}"
    h1 = hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()
    return f"ts={ts};h1={h1}"


def test_webhook_bad_signature_raises_value_error(paddle_service, mock_settings):
    fresh_ts = str(int(time.time()))
    with pytest.raises(ValueError, match="signature mismatch"):
        paddle_service.handle_webhook(b'{"event_type":"x"}', f"ts={fresh_ts};h1=bad")


def test_webhook_missing_signature_raises_value_error(paddle_service):
    with pytest.raises(ValueError, match="Missing Paddle-Signature"):
        paddle_service.handle_webhook(b'{}', None)


def test_webhook_duplicate_event_short_circuits(paddle_service, mock_settings):
    payload = json.dumps({
        "notification_id": MOCK_EVENT_ID,
        "event_type": "subscription.created",
        "data": {},
    }).encode()
    sig = _make_signature(payload, "test_secret")

    paddle_service._already_processed = MagicMock(return_value=True)
    paddle_service._record_event = MagicMock()
    paddle_service._sync_subscription = MagicMock()

    paddle_service.handle_webhook(payload, sig)

    paddle_service._record_event.assert_not_called()
    paddle_service._sync_subscription.assert_not_called()


# ---------------------------------------------------------------------------
# Webhook Event Handling
# ---------------------------------------------------------------------------

def test_webhook_subscription_created_syncs_pro_tier(paddle_service, mock_settings):
    data = {
        "id": MOCK_SUB_ID,
        "customer_id": MOCK_CUSTOMER_ID,
        "status": "active",
        "current_billing_period": {"ends_at": "2026-06-01T00:00:00Z"},
        "items": [{"price": {"id": MOCK_PRICE_PRO}}],
    }
    payload = json.dumps({
        "notification_id": MOCK_EVENT_ID,
        "event_type": "subscription.created",
        "data": data,
    }).encode()
    sig = _make_signature(payload, "test_secret")

    paddle_service._already_processed = MagicMock(return_value=False)
    paddle_service._db().table("user_subscriptions").select().eq().execute.return_value = MagicMock(
        data=[{"user_id": "user_1"}]
    )

    paddle_service.handle_webhook(payload, sig)

    paddle_service._db().table("user_subscriptions").upsert.assert_called_once()
    args = paddle_service._db().table("user_subscriptions").upsert.call_args[0][0]
    assert args["tier"] == "pro"
    assert args["status"] == "active"


def test_webhook_subscription_canceled_downgrades_to_free(paddle_service, mock_settings):
    data = {"id": MOCK_SUB_ID, "customer_id": MOCK_CUSTOMER_ID}
    payload = json.dumps({
        "notification_id": MOCK_EVENT_ID,
        "event_type": "subscription.canceled",
        "data": data,
    }).encode()
    sig = _make_signature(payload, "test_secret")

    paddle_service._already_processed = MagicMock(return_value=False)

    paddle_service.handle_webhook(payload, sig)

    paddle_service._db().table("user_subscriptions").update.assert_called_with(
        {"tier": "free", "status": "canceled", "paddle_subscription_id": None}
    )


def test_webhook_payment_failed_marks_past_due(paddle_service, mock_settings):
    data = {"customer_id": MOCK_CUSTOMER_ID}
    payload = json.dumps({
        "notification_id": MOCK_EVENT_ID,
        "event_type": "transaction.payment_failed",
        "data": data,
    }).encode()
    sig = _make_signature(payload, "test_secret")

    paddle_service._already_processed = MagicMock(return_value=False)

    paddle_service.handle_webhook(payload, sig)

    paddle_service._db().table("user_subscriptions").update.assert_called_with(
        {"status": "past_due"}
    )
