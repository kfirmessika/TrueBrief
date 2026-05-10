import pytest
from unittest.mock import MagicMock, patch
from truebrief.billing.stripe_service import StripeService, _price_to_tier
from truebrief.models.tier import Tier
from config.settings import settings

# Sample Stripe data
MOCK_EVENT_ID = "evt_123"
MOCK_CUSTOMER_ID = "cus_123"
MOCK_SUB_ID = "sub_123"
MOCK_PRICE_PRO = "price_pro"
MOCK_PRICE_POWER = "price_power"

@pytest.fixture
def mock_settings(monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_PRICE_PRO", MOCK_PRICE_PRO)
    monkeypatch.setattr(settings, "STRIPE_PRICE_POWER", MOCK_PRICE_POWER)
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    return settings

@pytest.fixture
def stripe_service():
    service = StripeService()
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

@patch("stripe.Customer.create")
@patch("stripe.checkout.Session.create")
def test_create_checkout_first_time_creates_customer(mock_session_create, mock_customer_create, stripe_service):
    stripe_service._get_customer_id = MagicMock(return_value=None)
    mock_customer_create.return_value = MagicMock(id=MOCK_CUSTOMER_ID)
    mock_session_create.return_value = MagicMock(url="http://stripe.com/checkout", id="sess_123")
    
    stripe_service.create_checkout_session(
        user_id="user_1",
        email="test@example.com",
        price_id=MOCK_PRICE_PRO,
        success_url="http://success",
        cancel_url="http://cancel"
    )
    
    mock_customer_create.assert_called_once_with(email="test@example.com", metadata={"user_id": "user_1"})
    stripe_service._db().table("user_subscriptions").upsert.assert_called_once()

@patch("stripe.Customer.create")
@patch("stripe.checkout.Session.create")
def test_create_checkout_reuses_existing_customer(mock_session_create, mock_customer_create, stripe_service):
    stripe_service._get_customer_id = MagicMock(return_value=MOCK_CUSTOMER_ID)
    mock_session_create.return_value = MagicMock(url="http://stripe.com/checkout", id="sess_123")
    
    stripe_service.create_checkout_session(
        user_id="user_1",
        email="test@example.com",
        price_id=MOCK_PRICE_PRO,
        success_url="http://success",
        cancel_url="http://cancel"
    )
    
    mock_customer_create.assert_not_called()
    stripe_service._db().table("user_subscriptions").upsert.assert_not_called()

# ---------------------------------------------------------------------------
# Webhook Logic
# ---------------------------------------------------------------------------

@patch("stripe.Webhook.construct_event")
def test_webhook_bad_signature_raises_value_error(mock_construct, stripe_service):
    mock_construct.side_effect = Exception("Invalid signature")
    with pytest.raises(ValueError, match="Webhook verification failed"):
        stripe_service.handle_webhook(b"payload", "bad_sig")

@patch("stripe.Webhook.construct_event")
def test_webhook_duplicate_event_short_circuits(mock_construct, stripe_service):
    mock_construct.return_value = {"id": MOCK_EVENT_ID, "type": "customer.subscription.created"}
    stripe_service._already_processed = MagicMock(return_value=True)
    stripe_service._record_event = MagicMock()
    stripe_service._sync_subscription = MagicMock()
    
    stripe_service.handle_webhook(b"payload", "sig")
    
    stripe_service._record_event.assert_not_called()
    stripe_service._sync_subscription.assert_not_called()

@patch("stripe.Webhook.construct_event")
def test_webhook_subscription_created_upserts_row_with_pro_tier(mock_construct, stripe_service, mock_settings):
    mock_construct.return_value = {
        "id": MOCK_EVENT_ID,
        "type": "customer.subscription.created",
        "data": {
            "object": {
                "id": MOCK_SUB_ID,
                "customer": MOCK_CUSTOMER_ID,
                "status": "active",
                "current_period_end": 1700000000,
                "items": {"data": [{"price": {"id": MOCK_PRICE_PRO}}]}
            }
        }
    }
    stripe_service._already_processed = MagicMock(return_value=False)
    stripe_service._db().table("user_subscriptions").select().execute.return_value = MagicMock(data=[{"user_id": "user_1"}])
    
    stripe_service.handle_webhook(b"payload", "sig")
    
    stripe_service._db().table("user_subscriptions").upsert.assert_called_once()
    args = stripe_service._db().table("user_subscriptions").upsert.call_args[0][0]
    assert args["tier"] == "pro"
    assert args["status"] == "active"

@patch("stripe.Webhook.construct_event")
def test_webhook_subscription_deleted_downgrades_to_free(mock_construct, stripe_service):
    mock_construct.return_value = {
        "id": MOCK_EVENT_ID,
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": MOCK_SUB_ID,
                "customer": MOCK_CUSTOMER_ID
            }
        }
    }
    stripe_service._already_processed = MagicMock(return_value=False)
    
    stripe_service.handle_webhook(b"payload", "sig")
    
    stripe_service._db().table("user_subscriptions").update.assert_called_with(
        {"tier": "free", "status": "canceled", "stripe_subscription_id": None}
    )

@patch("stripe.Webhook.construct_event")
def test_webhook_payment_failed_marks_past_due(mock_construct, stripe_service):
    mock_construct.return_value = {
        "id": MOCK_EVENT_ID,
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "customer": MOCK_CUSTOMER_ID
            }
        }
    }
    stripe_service._already_processed = MagicMock(return_value=False)
    
    stripe_service.handle_webhook(b"payload", "sig")
    
    stripe_service._db().table("user_subscriptions").update.assert_called_with(
        {"status": "past_due"}
    )

# ---------------------------------------------------------------------------
# Period End Extraction
# ---------------------------------------------------------------------------

def test_extract_period_end_root_path(stripe_service):
    sub = {"current_period_end": 123456789}
    assert stripe_service._extract_period_end(sub) == 123456789

def test_extract_period_end_item_path(stripe_service):
    sub = {"items": {"data": [{"current_period_end": 987654321}]}}
    assert stripe_service._extract_period_end(sub) == 987654321

def test_extract_period_end_none(stripe_service):
    sub = {}
    assert stripe_service._extract_period_end(sub) is None
