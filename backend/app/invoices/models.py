"""invoices table (docs/ERD.md).

Only draft / sent / void are stored (invariant 5). Paid, part paid and overdue are worked out
from allocations and the due date every time an invoice is read; see service.derive_status().
"""

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.time import utc_now


class Invoice(SQLModel, table=True):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("workspace_id", "number", name="uq_invoices_workspace_number"),
        UniqueConstraint("workspace_id", "reference", name="uq_invoices_workspace_reference"),
        CheckConstraint("status IN ('draft', 'sent', 'void')", name="ck_invoices_status"),
        # Money rules enforced by the database too, not only by Python (invariant 1).
        CheckConstraint("subtotal_kobo > 0", name="ck_invoices_subtotal_positive"),
        CheckConstraint("vat_kobo >= 0", name="ck_invoices_vat_not_negative"),
        CheckConstraint("total_kobo = subtotal_kobo + vat_kobo", name="ck_invoices_total_adds_up"),
        CheckConstraint("due_date >= issue_date", name="ck_invoices_due_after_issue"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", index=True)
    customer_id: uuid.UUID = Field(foreign_key="customers.id", index=True)
    number: str = Field(max_length=20)  # INV-0001, counts up per workspace
    reference: str = Field(max_length=20)  # RCN-7K4Q2M, what the payer quotes on the transfer
    description: str = Field(max_length=500)
    status: str = Field(default="draft", max_length=10)
    issue_date: date
    due_date: date
    sent_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    # BIGINT kobo (invariant 1). A Python int has no size limit, BIGINT holds up to ~₦92 quadrillion.
    subtotal_kobo: int = Field(sa_type=BigInteger)
    vat_kobo: int = Field(sa_type=BigInteger)
    total_kobo: int = Field(sa_type=BigInteger)
    # Secret for the public /i/{token} page. Null until the invoice is sent.
    public_token: str | None = Field(default=None, max_length=64, unique=True)
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
