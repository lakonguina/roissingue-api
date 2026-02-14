"""
Transaction retrieval routes.

This router exposes an endpoint for fetching historical transactions
submitted via the ``/execute`` API.  Users can filter the results by
API key, status or wallet address and can paginate through larger
result sets.  Only transactions belonging to the current user are
returned.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel import Session, select

from database import get_session
from model.api_key import APIKey
from model.transaction import Transaction
from model.user import User
from services.user import get_current_user

transaction_router = APIRouter()


class TransactionResponse(BaseModel):
    id: int
    api_key: str
    status: str
    wallet: str
    extra_data: dict | None
    created_at: str


@transaction_router.get("/transactions", response_model=list[TransactionResponse])
def list_transactions(
    api_key: Optional[str] = Query(None, description="Filter by API key value"),
    address: Optional[str] = Query(None, description="Filter by wallet address"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page"),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[TransactionResponse]:
    """Retrieve paginated transactions for the current user.

    Filters can be applied on the API key value, status and wallet
    address.  Pagination is controlled via the ``page`` and
    ``page_size`` parameters.  Results are sorted by creation date
    descending.
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account not verified"
        )
    # Build query
    stmt = select(Transaction, APIKey).join(APIKey, APIKey.id == Transaction.api_key_id)
    # Restrict to current user's keys
    stmt = stmt.where(APIKey.user_id == current_user.id)
    # Apply filters
    if api_key:
        stmt = stmt.where(APIKey.key == api_key)
    if address:
        stmt = stmt.where(Transaction.address == address)
    # Order by created_at descending
    stmt = stmt.order_by(Transaction.created_at.desc())
    # Pagination
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    results = session.exec(stmt).all()
    transactions: list[TransactionResponse] = []
    for tx, api_key_obj in results:
        transactions.append(
            TransactionResponse(
                id=tx.id,
                api_key=api_key_obj.key,
                address=tx.address,
                extra_data=tx.extra_data,
                created_at=tx.created_at.isoformat(),
            )
        )
    return transactions
