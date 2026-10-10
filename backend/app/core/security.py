"""Password hashing and login tokens.

- Passwords are hashed with argon2 (pwdlib's recommended default). We store only the hash;
  verify_password re-hashes the attempt with the salt inside the stored hash and compares.
- Login tokens are JWTs signed with HS256 and settings.jwt_secret. A JWT is not encrypted,
  only signed: anyone can read it, nobody can change it without the secret. So it carries
  only the user id ("sub"), the expiry ("exp") and the user's token_version ("ver"), nothing sensitive.
- A JWT can't be deleted on the server. To log someone out everywhere (after a password reset),
  we add 1 to users.token_version; every token still carrying the old "ver" is then refused (D-41).
- Forgot-password tokens are random, and only their sha256 is stored (D-39).
"""

import hashlib
import secrets
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


def create_access_token(
    user_id: uuid.UUID | str, *, token_version: int, expires_in: timedelta | None = None
) -> str:
    """Token for this user, valid for settings.jwt_expire_minutes unless expires_in is given (tests)."""
    if expires_in is None:
        expires_in = timedelta(minutes=settings.jwt_expire_minutes)
    claims = {"sub": str(user_id), "exp": datetime.now(UTC) + expires_in, "ver": token_version}
    return jwt.encode(claims, settings.jwt_secret, algorithm=ALGORITHM)


def read_access_token(token: str) -> tuple[uuid.UUID, int] | None:
    """(user id, token version) from a valid token, or None if it is forged, expired or malformed."""
    try:
        # algorithms=[...] is required: it stops an attacker choosing "none" or another algorithm.
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]})
        version = claims["ver"]
        # type() rather than isinstance(): in Python True is an int, and must not pass as version 1.
        if type(version) is not int:
            return None
        return uuid.UUID(claims["sub"]), version
    except (jwt.PyJWTError, KeyError, ValueError, TypeError, AttributeError):
        return None


def new_reset_token() -> str:
    """32 random bytes, URL-safe (43 characters). Guessing one is not a realistic attack."""
    return secrets.token_urlsafe(32)


def hash_reset_token(raw: str) -> str:
    """sha256 hex of a reset token.

    A fast hash is enough here, unlike passwords: the token is 32 random bytes, so there is nothing
    to brute-force. argon2 exists to slow down guessing of low-entropy, human-chosen passwords.
    """
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
