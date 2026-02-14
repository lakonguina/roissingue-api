"""
Authentication routes.

This router implements endpoints for user registration, login,
email verification and password reset.  It uses JWT tokens for
authentication and relies on the database models defined in
``roissingue_api.model``.  Emails are delivered via the
``send_email`` service.  Most responses return basic messages or
tokens; the actual website will use these endpoints via internal
functions rather than exposing them directly to end users.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import Session, select

from database import get_session
from model.user import User
from model.verification_token import VerificationToken
from services.email import send_email
from services.security import create_access_token, hash_password, verify_password

auth_router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_verified: bool


@auth_router.post("/register", response_model=dict)
def register(
    payload: RegisterRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> dict:
    """Create a new user and send an email verification link.

    Users are created with ``is_verified`` set to False.  A
    verification token is generated and emailed to the user.  If the
    email address is already registered a 400 error is raised.
    """
    # Check if email already exists
    statement = select(User).where(User.email == payload.email)
    existing = session.exec(statement).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )
    # Hash the password and create the user
    user = User(email=payload.email, hashed_password=hash_password(payload.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    # Generate verification token
    token_str = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(days=1)
    vtoken = VerificationToken(
        user_id=user.id, token=token_str, type="verification", expires_at=expires
    )
    session.add(vtoken)
    session.commit()
    # Send verification email asynchronously
    subject = "Verify your Roissingue account"
    link = f"http://localhost:8000/auth/verify?token={token_str}"
    body = (
        f"Hello,\n\n"
        f"Thank you for registering with Roissingue. Please verify your account by clicking the link below:\n"
        f"{link}\n\n"
        "If you did not sign up for this service, please ignore this email.\n"
    )
    background_tasks.add_task(
        send_email, to_email=user.email, subject=subject, body=body
    )
    return {
        "message": "Registration successful. Please check your email to verify your account."
    }


@auth_router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    session: Session = Depends(get_session),
) -> TokenResponse:
    """Authenticate a user and return a bearer token.

    The returned token contains the user ID in the ``sub`` claim and
    a ``verified`` claim indicating whether the user's email has
    been confirmed.  If authentication fails a 401 error is
    returned.
    """
    statement = select(User).where(User.email == payload.email)
    user = session.exec(statement).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    token = create_access_token(
        str(user.id), additional_claims={"verified": user.is_verified}
    )
    return TokenResponse(access_token=token, is_verified=user.is_verified)


@auth_router.get("/verify", response_model=dict)
def verify_email(token: str, session: Session = Depends(get_session)) -> dict:
    """Verify a user's email address using a token.

    If the token is valid and not expired the user's ``is_verified``
    flag is set to True and the token record is removed.  If the
    token is invalid or expired a 400 error is returned.
    """
    statement = select(VerificationToken).where(VerificationToken.token == token)
    vtoken = session.exec(statement).first()
    if not vtoken or vtoken.type != "verification":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification token"
        )
    if vtoken.expires_at < datetime.utcnow():
        session.delete(vtoken)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token has expired",
        )
    user = session.get(User, vtoken.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification token"
        )
    user.is_verified = True
    session.delete(vtoken)
    session.add(user)
    session.commit()
    return {"message": "Email successfully verified."}


class ResetRequest(BaseModel):
    email: EmailStr


@auth_router.post("/request-password-reset", response_model=dict)
def request_password_reset(
    payload: ResetRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> dict:
    """Initiate a password reset by sending a reset link via email.

    If the email exists a reset token is generated and emailed.  The
    response always indicates success to prevent user enumeration.
    """
    statement = select(User).where(User.email == payload.email)
    user = session.exec(statement).first()
    if user:
        # Remove any existing reset tokens for the user
        stmt = select(VerificationToken).where(
            VerificationToken.user_id == user.id, VerificationToken.type == "reset"
        )
        for rt in session.exec(stmt).all():
            session.delete(rt)
        # Generate new token
        token_str = secrets.token_urlsafe(32)
        expires = datetime.utcnow() + timedelta(hours=1)
        vtoken = VerificationToken(
            user_id=user.id, token=token_str, type="reset", expires_at=expires
        )
        session.add(vtoken)
        session.commit()
        # Send reset email
        subject = "Reset your Roissingue password"
        link = f"http://localhost:8000/auth/reset-password?token={token_str}"
        body = (
            f"Hello,\n\n"
            "You recently requested to reset your password. Use the link below to choose a new password:\n"
            f"{link}\n\n"
            "If you did not request a password reset please ignore this email.\n"
        )
        background_tasks.add_task(
            send_email, to_email=user.email, subject=subject, body=body
        )
    # Always return success message
    return {
        "message": "If an account with that email exists, a password reset link has been sent."
    }


class ResetPasswordPayload(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


@auth_router.post("/reset-password", response_model=dict)
def reset_password(
    payload: ResetPasswordPayload,
    session: Session = Depends(get_session),
) -> dict:
    """Reset a user's password using a reset token.

    Validates the token, updates the user's password and deletes the
    token.  Returns a simple success message or 400 if the token is
    invalid or expired.
    """
    statement = select(VerificationToken).where(
        VerificationToken.token == payload.token
    )
    vtoken = session.exec(statement).first()
    if not vtoken or vtoken.type != "reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token"
        )
    if vtoken.expires_at < datetime.utcnow():
        session.delete(vtoken)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Reset token has expired"
        )
    user = session.get(User, vtoken.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token"
        )
    user.hashed_password = hash_password(payload.new_password)
    session.delete(vtoken)
    session.add(user)
    session.commit()
    return {"message": "Password has been reset successfully."}
