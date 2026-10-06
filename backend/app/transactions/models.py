"""transactions: money that came IN, from a bank statement line or a Paystack payment (docs/ERD.md).

Statement import (feature 4) and the Paystack webhook (feature 6) create these rows.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.time import utc_now


class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"
    __table_args__ = (
        # Invariant 2: the same statement line imported twice is one row (feature 4 uses ON CONFLICT DO NOTHING).
        UniqueConstraint("workspace_id", "fingerprint", name="uq_transactions_workspace_fingerprint"),
        # Invariant 3: the same Paystack payment (webhook retried) is one row. NULLs never clash,
        # so bank lines (no external_reference) are unaffected.
        UniqueConstraint("source", "external_reference", name="uq_transactions_source_external_reference"),
        CheckConstraint("source IN ('bank_statement', 'paystack')", name="ck_transactions_source"),
        # settlement = Paystack paying out to the bank: never matched to invoices (invariant 6).
        CheckConstraint("kind IN ('credit', 'settlement')", name="ck_transactions_kind"),
        CheckConstraint("amount_kobo > 0", name="ck_transactions_amount_positive"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", index=True)
    source: str = Field(max_length=20)
    kind: str = Field(default="credit", max_length=20)
    value_date: date
    amount_kobo: int = Field(sa_type=BigInteger)
    narration: str = Field(sa_type=Text)  # exactly as the bank wrote it
    bank_reference: str | None = Field(default=None, max_length=100)
    balance_kobo: int | None = Field(default=None, sa_type=BigInteger)  # running balance, if the bank gives one
    payer_name: str | None = Field(default=None, max_length=200)
    # Paystack reference. TEXT, not VARCHAR(100): a merchant can choose any reference, and a too-long one would
    # fail the insert, answer 500 and make Paystack retry forever without the money ever being recorded.
    external_reference: str | None = Field(default=None, sa_type=Text)
    fingerprint: str = Field(max_length=64)  # sha256 hex, see docs/DECISIONS.md D-03
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
