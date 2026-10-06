"""Calls to Paystack's API. Kept apart from service.py so tests can swap verify_transaction for a fake.

Docs: https://paystack.com/docs/api/transaction/#verify
"""

import uuid
from datetime import UTC, datetime
from urllib.parse import quote

import httpx

from app.core.config import settings
from app.paystack.schemas import VerifiedCharge

BASE_URL = "https://api.paystack.co"
# Leave Paystack's webhook request time to finish the database work after we have verified.
TIMEOUT_SECONDS = 10


class PaystackUnavailable(Exception):
    """Paystack couldn't be asked, or its answer can't be trusted yet (network error, 5xx, 429, unreadable body).

    The webhook answers 502 so Paystack retries (D-32, D-35); the pay button shows "try again".
    """


def verify_transaction(reference: str) -> VerifiedCharge | None:
    """Ask Paystack what really happened for this reference. None if Paystack has never heard of it."""
    try:
        response = httpx.get(
            f"{BASE_URL}/transaction/verify/{quote(reference, safe='')}",
            headers={"Authorization": f"Bearer {settings.paystack_secret_key}"},
            timeout=TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as error:
        raise PaystackUnavailable(str(error)) from error
    if response.status_code in (400, 404):
        return None  # Paystack has never heard of this reference, e.g. a forged event
    if response.status_code != 200:
        # Anything else (5xx, 429 rate limit, 401/403 bad key, 408 timeout) says nothing about the payment.
        # Answering "ignored" would make Paystack stop retrying and lose a real payment, so retry later.
        raise PaystackUnavailable(f"Paystack answered {response.status_code}")

    try:
        return _charge_from(response.json()["data"])
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        # A 200 we can't read (HTML error page, missing field, amount that isn't whole kobo). Nothing has been
        # written yet, so asking Paystack to retry is safe; recording a half-understood payment is not.
        # (pydantic's ValidationError and json's JSONDecodeError are both ValueErrors.)
        raise PaystackUnavailable(f"Unreadable answer from Paystack: {error!r}") from error


def _charge_from(data: dict) -> VerifiedCharge:
    customer = data.get("customer") or {}
    full_name = " ".join(part for part in (customer.get("first_name"), customer.get("last_name")) if part)
    # Paystack's JSON has used both spellings; take whichever is present.
    paid_at = datetime.fromisoformat(data.get("paid_at") or data["paidAt"])
    if paid_at.tzinfo is None:
        # Paystack sends UTC ("...Z"). If a time ever arrives without a zone, say so explicitly; otherwise
        # astimezone() would treat it as the server's local time and could shift the Lagos date (D-13).
        paid_at = paid_at.replace(tzinfo=UTC)
    return VerifiedCharge(
        reference=data["reference"],
        status=data["status"],
        currency=data["currency"],
        amount_kobo=data["amount"],
        paid_at=paid_at,
        invoice_id=_invoice_id(data.get("metadata")),
        payer_name=full_name or customer.get("email"),
        channel=data.get("channel"),
    )


def initialize_transaction(*, email: str, amount_kobo: int, invoice_id: uuid.UUID, callback_url: str) -> str:
    """Start a Paystack checkout and return the URL to send the customer to.

    Docs: https://paystack.com/docs/api/transaction/#initialize
    Paystack makes up the payment reference. metadata.invoice_id comes back to us through verify-transaction,
    which is how the webhook knows which invoice the money is for.
    """
    try:
        response = httpx.post(
            f"{BASE_URL}/transaction/initialize",
            headers={"Authorization": f"Bearer {settings.paystack_secret_key}"},
            json={
                "email": email,
                "amount": amount_kobo,  # Paystack expects kobo for NGN
                "currency": "NGN",
                "callback_url": callback_url,
                "metadata": {"invoice_id": str(invoice_id)},
            },
            timeout=TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as error:
        raise PaystackUnavailable(str(error)) from error
    try:
        body = response.json()
        if response.status_code != 200 or not body.get("status"):
            # Any refusal (bad key, bad email) means the customer can't pay right now; the router answers 502.
            raise PaystackUnavailable(f"Paystack answered {response.status_code}: {body.get('message', '')}")
        return body["data"]["authorization_url"]
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        # Not JSON, or JSON without the checkout URL: same as Paystack being down for the customer.
        raise PaystackUnavailable(f"Unreadable answer from Paystack (HTTP {response.status_code})") from error


def _invoice_id(metadata: object) -> uuid.UUID | None:
    # Metadata comes back exactly as it was sent: our dict, or "" / null for payments we didn't start.
    if not isinstance(metadata, dict):
        return None
    try:
        return uuid.UUID(str(metadata.get("invoice_id")))
    except ValueError:
        return None
