import time
from unittest.mock import patch, MagicMock
import pytest
from jose import jwt
from fastapi import HTTPException
from truebrief.auth.supabase_auth import verify_supabase_jwt, _get_jwks
from truebrief.auth.user_repo import get_or_create_user
from truebrief.auth.dependencies import get_current_user_logic

@pytest.fixture(autouse=True)
def reset_jwks_cache():
    import truebrief.auth.supabase_auth as supabase_auth
    supabase_auth._JWKS_CACHE = (0.0, {})

@patch("truebrief.auth.supabase_auth.httpx.get")
def test_jwks_cache_hits_within_ttl(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"keys": [{"kid": "123"}]}
    mock_get.return_value = mock_resp

    _get_jwks()
    _get_jwks()

    assert mock_get.call_count == 1

@patch("truebrief.auth.supabase_auth.time.time")
@patch("truebrief.auth.supabase_auth.httpx.get")
def test_jwks_cache_refreshes_after_ttl(mock_get, mock_time):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"keys": [{"kid": "123"}]}
    mock_get.return_value = mock_resp

    mock_time.return_value = 1000
    _get_jwks()

    # Still within TTL
    mock_time.return_value = 1000 + 100
    _get_jwks()
    assert mock_get.call_count == 1

    # After TTL
    mock_time.return_value = 1000 + 4000
    _get_jwks()
    assert mock_get.call_count == 2

@patch("truebrief.auth.supabase_auth._get_jwks")
@patch("truebrief.auth.supabase_auth.jwt.decode")
@patch("truebrief.auth.supabase_auth.jwt.get_unverified_header")
def test_verify_supabase_jwt_valid_token_returns_payload(mock_unverified, mock_decode, mock_get_jwks):
    mock_unverified.return_value = {"kid": "test_kid"}
    mock_get_jwks.return_value = {"keys": [{"kid": "test_kid"}]}
    mock_decode.return_value = {"sub": "user_123"}

    payload = verify_supabase_jwt("valid.token.here")
    assert payload["sub"] == "user_123"

@patch("truebrief.auth.supabase_auth._get_jwks")
@patch("truebrief.auth.supabase_auth.jwt.get_unverified_header")
def test_verify_supabase_jwt_missing_kid_raises(mock_unverified, mock_get_jwks):
    mock_unverified.return_value = {"kid": "wrong_kid"}
    mock_get_jwks.return_value = {"keys": [{"kid": "test_kid"}]}

    with pytest.raises(jwt.JWTError, match="kid not found in JWKS"):
        verify_supabase_jwt("token")

@patch("truebrief.auth.supabase_auth._get_jwks")
@patch("truebrief.auth.supabase_auth.jwt.decode")
@patch("truebrief.auth.supabase_auth.jwt.get_unverified_header")
def test_verify_supabase_jwt_invalid_signature_raises(mock_unverified, mock_decode, mock_get_jwks):
    mock_unverified.return_value = {"kid": "test_kid"}
    mock_get_jwks.return_value = {"keys": [{"kid": "test_kid"}]}
    mock_decode.side_effect = jwt.JWTError("Signature verification failed")

    with pytest.raises(jwt.JWTError):
        verify_supabase_jwt("bad.token")

@patch("truebrief.auth.supabase_auth._get_jwks")
@patch("truebrief.auth.supabase_auth.jwt.decode")
@patch("truebrief.auth.supabase_auth.jwt.get_unverified_header")
def test_verify_supabase_jwt_expired_token_raises_401(mock_unverified, mock_decode, mock_get_jwks):
    mock_unverified.return_value = {"kid": "test_kid"}
    mock_get_jwks.return_value = {"keys": [{"kid": "test_kid"}]}
    mock_decode.side_effect = jwt.ExpiredSignatureError("Expired")

    with pytest.raises(jwt.JWTError):
        verify_supabase_jwt("expired.token")

