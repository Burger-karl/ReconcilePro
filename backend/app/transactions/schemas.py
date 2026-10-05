import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.allocations.schemas import AllocationRead

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


class TransactionDetail(TransactionRead):
    allocations: list[AllocationRead]


class TransactionList(BaseModel):
    items: list[TransactionRead]
    total: int
