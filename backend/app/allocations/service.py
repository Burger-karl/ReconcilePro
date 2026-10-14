"""allocate() and reverse(): the ONLY code that writes payment_allocations (invariant 4).

How allocate() stays correct when two requests arrive at the same moment
--------------------------------------------------------------------------
1. Lock the bank line, then the invoice, with SELECT ... FOR UPDATE. A second request that wants
   either row waits here until the first one commits or rolls back.
2. Only AFTER holding both locks, add up the existing (non-reversed) allocations. PostgreSQL's default
   isolation (READ COMMITTED) gives each statement the latest committed data, so the waiting request
   sees the first one's allocation when it finally gets the lock.
3. Refuse if the bank line OR the invoice would go over its amount.

Locks are always taken in the same order (bank line first, then invoice). If one request locked the
invoice first and another the bank line first, each could wait for the other forever (a deadlock).

Neither function commits. The caller commits once, so an allocation and whatever caused it (a
Paystack transaction insert, an audit row) are saved together or not at all (invariant 3).
"""

import uuid
from datetime import date

from sqlalchemy import BigInteger, cast, func
from sqlmodel import Session, select

from app.allocations.models import PaymentAllocation
from app.allocations.schemas import AllocationRead
from app.audit.service import record
from app.core.time import utc_now
from app.invoices.models import Invoice
from app.transactions.models import Transaction

METHODS = ("auto", "suggested", "manual")


class AllocationError(Exception):
    """Base class; the message is safe to show to the user."""


class AllocationNotFound(AllocationError):
    """The bank line, invoice or allocation doesn't exist in this workspace."""


class AllocationNotAllowed(AllocationError):
    """The request breaks a rule (bad amount, settlement line, draft/void invoice, ...)."""


class AllocationAlreadyReversed(AllocationError):
    pass


class OverAllocated(AllocationError):
    """More than is left on the bank line or the invoice. `available_kobo` is what IS left."""

    def __init__(self, side: str, available_kobo: int) -> None:
        self.side = side  # "transaction" or "invoice"
        self.available_kobo = available_kobo
        what = "bank line" if side == "transaction" else "invoice"
        super().__init__(f"Amount is more than is left on the {what}")


# --- totals ------------------------------------------------------------------------------------------


def _sum_amount():
    # SUM() of a BIGINT column comes back from PostgreSQL as NUMERIC, which Python reads as Decimal.
    # Casting back to BIGINT keeps money as plain ints (invariant 1). COALESCE turns "no rows" into 0.
    return cast(func.coalesce(func.sum(PaymentAllocation.amount_kobo), 0), BigInteger)


