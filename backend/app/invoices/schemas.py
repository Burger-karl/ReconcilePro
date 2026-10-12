"""Request and response bodies for /api/v1/invoices and the public invoice page.

Money fields are StrictInt kobo: 1500.5 or "90000" is rejected with 422 instead of being
silently converted (invariant 1). VAT and total are never accepted from the client.
"""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, StrictInt, field_validator, model_validator

InvoiceStatus = Literal["draft", "sent", "part_paid", "paid", "overdue", "void"]

# ₦10 billion per invoice is far above any SME invoice and catches typos with extra zeros.
MAX_SUBTOTAL_KOBO = 1_000_000_000_000


def _not_blank(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Cannot be blank")
    return value


class InvoiceCreate(BaseModel):
    customer_id: uuid.UUID
    description: str = Field(max_length=500)
    subtotal_kobo: StrictInt = Field(gt=0, le=MAX_SUBTOTAL_KOBO)
    issue_date: date
    due_date: date

    _description = field_validator("description")(_not_blank)

    @model_validator(mode="after")
    def due_after_issue(self) -> "InvoiceCreate":
        if self.due_date < self.issue_date:
            raise ValueError("Due date cannot be before the issue date")
        return self


class InvoiceUpdate(BaseModel):
    """Drafts only. Every field optional; the date order is checked in the service, because
    it may compare a new date with an unchanged one."""

    customer_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=500)
    subtotal_kobo: StrictInt | None = Field(default=None, gt=0, le=MAX_SUBTOTAL_KOBO)
    issue_date: date | None = None
    due_date: date | None = None

    @field_validator("description")
    @classmethod
    def description_not_blank(cls, value: str | None) -> str | None:
        return None if value is None else _not_blank(value)


class VoidRequest(BaseModel):
    reason: str = Field(max_length=500)

    _reason = field_validator("reason")(_not_blank)


class InvoiceRead(BaseModel):
    id: uuid.UUID
    number: str
    reference: str
    customer_id: uuid.UUID
    customer_name: str
    description: str
    status: InvoiceStatus  # DERIVED, see service.derive_status
    issue_date: date
    due_date: date
    sent_at: datetime | None
    subtotal_kobo: int
    vat_kobo: int
    total_kobo: int
    paid_kobo: int
    outstanding_kobo: int
    public_token: str | None
    created_at: datetime


class InvoicePayment(BaseModel):
    """One allocation to this invoice and the bank line it came from. Reversed ones are listed too."""

    id: uuid.UUID  # the allocation id, used to reverse it
    transaction_id: uuid.UUID
    source: str  # bank_statement | paystack
    value_date: date
    narration: str
    amount_kobo: int
    method: str  # auto | suggested | manual
    created_at: datetime
    reversed_at: datetime | None
    reversal_reason: str | None


class InvoiceDetail(InvoiceRead):
    payments: list[InvoicePayment]


class InvoiceList(BaseModel):
    items: list[InvoiceRead]
    total: int


class PublicInvoice(BaseModel):
    """What the customer sees at /i/{token}. Deliberately no ids of any kind."""

    business_name: str
    customer_name: str
    number: str
    reference: str
    description: str
    status: InvoiceStatus
    issue_date: date
    due_date: date
    subtotal_kobo: int
    vat_kobo: int
    total_kobo: int
    paid_kobo: int
    outstanding_kobo: int
