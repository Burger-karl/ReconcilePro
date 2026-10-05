"""payment_allocations: how much of which bank credit paid which invoice (docs/ERD.md).

Only allocations/service.py inserts rows here (invariant 4). Rows are never deleted: a mistake is
undone by setting reversed_at (invariant 7), so the history of what happened stays visible.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime
from sqlmodel import Field, SQLModel

from app.core.time import utc_now


class PaymentAllocation(SQLModel, table=True):
    __tablename__ = "payment_allocations"
    __table_args__ = (
        CheckConstraint("amount_kobo > 0", name="ck_allocations_amount_positive"),
        CheckConstraint("method IN ('auto', 'suggested', 'manual')", name="ck_allocations_method"),
        # A reversal is all-or-nothing: when, who and why are set together (who may be null = system).
        CheckConstraint(
            "(reversed_at IS NULL) = (reversal_reason IS NULL)", name="ck_allocations_reversal_complete"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", index=True)
    transaction_id: uuid.UUID = Field(foreign_key="transactions.id", index=True)
    invoice_id: uuid.UUID = Field(foreign_key="invoices.id", index=True)
    amount_kobo: int = Field(sa_type=BigInteger)
    # auto = exact reference match, suggested = accountant accepted a suggestion, manual = accountant chose.
    method: str = Field(max_length=20)
    created_by: uuid.UUID | None = Field(default=None, foreign_key="users.id")  # null = the system
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    reversed_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    reversed_by: uuid.UUID | None = Field(default=None, foreign_key="users.id")
    reversal_reason: str | None = Field(default=None, max_length=500)
