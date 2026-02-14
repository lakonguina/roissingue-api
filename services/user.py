"""
FastAPI dependency functions.

Reusable dependencies for retrieving the current authenticated user
via JWT Bearer token and validating API keys.

If a credential is missing or invalid, an appropriate HTTP error is raised.
"""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from database import get_session
from model.api_key import APIKey
from model.user import User
from services.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name="X-API-KEY", auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: Session = Depends(get_session),
) -> User:
    """
    Validate JWT Bearer token and return authenticated user.
    """

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )

    token = credentials.credentials

    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        if subject is None:
            raise ValueError("Invalid token payload")
        user_id = int(subject)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = session.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    request.state.user = user
    return user


def get_api_key(
    request: Request,
    api_key: str | None = Depends(api_key_scheme),
    session: Session = Depends(get_session),
) -> APIKey:
    """
    Validate API key and return APIKey object.
    """

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )

    api_key_obj = session.exec(select(APIKey).where(APIKey.key == api_key)).first()

    if not api_key_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    user = session.get(User, api_key_obj.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not verified",
        )

    request.state.user = user
    request.state.api_key = api_key_obj

    return api_key_obj
