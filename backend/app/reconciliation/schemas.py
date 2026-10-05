import uuid
from typing import Literal

from pydantic import BaseModel, Field, StrictInt

from app.transactions.schemas import TransactionRead


class BreakdownRead(BaseModel):
    amount: int  # out of 50
    name: int  # out of 30
    date: int  # out of 20


class CandidateRead(BaseModel):
    invoice_id: uuid.UUID
    invoice_number: str
    customer_name: str
    status: str
    outstanding_kobo: int
    score: int  # 0-100
    breakdown: BreakdownRead
    reference_match: bool
    reasons: list[str]


class QueueItem(BaseModel):
    transaction: TransactionRead
    # Set when the matcher is confident (score >= 70 with a clear lead, or an exact reference).
    suggested_invoice_id: uuid.UUID | None
    candidates: list[CandidateRead]


class Queue(BaseModel):
    items: list[QueueItem]
    total: int


class AllocateRequest(BaseModel):
    transaction_id: uuid.UUID
    invoice_id: uuid.UUID
    amount_kobo: StrictInt = Field(gt=0)  # invariant 1: whole kobo, no floats
    # "auto" is reserved for the system; a person either accepted a suggestion or chose themselves.
    method: Literal["suggested", "manual"]


class RejectRequest(BaseModel):
    transaction_id: uuid.UUID
    invoice_id: uuid.UUID


class AutoMatchResult(BaseModel):
    auto_allocated: int
