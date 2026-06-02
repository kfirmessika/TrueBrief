import time
import httpx
from jose import jwt
from config.settings import settings

_JWKS_CACHE: tuple[float, dict] = (0.0, {})
JWKS_TTL_SECONDS = 3600

def _get_jwks() -> dict:
    global _JWKS_CACHE
    now = time.time()
    expires_at, cached = _JWKS_CACHE
    if now < expires_at and cached:
        return cached
    resp = httpx.get(settings.CLERK_JWKS_URL, timeout=5.0)
    resp.raise_for_status()
    keys = resp.json()
    _JWKS_CACHE = (now + JWKS_TTL_SECONDS, keys)
    return keys

def verify_clerk_jwt(token: str) -> dict:
    if not settings.CLERK_ISSUER:
        raise jwt.JWTError("CLERK_ISSUER is not configured — cannot validate token issuer")

    jwks = _get_jwks()
    header = jwt.get_unverified_header(token)
    key = next((k for k in jwks["keys"] if k["kid"] == header["kid"]), None)
    if not key:
        raise jwt.JWTError("kid not found in JWKS")

    return jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        audience=settings.CLERK_AUDIENCE or None,  # Clerk audience is optional
        issuer=settings.CLERK_ISSUER,
    )
