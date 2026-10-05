"""Application settings, read from environment variables (or backend/.env in local dev).

pydantic-settings validates types at startup, so a missing DATABASE_URL fails fast
instead of failing on the first request.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # psycopg 3 driver, e.g. postgresql+psycopg://reconcile:reconcile@localhost:5433/reconcile
    database_url: str = "postgresql+psycopg://reconcile:reconcile@localhost:5433/reconcile"
    # Separate database for pytest, so tests never touch dev data.
    test_database_url: str = "postgresql+psycopg://reconcile:reconcile@localhost:5433/reconcile_test"

    # Used to sign login tokens. The default only exists so local dev starts; Render sets a real one.
    # HS256 needs a key of at least 32 bytes (RFC 7518). Generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"
    jwt_secret: str = "dev-only-insecure-secret-change-me-in-production"
    jwt_expire_minutes: int = 60 * 24

    paystack_secret_key: str = ""
    resend_api_key: str = ""

    # The Next.js app; allowed by CORS and used to build public invoice links.
    frontend_url: str = "http://localhost:3000"


settings = Settings()
