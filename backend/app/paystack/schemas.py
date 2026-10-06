"""Paystack shapes: what verify-transaction tells us, and what the webhook answers."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, StrictInt


class VerifiedCharge(BaseModel):
    """One payment as Paystack's verify-transaction endpoint reports it. The only Paystack data we trust (D-30)."""

    reference: str
    status: str  # "success", "failed", "abandoned", ...
    currency: str
    # Paystack already sends NGN amounts in kobo, as an integer (invariant 1). StrictInt refuses 107500.5,
    # "107500" and True instead of quietly converting them: a malformed amount must never become money.
    amount_kobo: StrictInt
    paid_at: datetime
    invoice_id: uuid.UUID | None  # metadata.invoice_id, set when the payment was started from our invoice page
    payer_name: str | None
    channel: str | None  # "card", "bank_transfer", "ussd", ...


class PaymentLink(BaseModel):
    """Answer to the public "Pay with Paystack" button. Deliberately nothing but the checkout URL."""

    authorization_url: str


class WebhookResult(BaseModel):
    status: Literal["allocated", "unallocated", "duplicate", "ignored"]
