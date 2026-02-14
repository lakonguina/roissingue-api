"""
Transaction model.

Records the outcome of calls to the ``/execute`` endpoint.  Each
transaction is linked to the API key that initiated the call and
captures the status returned by Biconomy, the wallet responsible for
the swap, the full response payload as JSON and the creation
timestamp.
"""

from datetime import datetime

from sqlalchemy import JSON
from sqlmodel import Field, Relationship, SQLModel


class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"
    id: int | None = Field(default=None, primary_key=True)
    api_key_id: int = Field(foreign_key="api_keys.id", index=True)
    status: str
    address: str
    extra_data: dict | None = Field(default=None, sa_type=JSON)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    api_key: "APIKey" = Relationship(back_populates="transactions")
