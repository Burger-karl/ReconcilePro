import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

AllocationState = Literal["unallocated", "part", "allocated"]


class TransactionRead(BaseModel):
    id: uuid.UUID
    source: str
    kind: str
    value_date: date
    amount_kobo: int
    allocated_kobo: int  # sum of non-reversed allocations
    unallocated_kobo: int  # what is still free to allocate
    narration: str
    bank_reference: str | None
    balance_kobo: int | None
    payer_name: str | None
    created_at: datetime


class AllocationRead(BaseModel):
    """One line of a bank credit's allocation history, reversed ones included."""

    id: uuid.UUID
    invoice_id: uuid.UUID
    invoice_number: str
    amount_kobo: int
    method: str
    created_at: datetime
    reversed_at: datetime | None
    reversal_reason: str | None


class TransactionDetail(TransactionRead):
    allocations: list[AllocationRead]


class TransactionList(BaseModel):
    items: list[TransactionRead]
    total: int
