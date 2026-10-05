import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


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


class ReverseRequest(BaseModel):
    reason: str = Field(max_length=500)

    @field_validator("reason")
    @classmethod
    def reason_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A reason is required")
        return value