def invoice_paid_totals(
    session: Session, workspace_id: uuid.UUID, invoice_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """Kobo paid per invoice: sum of non-reversed allocations. Invoices with nothing paid are absent.

    Filtered by workspace as well as by id (invariant 8): even if a caller passed another workspace's
    invoice id by mistake, it would get nothing back.
    """
    if not invoice_ids:
        return {}
    rows = session.exec(
        select(PaymentAllocation.invoice_id, _sum_amount())
        .where(
            PaymentAllocation.workspace_id == workspace_id,
            PaymentAllocation.invoice_id.in_(invoice_ids),
            PaymentAllocation.reversed_at.is_(None),
        )
        .group_by(PaymentAllocation.invoice_id)
    ).all()
    return {invoice_id: total for invoice_id, total in rows}


def last_payment_date(session: Session, workspace_id: uuid.UUID, invoice_id: uuid.UUID) -> date | None:
    """Value date of the latest NON-reversed payment to this invoice (the day the money arrived), or None.

    Shown on the public page as "payment received on …" (D-61). A reversed allocation was never really a
    payment for this invoice, so it is ignored, like in invoice_paid_totals.
    """
    return session.exec(
        select(func.max(Transaction.value_date))
        .join(PaymentAllocation, PaymentAllocation.transaction_id == Transaction.id)
        .where(
            PaymentAllocation.workspace_id == workspace_id,
            PaymentAllocation.invoice_id == invoice_id,
            PaymentAllocation.reversed_at.is_(None),
        )
    ).one()


def allocated_totals(
    session: Session, workspace_id: uuid.UUID, transaction_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """Kobo already allocated per bank line: sum of non-reversed allocations, within one workspace."""
    if not transaction_ids:
        return {}
    rows = session.exec(
        select(PaymentAllocation.transaction_id, _sum_amount())
        .where(
            PaymentAllocation.workspace_id == workspace_id,
            PaymentAllocation.transaction_id.in_(transaction_ids),
            PaymentAllocation.reversed_at.is_(None),
        )
        .group_by(PaymentAllocation.transaction_id)
    ).all()
    return {transaction_id: total for transaction_id, total in rows}


def invoice_payments(
    session: Session, workspace_id: uuid.UUID, invoice_id: uuid.UUID
) -> list[tuple[PaymentAllocation, Transaction]]:
    """Every allocation to one invoice, reversed ones included, oldest first, with the bank line it came from.

    Read-only. Reversed rows are kept because the history must show what was undone and why (invariant 7).
    """
    return list(
        session.exec(
            select(PaymentAllocation, Transaction)
            .join(Transaction, Transaction.id == PaymentAllocation.transaction_id)
            .where(
                PaymentAllocation.workspace_id == workspace_id,
                PaymentAllocation.invoice_id == invoice_id,
                Transaction.workspace_id == workspace_id,
            )
            .order_by(PaymentAllocation.created_at)
        ).all()
    )


# --- allocate -----------------------------------------------------------------------------------------


def allocate(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    transaction_id: uuid.UUID,
    invoice_id: uuid.UUID,
    amount_kobo: int,
    method: str,
    actor_user_id: uuid.UUID | None,
) -> PaymentAllocation:
    """Put `amount_kobo` of a bank credit against an invoice. Raises an AllocationError subclass if not allowed.

    actor_user_id is None when the system does it (auto-match, Paystack webhook). Does NOT commit.
    """
    # `type(...) is int` rather than isinstance: True/False are ints in Python and must be rejected too.
    if type(amount_kobo) is not int or amount_kobo <= 0:
        raise AllocationNotAllowed("Amount must be a positive whole number of kobo")
    if method not in METHODS:
        raise AllocationNotAllowed(f"Unknown allocation method {method!r}")

    # Step 1: lock the bank line, THEN the invoice (always this order, see module docstring).
    # populate_existing: if these rows are already loaded in this session, refresh them from the
    # database after the lock, so we never check rules against stale values.
    transaction = session.exec(
        select(Transaction)
        .where(Transaction.id == transaction_id, Transaction.workspace_id == workspace_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if transaction is None:
        raise AllocationNotFound("Bank line not found")
    invoice = session.exec(
        select(Invoice)
        .where(Invoice.id == invoice_id, Invoice.workspace_id == workspace_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if invoice is None:
        raise AllocationNotFound("Invoice not found")

    if transaction.kind != "credit":
        raise AllocationNotAllowed("Paystack settlement lines are never matched to invoices")
    # Stored status "sent" covers what the user sees as sent, part paid and overdue.
    if invoice.status != "sent":
        raise AllocationNotAllowed(f"Only sent invoices can receive payments; this one is {invoice.status}")

    # Step 2: re-sum existing allocations now that we hold the locks.
    left_on_transaction = transaction.amount_kobo - allocated_totals(session, workspace_id, [transaction.id]).get(transaction.id, 0)
    left_on_invoice = invoice.total_kobo - invoice_paid_totals(session, workspace_id, [invoice.id]).get(invoice.id, 0)

    # Step 3: neither side may go over.
    if amount_kobo > left_on_transaction:
        raise OverAllocated("transaction", left_on_transaction)
    if amount_kobo > left_on_invoice:
        raise OverAllocated("invoice", left_on_invoice)

    allocation = PaymentAllocation(
        workspace_id=workspace_id,
        transaction_id=transaction.id,
        invoice_id=invoice.id,
        amount_kobo=amount_kobo,
        method=method,
        created_by=actor_user_id,
    )
    session.add(allocation)
    record(
        session,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action="allocation.created",
        entity_type="allocation",
        entity_id=allocation.id,
        data={
            "transaction_id": str(transaction.id),
            "invoice_id": str(invoice.id),
            "invoice_number": invoice.number,
            "amount_kobo": amount_kobo,
            "method": method,
        },
    )
    # flush = run the INSERTs now (inside the open transaction) so constraint errors surface here,
    # but leave the commit to the caller.
    session.flush()
    return allocation


# --- reverse ------------------------------------------------------------------------------------------


def reverse(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    allocation_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    reason: str,
) -> PaymentAllocation:
    """Undo an allocation by marking it reversed. The row stays forever (invariant 7). Does NOT commit."""
    reason = reason.strip()
    if not reason:
        raise AllocationNotAllowed("A reason is required to reverse an allocation")

    # Lock it so two "reverse" clicks can't both pass the already-reversed check.
    allocation = session.exec(
        select(PaymentAllocation)
        .where(PaymentAllocation.id == allocation_id, PaymentAllocation.workspace_id == workspace_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if allocation is None:
        raise AllocationNotFound("Allocation not found")
    if allocation.reversed_at is not None:
        raise AllocationAlreadyReversed("This allocation was already reversed")

    allocation.reversed_at = utc_now()
    allocation.reversed_by = actor_user_id
    allocation.reversal_reason = reason
    session.add(allocation)
    record(
        session,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action="allocation.reversed",
        entity_type="allocation",
        entity_id=allocation.id,
        data={
            "transaction_id": str(allocation.transaction_id),
            "invoice_id": str(allocation.invoice_id),
            "amount_kobo": allocation.amount_kobo,
            "reason": reason,
        },
    )
    session.flush()
    return allocation


# --- reading ------------------------------------------------------------------------------------------------


def to_read(session: Session, allocation: PaymentAllocation) -> AllocationRead:
    """API shape of one allocation, with its invoice number for display."""
    number = session.exec(
        select(Invoice.number).where(Invoice.id == allocation.invoice_id, Invoice.workspace_id == allocation.workspace_id)
    ).one()
    return AllocationRead(
        id=allocation.id,
        invoice_id=allocation.invoice_id,
        invoice_number=number,
        amount_kobo=allocation.amount_kobo,
        method=allocation.method,
        created_at=allocation.created_at,
        reversed_at=allocation.reversed_at,
        reversal_reason=allocation.reversal_reason,
    )
