"""Password hashing and login tokens.

- Passwords are hashed with argon2 (pwdlib's recommended default). We store only the hash;
  verify_password re-hashes the attempt with the salt inside the stored hash and compares.
- Login tokens are JWTs signed with HS256 and settings.jwt_secret. A JWT is not encrypted,
  only signed: anyone can read it, nobody can change it without the secret. So it carries
  only the user id ("sub") and the expiry ("exp"), nothing sensitive.
"""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

ALGORITHM = "HS256"

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def create_access_token(user_id: uuid.UUID | str, expires_in: timedelta | None = None) -> str:
    """Token for this user, valid for settings.jwt_expire_minutes unless expires_in is given (tests)."""
    if expires_in is None:
        expires_in = timedelta(minutes=settings.jwt_expire_minutes)
    claims = {"sub": str(user_id), "exp": datetime.now(UTC) + expires_in}
    return jwt.encode(claims, settings.jwt_secret, algorithm=ALGORITHM)


def read_access_token(token: str) -> uuid.UUID | None:
    """The user id inside a valid token, or None if the token is forged, expired or malformed."""
    try:
        # algorithms=[...] is required: it stops an attacker choosing "none" or another algorithm.
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return uuid.UUID(claims["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
