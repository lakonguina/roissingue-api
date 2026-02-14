"""
User model.

Defines the user table used for authentication and account management.
Each user is uniquely identified by their email address.  Passwords
are stored as salted SHA‑256 hashes.  The ``is_verified`` flag
indicates whether the user has confirmed their email address via the
verification workflow.  ``created_at`` records when the account was
created.
"""

from datetime import datetime

from sqlmodel import Field, Relationship, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    verification_tokens: list["VerificationToken"] = Relationship(back_populates="user")
    api_keys: list["APIKey"] = Relationship(back_populates="user")
