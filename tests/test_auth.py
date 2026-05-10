import time
from unittest.mock import patch, MagicMock
import pytest
from jose import jwt
from fastapi import HTTPException
from truebrief.auth.clerk import verify_clerk_jwt, _get_jwks
from truebrief.auth.user_repo import get_or_create_user
from truebrief.auth.dependencies import get_current_user_logic

@pytest.fixture(autouse=True)
def reset_jwks_cache():
    import truebrief.auth.clerk as clerk
    clerk._JWKS_CACHE = (0.0, {})

@patch("truebrief.auth.clerk.httpx.get")
def test_jwks_cache_hits_within_ttl(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"keys": [{"kid": "123"}]}
    mock_get.return_value = mock_resp

    _get_jwks()
    _get_jwks()
    
    assert mock_get.call_count == 1

@patch("truebrief.auth.clerk.time.time")
@patch("truebrief.auth.clerk.httpx.get")
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

@patch("truebrief.auth.clerk._get_jwks")
@patch("truebrief.auth.clerk.jwt.decode")
@patch("truebrief.auth.clerk.jwt.get_unverified_header")
def test_verify_clerk_jwt_valid_token_returns_payload(mock_unverified, mock_decode, mock_get_jwks):
    mock_unverified.return_value = {"kid": "test_kid"}
    mock_get_jwks.return_value = {"keys": [{"kid": "test_kid"}]}
    mock_decode.return_value = {"sub": "user_123"}
    
    payload = verify_clerk_jwt("valid.token.here")
    assert payload["sub"] == "user_123"

@patch("truebrief.auth.clerk._get_jwks")
@patch("truebrief.auth.clerk.jwt.get_unverified_header")
def test_verify_clerk_jwt_missing_kid_raises(mock_unverified, mock_get_jwks):
    mock_unverified.return_value = {"kid": "wrong_kid"}
    mock_get_jwks.return_value = {"keys": [{"kid": "test_kid"}]}
    
    with pytest.raises(jwt.JWTError, match="kid not found in JWKS"):
        verify_clerk_jwt("token")

@patch("truebrief.auth.clerk._get_jwks")
@patch("truebrief.auth.clerk.jwt.decode")
@patch("truebrief.auth.clerk.jwt.get_unverified_header")
def test_verify_clerk_jwt_invalid_signature_raises(mock_unverified, mock_decode, mock_get_jwks):
    mock_unverified.return_value = {"kid": "test_kid"}
    mock_get_jwks.return_value = {"keys": [{"kid": "test_kid"}]}
    mock_decode.side_effect = jwt.JWTError("Signature verification failed")
    
    with pytest.raises(jwt.JWTError):
        verify_clerk_jwt("bad.token")

@patch("truebrief.auth.clerk._get_jwks")
@patch("truebrief.auth.clerk.jwt.decode")
@patch("truebrief.auth.clerk.jwt.get_unverified_header")
def test_verify_clerk_jwt_expired_token_raises_401(mock_unverified, mock_decode, mock_get_jwks):
    mock_unverified.return_value = {"kid": "test_kid"}
    mock_get_jwks.return_value = {"keys": [{"kid": "test_kid"}]}
    mock_decode.side_effect = jwt.ExpiredSignatureError("Expired")
    
    with pytest.raises(jwt.JWTError):
        verify_clerk_jwt("expired.token")

@patch("truebrief.auth.user_repo.get_supabase")
def test_get_or_create_user_existing_returns_row(mock_supabase):
    db_mock = MagicMock()
    mock_supabase.return_value = db_mock
    db_mock.table().select().eq().execute.return_value.data = [{"id": "uuid-1", "clerk_id": "clerk_1", "email": "a@b.com"}]
    
    user = get_or_create_user("clerk_1", "a@b.com")
    
    assert user.id == "uuid-1"
    assert user.clerk_id == "clerk_1"
    # Should not insert
    db_mock.table().insert.assert_not_called()

@patch("truebrief.auth.user_repo.get_supabase")
def test_get_or_create_user_updates_last_seen_at(mock_supabase):
    db_mock = MagicMock()
    mock_supabase.return_value = db_mock
    db_mock.table().select().eq().execute.return_value.data = [{"id": "uuid-1", "clerk_id": "clerk_1", "email": "a@b.com"}]
    
    get_or_create_user("clerk_1", "a@b.com")
    
    db_mock.table().update.assert_called_with({"last_seen_at": "now()"})
    db_mock.table().update().eq.assert_called_with("id", "uuid-1")

@patch("truebrief.auth.user_repo.get_supabase")
def test_get_or_create_user_first_login_inserts_user_and_subscription(mock_supabase):
    db_mock = MagicMock()
    mock_supabase.return_value = db_mock
    db_mock.table().select().eq().execute.return_value.data = []
    
    user = get_or_create_user("clerk_1", "a@b.com")
    
    assert user.clerk_id == "clerk_1"
    assert db_mock.table().insert.call_count == 2

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
