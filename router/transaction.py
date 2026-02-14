"""
Transaction retrieval routes.

This router exposes an endpoint for fetching historical transactions
submitted via the ``/execute`` API. Users can filter the results by
API key or wallet address and can paginate through larger result sets.
Only transactions belonging to the current user are returned.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from database import get_session
from model.api_key import APIKey
from model.transaction import Transaction
from model.user import User
from services.user import get_current_user

transaction_router = APIRouter()


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # important for ORM/SQLModel

    id: int
    api_key_id: int
    hash: str
    address: str
    created_at: datetime


@transaction_router.get("/transactions", response_model=list[TransactionResponse])
def list_transactions(
    api_key: Optional[str] = Query(None, description="Filter by API key value"),
    address: Optional[str] = Query(None, description="Filter by wallet address"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=20, description="Number of items per page"),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[Transaction]:
    """Retrieve paginated transactions for the current user."""
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account not verified"
        )

    stmt = (
        select(Transaction)
        .join(APIKey, APIKey.id == Transaction.api_key_id)
        .where(APIKey.user_id == current_user.id)
    )

    if api_key:
        stmt = stmt.where(APIKey.key == api_key)

    if address:
        stmt = stmt.where(Transaction.address == address)

    stmt = stmt.order_by(Transaction.created_at.desc())

    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    transactions = session.exec(stmt).all()
    return transactions
