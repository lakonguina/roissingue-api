"""
Security utilities.

This module centralises the helper functions used for password
hashing and JSON Web Token generation/validation.  Passwords are
salted and hashed using SHA‑256 to avoid storing plain text
passwords.  Tokens are generated using the PyJWT library and signed
with the application's secret key.  The ``create_access_token``
function produces a short‑lived token that encodes the user ID and
verification status.  ``decode_access_token`` is used internally by
authentication dependencies to retrieve the claims from a token.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import jwt  # type: ignore

from settings import settings


def hash_password(password: str) -> str:
    """Hash a password with a random salt using SHA‑256.

    Returns a string containing the hex encoded salt and hash separated
    by a colon.  The salt is 16 hexadecimal characters long (8 bytes).

    :param password: the plain text password
    :return: salted and hashed password string
    """
    salt = secrets.token_hex(8)
    hash_obj = hashlib.sha256((salt + password).encode())
    return f"{salt}:{hash_obj.hexdigest()}"


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against a salted SHA‑256 hash.

    The stored hash is expected to be in the format ``salt:hash``.

    :param password: candidate plain text password
    :param hashed_password: stored salted hash
    :return: True if the password matches the hash, False otherwise
    """
    try:
        salt, hashed = hashed_password.split(":", 1)
    except ValueError:
        return False
    computed = hashlib.sha256((salt + password).encode()).hexdigest()
    return secrets.compare_digest(computed, hashed)


def create_access_token(
    subject: str,
    *,
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate a signed JSON Web Token for the given subject.

    The token encodes the ``sub`` claim with the provided subject and
    includes an expiry timestamp.  Additional claims can be supplied
    via the ``additional_claims`` parameter.  Tokens are signed with
    the secret key defined in ``settings.secret_key``.

    :param subject: identifier for the token subject (typically the user ID)
    :param expires_delta: relative expiry duration; defaults to 1 day
    :param additional_claims: extra claims to embed in the payload
    :return: encoded JWT as a string
    """
    to_encode: Dict[str, Any] = {"sub": str(subject)}
    if additional_claims:
        to_encode.update(additional_claims)
    expire = datetime.utcnow() + (expires_delta or timedelta(days=1))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm="HS256")
    # The PyJWT library returns a string when algorithm != None
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JSON Web Token.

    :param token: JWT string to decode
    :raises jwt.ExpiredSignatureError: if the token has expired
    :raises jwt.InvalidTokenError: if the token is invalid
    :return: payload dictionary
    """
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    return payload
