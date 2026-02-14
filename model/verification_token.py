"""
Verification token model.

Stores time limited tokens used for account verification and password
reset.  Each token is linked to a user and has an expiration time.
Tokens are invalidated by deleting the record once consumed.  The
``type`` field distinguishes between verification and password reset
flows.
"""

from datetime import datetime, timedelta

from sqlmodel import Field, Relationship, SQLModel


class VerificationToken(SQLModel, table=True):
    __tablename__ = "verification_tokens"
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    token: str = Field(index=True, unique=True)
    type: str = Field(default="verification")  # "verification" or "reset"
    expires_at: datetime = Field()
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user: "User" = Relationship(back_populates="verification_tokens")
