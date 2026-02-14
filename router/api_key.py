"""
API key management routes.

This router provides endpoints for authenticated users to create,
list and delete API keys.  API keys grant access to the main API
routes under ``/main_v1`` and should be treated as secrets.  A user
must have a verified account to manage API keys.  Deleting a key
revokes all access associated with it.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from database import get_session
from model.api_key import APIKey
from model.user import User
from services.user import get_current_user

api_key_router = APIRouter()


class APIKeyCreateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=100)


class APIKeyResponse(BaseModel):
    id: int
    key: str
    name: str | None = None
    created_at: str


@api_key_router.get("/api-keys", response_model=list[APIKeyResponse])
def list_api_keys(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[APIKeyResponse]:
    """Return all API keys belonging to the current user."""
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account not verified"
        )
    statement = select(APIKey).where(APIKey.user_id == current_user.id)
    keys = session.exec(statement).all()
    return [
        APIKeyResponse(
            id=key.id, key=key.key, name=key.name, created_at=key.created_at.isoformat()
        )
        for key in keys
    ]


@api_key_router.post(
    "/api-keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED
)
def create_api_key(
    payload: APIKeyCreateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> APIKeyResponse:
    """Create a new API key for the current user."""
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account not verified"
        )
    # Generate a unique API key
    key_value = secrets.token_urlsafe(32)
    api_key = APIKey(user_id=current_user.id, key=key_value, name=payload.name)
    session.add(api_key)
    session.commit()
    session.refresh(api_key)
    return APIKeyResponse(
        id=api_key.id,
        key=api_key.key,
        name=api_key.name,
        created_at=api_key.created_at.isoformat(),
    )


@api_key_router.delete("/api-keys/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_api_key(
    api_key_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    """Delete an API key owned by the current user."""
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account not verified"
        )
    api_key = session.get(APIKey, api_key_id)
    if not api_key or api_key.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
        )
    session.delete(api_key)
    session.commit()
    return None
