"""Application settings, read from environment variables (or backend/.env in local dev).

pydantic-settings validates types at startup, so a missing DATABASE_URL fails fast
instead of failing on the first request.
"""

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Only for local development. Production refuses to start with it (D-43).
DEV_JWT_SECRET = "dev-only-insecure-secret-change-me-in-production"
# HS256 needs a key of at least 32 bytes (RFC 7518).
MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "production" unless told otherwise: forgetting to set ENVIRONMENT on a server must not switch the
    # safety checks off. docker-compose and the tests set ENVIRONMENT=development (D-43).
    environment: Literal["development", "production"] = "production"

    # psycopg 3 driver, e.g. postgresql+psycopg://reconcile:reconcile@localhost:5433/reconcile
    database_url: str = "postgresql+psycopg://reconcile:reconcile@localhost:5433/reconcile"
    # Separate database for pytest, so tests never touch dev data.
    test_database_url: str = "postgresql+psycopg://reconcile:reconcile@localhost:5433/reconcile_test"

    # Used to sign login tokens. The default only exists so local dev starts; Render sets a real one.
    # Generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"
    jwt_secret: str = DEV_JWT_SECRET
    jwt_expire_minutes: int = 60 * 24

    paystack_secret_key: str = ""
    # Empty in local dev: emails are then written to the log instead of sent (app/email/service.py).
    resend_api_key: str = ""
    email_from: str = "Reconcile <onboarding@resend.dev>"

    # OAuth client id from Google Cloud Console. Empty = Google sign-in is switched off (503).
    google_client_id: str = ""
    # How long a forgot-password link works (D-39).
    password_reset_minutes: int = 30

    # The Next.js app; allowed by CORS and used to build public invoice links.
    frontend_url: str = "http://localhost:3000"

    # How many proxies the host puts in front of the API, each appending to X-Forwarded-For. 0 = none (local),
    # so the header is ignored: anyone can send it. Set on Render after checking the real address (D-66).
    trusted_proxy_hops: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def production_needs_a_real_jwt_secret(self) -> "Settings":
        """Anyone who knows the signing secret can forge a login token for any user. The development
        default is in this public repository, so a server must never run with it (D-43)."""
        if self.environment == "production" and (
            self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret.encode()) < MIN_JWT_SECRET_LENGTH
        ):
            raise ValueError(
                "JWT_SECRET must be set to a random value of at least 32 bytes in production "
                "(or set ENVIRONMENT=development for local work)"
            )
        return self


settings = Settings()
