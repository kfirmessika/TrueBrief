from typing import Optional

from fastapi import Header, HTTPException
from jose import jwt

from truebrief.auth.clerk import verify_clerk_jwt
from truebrief.auth.models import User
from truebrief.auth.user_repo import get_or_create_user


def get_current_user_logic(authorization: Optional[str]) -> User:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    try:
        payload = verify_clerk_jwt(token)
    except jwt.JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    return get_or_create_user(
        clerk_id=payload["sub"],
        email=payload.get("email", ""),
    )


async def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> User:
    return get_current_user_logic(authorization)


async def get_optional_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> Optional[User]:
    if not authorization:
        return None
    return get_current_user_logic(authorization)
