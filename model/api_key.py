"""
API key model.

Stores opaque API keys associated with users.  Each key grants access
to the main API routes.  Keys can be revoked by deleting the record.
``created_at`` records when the key was generated.
"""

from datetime import datetime

from sqlmodel import Field, Relationship, SQLModel


class APIKey(SQLModel, table=True):
    __tablename__ = "api_keys"
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    key: str = Field(unique=True, index=True)
    name: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user: "User" = Relationship(back_populates="api_keys")