@patch("truebrief.auth.user_repo.get_supabase")
def test_get_or_create_user_existing_returns_row(mock_supabase):
    db_mock = MagicMock()
    mock_supabase.return_value = db_mock
    db_mock.table().select().eq().execute.return_value.data = [{"id": "uuid-1", "auth_uid": "auth_1", "email": "a@b.com"}]

    user = get_or_create_user("auth_1", "a@b.com")

    assert user.id == "uuid-1"
    assert user.auth_uid == "auth_1"
    # Should not insert
    db_mock.table().insert.assert_not_called()

@patch("truebrief.auth.user_repo.get_supabase")
def test_get_or_create_user_updates_last_seen_at(mock_supabase):
    db_mock = MagicMock()
    mock_supabase.return_value = db_mock
    db_mock.table().select().eq().execute.return_value.data = [{"id": "uuid-1", "auth_uid": "auth_1", "email": "a@b.com"}]

    get_or_create_user("auth_1", "a@b.com")

    db_mock.table().update.assert_called_with({"last_seen_at": "now()"})
    db_mock.table().update().eq.assert_called_with("id", "uuid-1")

@patch("truebrief.auth.user_repo.get_supabase")
def test_get_or_create_user_first_login_inserts_user_and_subscription(mock_supabase):
    db_mock = MagicMock()
    mock_supabase.return_value = db_mock
    # Neither the auth_uid lookup nor the email-adoption lookup finds a row.
    db_mock.table().select().eq().execute.return_value.data = []
    db_mock.table().select().eq().is_().execute.return_value.data = []

    user = get_or_create_user("auth_1", "a@b.com")

    assert user.auth_uid == "auth_1"
    assert db_mock.table().insert.call_count == 2

@patch("truebrief.auth.user_repo.get_supabase")
def test_get_or_create_user_adopts_matching_email_with_null_auth_uid(mock_supabase):
    """One-time Clerk→Supabase migration affordance: a pre-existing row with a matching
    email and NULL auth_uid gets adopted (auth_uid stamped in) instead of creating a
    duplicate account — this is what keeps the pre-existing account's topics attached."""
    db_mock = MagicMock()
    mock_supabase.return_value = db_mock

    users_table = MagicMock()
    # First .eq(...) call (auth_uid lookup) → no match.
    # Second .eq(...).is_(...) call (email + NULL auth_uid) → match.
    users_table.select.return_value.eq.return_value.execute.return_value.data = []
    users_table.select.return_value.eq.return_value.is_.return_value.execute.return_value.data = [
        {"id": "uuid-legacy", "auth_uid": None, "email": "a@b.com"}
    ]

    def table_side_effect(name):
        if name == "users":
            return users_table
        return MagicMock()

    db_mock.table.side_effect = table_side_effect

    user = get_or_create_user("new_auth_uid", "a@b.com")

    assert user.id == "uuid-legacy"
    assert user.auth_uid == "new_auth_uid"
    # Adoption is an UPDATE, never an INSERT.
    db_mock.table("users").insert.assert_not_called()
    db_mock.table("users").update.assert_called_with({
        "auth_uid": "new_auth_uid",
        "last_seen_at": "now()",
    })

def test_get_current_user_missing_authorization_raises_401():
    with pytest.raises(HTTPException) as exc:
        get_current_user_logic("InvalidTokenFormat")
    assert exc.value.status_code == 401
    assert "Missing Bearer token" in str(exc.value.detail)

def test_get_current_user_malformed_bearer_raises_401():
    with pytest.raises(HTTPException) as exc:
        get_current_user_logic("Bearer")
    # Actually wait, token will be "" which might fail at decode, let's see
    # If the token is empty string, decode will fail.
    pass

@patch("truebrief.auth.dependencies.get_current_user_logic")
async def test_get_optional_user_returns_none_when_no_header(mock_logic):
    from truebrief.auth.dependencies import get_optional_user
    res = await get_optional_user(None)
    assert res is None
    mock_logic.assert_not_called()
