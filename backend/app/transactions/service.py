"""Read bank credits and Paystack payments. Every query filters by the caller's workspace (invariant 8).

This feature only reads transactions; statement import and the Paystack webhook create them, and
only allocations/service.py allocates them.
"""

import uuid
from datetime import date

from sqlmodel import Session, select

from app.allocations.models import PaymentAllocation
from app.allocations.service import allocated_totals
from app.auth.models import User
from app.invoices.models import Invoice
from app.transactions.models import Transaction
from app.transactions.schemas import AllocationRead, TransactionDetail, TransactionRead


class TransactionNotFound(Exception):
    pass


def to_read(transaction: Transaction, allocated_kobo: int) -> TransactionRead:
    return TransactionRead(
        id=transaction.id,
        source=transaction.source,
        kind=transaction.kind,
        value_date=transaction.value_date,
        amount_kobo=transaction.amount_kobo,
        allocated_kobo=allocated_kobo,
        unallocated_kobo=transaction.amount_kobo - allocated_kobo,
        narration=transaction.narration,
        bank_reference=transaction.bank_reference,
        balance_kobo=transaction.balance_kobo,
        payer_name=transaction.payer_name,
        created_at=transaction.created_at,
    )


def _state(read: TransactionRead) -> str:
    if read.allocated_kobo == 0:
        return "unallocated"
    if read.unallocated_kobo == 0:
        return "allocated"
    return "part"


def list_transactions(
    session: Session,
    user: User,
    *,
    source: str | None = None,
    kind: str | None = None,
    state: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[TransactionRead], int]:
    query = (
        select(Transaction)
        .where(Transaction.workspace_id == user.workspace_id)
        .order_by(Transaction.value_date.desc(), Transaction.created_at.desc())
    )
    if source is not None:
        query = query.where(Transaction.source == source)
    if kind is not None:
        query = query.where(Transaction.kind == kind)
    if date_from is not None:
        query = query.where(Transaction.value_date >= date_from)
    if date_to is not None:
        query = query.where(Transaction.value_date <= date_to)

    transactions = session.exec(query).all()
    allocated = allocated_totals(session, user.workspace_id, [t.id for t in transactions])
    reads = [to_read(t, allocated.get(t.id, 0)) for t in transactions]
    # Like invoice status (docs/DECISIONS.md D-15), allocation state is derived, so it is filtered in Python.
    if state is not None:
        reads = [read for read in reads if _state(read) == state]
    return reads[offset : offset + limit], len(reads)


def get_transaction(session: Session, user: User, transaction_id: uuid.UUID) -> TransactionDetail:
    transaction = session.exec(
        select(Transaction).where(Transaction.id == transaction_id, Transaction.workspace_id == user.workspace_id)
    ).first()
    if transaction is None:
        raise TransactionNotFound
    rows = session.exec(
        select(PaymentAllocation, Invoice.number)
        .join(Invoice, Invoice.id == PaymentAllocation.invoice_id)
        .where(PaymentAllocation.transaction_id == transaction.id, PaymentAllocation.workspace_id == user.workspace_id)
        .order_by(PaymentAllocation.created_at)
    ).all()
    allocated = allocated_totals(session, user.workspace_id, [transaction.id]).get(transaction.id, 0)
    return TransactionDetail(
        **to_read(transaction, allocated).model_dump(),
        allocations=[
            AllocationRead(
                id=allocation.id,
                invoice_id=allocation.invoice_id,
                invoice_number=number,
                amount_kobo=allocation.amount_kobo,
                method=allocation.method,
                created_at=allocation.created_at,
                reversed_at=allocation.reversed_at,
                reversal_reason=allocation.reversal_reason,
            )
            for allocation, number in rows
        ],
    )
