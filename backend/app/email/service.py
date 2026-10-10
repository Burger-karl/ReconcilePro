"""send_email(): the one way the backend sends email, through Resend (resend.com/docs/api-reference/emails/send-email).

Callers run it as a FastAPI background task, after the response has gone out. That keeps slow email
off the request, and for forgot-password it means the answer takes the same time whether or not
the email has an account (D-39).

Without RESEND_API_KEY nothing is sent. In development the email is written to the log instead, so a
developer can still click the reset link; in production only "not sent" is logged. A failure is logged, never raised: the HTTP response has
already been sent, so there is nobody to raise it to.
"""

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
TIMEOUT_SECONDS = 10


def send_email(*, to: str, subject: str, text: str) -> None:
    if not settings.resend_api_key:
        if settings.environment == "development":
            logger.warning("RESEND_API_KEY not set; email NOT sent.\nTo: %s\nSubject: %s\n\n%s", to, subject, text)
        else:
            # Never the body in production: server logs are read by more people (and tools) than the
            # inbox, and the body may hold a working password reset link (D-45).
            logger.error("RESEND_API_KEY not set; email to %s (%r) NOT sent", to, subject)
        return
    try:
        response = httpx.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={"from": settings.email_from, "to": [to], "subject": subject, "text": text},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        # Log who and why, never the body: it may hold a reset link.
        logger.error("Email to %s (%r) failed: %r", to, subject, error)
