"""Checking a "Sign in with Google" ID token. The only file that talks to Google (D-37).

How the flow works:
1. The browser shows Google's sign-in button. Google signs the person in and gives the browser an
   ID token: a JWT signed by Google with RS256 (Google's private key; anyone can check it with the
   public keys Google publishes).
2. The frontend posts that token to us. We check it here and then issue our OWN login token.

Each check stops a different attack (Google's guide: developers.google.com/identity/gsi/web/guides/verify-google-id-token):
- signature (Google's public key, RS256 only) -> a token someone forged
- aud == our client id                       -> a real Google token issued to ANOTHER app, replayed against us
- iss is Google                              -> a token from somebody else's identity provider
- exp in the future                          -> an old token being reused
- email_verified is True                     -> someone claiming an email address they never proved they own
"""

from dataclasses import dataclass

import jwt
from jwt import PyJWKClient

from app.core.config import settings

GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
# A tuple, not a string: jwt.decode checks `iss in issuer`, and on a string that would be a substring test.
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")

# Downloads Google's public keys and caches them; Google rotates them, and a token says which one
# signed it in its "kid" header.
_jwks_client = PyJWKClient(GOOGLE_CERTS_URL, cache_keys=True, timeout=10)


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str  # Google's permanent user id. Never reused, never changes.
    email: str  # lower-case
    # True when Google, not just the person, controls this address (see is_google_authoritative).
    google_is_authoritative: bool


class InvalidGoogleCredential(Exception):
    pass


class GoogleNotConfigured(Exception):
    pass


class GoogleUnavailable(Exception):
    pass


def _google_public_key(credential: str):
    """The public key that signed this token, from Google's published keys. Tests replace this."""
    try:
        return _jwks_client.get_signing_key_from_jwt(credential).key
    except jwt.PyJWKClientConnectionError as error:
        raise GoogleUnavailable from error
    except jwt.PyJWTError as error:
        # Unknown "kid", malformed header, etc.
        raise InvalidGoogleCredential from error


def is_google_authoritative(email: str, claims: dict) -> bool:
    """Whether Google itself owns this email address, per Google's guide.

    True for @gmail.com, and for Google Workspace accounts ("hd" = the company's domain, run by its
    Google admin). A personal Google account can also carry a verified non-Gmail address; Google
    proved the person received an email there once, but Google doesn't own that address, so we
    don't use it to take over an existing Reconcile account (D-38).
    """
    return email.endswith("@gmail.com") or (claims.get("email_verified") is True and bool(claims.get("hd")))


def verify_google_credential(credential: str) -> GoogleIdentity:
    if not settings.google_client_id:
        raise GoogleNotConfigured

    key = _google_public_key(credential)
    try:
        claims = jwt.decode(
            credential,
            key,
            # Only RS256. Allowing HS256 here would let an attacker sign with Google's PUBLIC key as an
            # HMAC secret (the "algorithm confusion" attack).
            algorithms=["RS256"],
            audience=settings.google_client_id,
            issuer=GOOGLE_ISSUERS,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.PyJWTError as error:
        raise InvalidGoogleCredential from error

    sub, email = claims.get("sub"), claims.get("email")
    # `is True`: a string "true" or a missing claim does not count as verified.
    if claims.get("email_verified") is not True or not isinstance(sub, str) or not isinstance(email, str):
        raise InvalidGoogleCredential
    if not sub or not email or len(sub) > 255 or len(email) > 320:
        raise InvalidGoogleCredential

    email = email.strip().lower()
    return GoogleIdentity(sub=sub, email=email, google_is_authoritative=is_google_authoritative(email, claims))
