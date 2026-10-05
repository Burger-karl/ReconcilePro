"""Reconciliation: load data, ask the (pure) matcher, and move money only through allocate().

Every query filters by workspace (invariant 8). Nothing here inserts allocations directly (invariant 4).
"""

import uuid

from sqlmodel import Session, select

from app.allocations import service as allocations
from app.allocations.models import PaymentAllocation
from app.audit.models import AuditEvent
from app.audit.service import record
from app.auth.models import User
from app.core.time import LAGOS, lagos_today
from app.customers.models import Customer
from app.invoices.models import Invoice
from app.invoices.service import derive_status
from app.matching.service import CreditIn, InvoiceIn, MatchResult, match
from app.reconciliation.schemas import AllocateRequest, BreakdownRead, CandidateRead, QueueItem
from app.transactions.models import Transaction
from app.transactions.service import to_read


class NotFound(Exception):
    pass


# --- loading data for the matcher -------------------------------------------------------------------------


def open_invoices(session: Session, workspace_id: uuid.UUID) -> list[InvoiceIn]:
    """Every sent invoice with its DERIVED status and outstanding amount. match() keeps only the open ones."""
    rows = session.exec(
        select(Invoice, Customer)
        .join(Customer, Customer.id == Invoice.customer_id)
        .where(Invoice.workspace_id == workspace_id, Invoice.status == "sent")
    ).all()
    paid = allocations.invoice_paid_totals(session, workspace_id, [invoice.id for invoice, _ in rows])
    today = lagos_today()
    result = []
    for invoice, customer in rows:
        paid_kobo = paid.get(invoice.id, 0)
        result.append(
            InvoiceIn(
                id=invoice.id,
                number=invoice.number,
                reference=invoice.reference,
                status=derive_status(
                    invoice.status, total_kobo=invoice.total_kobo, paid_kobo=paid_kobo, due_date=invoice.due_date, today=today
                ),
                customer_name=customer.name,
                aliases=tuple(customer.aliases),
                outstanding_kobo=invoice.total_kobo - paid_kobo,
                # sent_at is stored in UTC; the date that counts is the Lagos date (docs/DECISIONS.md D-13).
                sent_date=invoice.sent_at.astimezone(LAGOS).date() if invoice.sent_at else None,
            )
        )
    return result


def _credit_in(transaction: Transaction, allocated_kobo: int) -> CreditIn:
    return CreditIn(
        id=transaction.id,
        kind=transaction.kind,
        amount_kobo=transaction.amount_kobo - allocated_kobo,  # match on what is still unallocated
        value_date=transaction.value_date,
        narration=transaction.narration,
        bank_reference=transaction.bank_reference,
        payer_name=transaction.payer_name,
    )


def rejected_pairs(session: Session, workspace_id: uuid.UUID) -> set[tuple[uuid.UUID, uuid.UUID]]:
    """(transaction, invoice) pairs the accountant said "not this one" to (docs/DECISIONS.md D-28)."""
    events = session.exec(
        select(AuditEvent.data).where(AuditEvent.workspace_id == workspace_id, AuditEvent.action == "match.rejected")
    ).all()
    return {(uuid.UUID(data["transaction_id"]), uuid.UUID(data["invoice_id"])) for data in events}


def _match(credit: CreditIn, invoices: list[InvoiceIn], rejected: set[tuple[uuid.UUID, uuid.UUID]]) -> MatchResult:
    return match(credit, [invoice for invoice in invoices if (credit.id, invoice.id) not in rejected])


def _unallocated_credits(session: Session, workspace_id: uuid.UUID, transaction_ids: list[uuid.UUID] | None = None):
    """(transaction, allocated_kobo) for credits that still have money left, newest first."""
    query = (
        select(Transaction)
        .where(Transaction.workspace_id == workspace_id, Transaction.kind == "credit")
        .order_by(Transaction.value_date.desc(), Transaction.created_at.desc())
    )
    if transaction_ids is not None:
        query = query.where(Transaction.id.in_(transaction_ids))
    transactions = session.exec(query).all()
    allocated = allocations.allocated_totals(session, workspace_id, [t.id for t in transactions])
    return [(t, allocated.get(t.id, 0)) for t in transactions if allocated.get(t.id, 0) < t.amount_kobo]


# --- auto-matching ----------------------------------------------------------------------------------------


def auto_match(session: Session, workspace_id: uuid.UUID, transaction_ids: list[uuid.UUID] | None = None) -> tuple[int, int]:
    """Allocate every credit that has an exact, fitting reference. Returns (auto_allocated, needs_review).

    The system is the actor (actor_user_id=None). Does NOT commit: statement import calls this inside
    its own transaction, so the import and its automatic allocations are saved together.
    """
    rejected = rejected_pairs(session, workspace_id)
    auto_allocated = needs_review = 0
    for transaction, allocated_kobo in _unallocated_credits(session, workspace_id, transaction_ids):
        # Reload invoices for every credit: an allocation made for the previous credit changes what is outstanding.
        result = _match(_credit_in(transaction, allocated_kobo), open_invoices(session, workspace_id), rejected)
        if result.decision != "auto":
            needs_review += 1
            continue
        try:
            allocations.allocate(
                session,
                workspace_id=workspace_id,
                transaction_id=transaction.id,
                invoice_id=result.invoice_id,
                amount_kobo=result.amount_kobo,
                method="auto",
                actor_user_id=None,
            )
            auto_allocated += 1
        except allocations.AllocationError:
            # e.g. someone allocated to the invoice a moment ago. Leave it for a person to look at.
            needs_review += 1
    return auto_allocated, needs_review


def run_auto_match(session: Session, user: User) -> int:
    auto_allocated, _ = auto_match(session, user.workspace_id)
    session.commit()
    return auto_allocated


# --- the queue --------------------------------------------------------------------------------------------


def queue(session: Session, user: User) -> list[QueueItem]:
    """Credits with money still unallocated, each with its best candidates. Settlements never appear."""
    invoices = open_invoices(session, user.workspace_id)
    rejected = rejected_pairs(session, user.workspace_id)
    items = []
    for transaction, allocated_kobo in _unallocated_credits(session, user.workspace_id):
        result = _match(_credit_in(transaction, allocated_kobo), invoices, rejected)
        items.append(
            QueueItem(
                transaction=to_read(transaction, allocated_kobo),
                # An exact reference that wasn't auto-allocated yet (e.g. invoice sent after the import) is a
                # suggestion too.
                suggested_invoice_id=result.invoice_id if result.decision in ("auto", "suggested") else None,
                candidates=[
                    CandidateRead(
                        invoice_id=c.invoice_id,
                        invoice_number=c.number,
                        customer_name=c.customer_name,
                        status=c.status,
                        outstanding_kobo=c.outstanding_kobo,
                        score=c.score,
                        breakdown=BreakdownRead(amount=c.breakdown.amount, name=c.breakdown.name, date=c.breakdown.date),
                        reference_match=c.reference_match,
                        reasons=c.reasons,
                    )
                    for c in result.candidates
                ],
            )
        )
    return items


# --- what the accountant does -----------------------------------------------------------------------------


def allocate_by_hand(session: Session, user: User, data: AllocateRequest) -> PaymentAllocation:
    """Accept a suggestion or allocate manually. allocate() checks everything and raises if not allowed."""
    allocation = allocations.allocate(
        session,
        workspace_id=user.workspace_id,
        transaction_id=data.transaction_id,
        invoice_id=data.invoice_id,
        amount_kobo=data.amount_kobo,
        method=data.method,
        actor_user_id=user.id,
    )
    session.commit()
    return allocation


def reject(session: Session, user: User, transaction_id: uuid.UUID, invoice_id: uuid.UUID) -> None:
    """Record "this credit is not for this invoice" so it isn't proposed again."""
    transaction = session.exec(
        select(Transaction.id).where(Transaction.id == transaction_id, Transaction.workspace_id == user.workspace_id)
    ).first()
    invoice = session.exec(
        select(Invoice.id).where(Invoice.id == invoice_id, Invoice.workspace_id == user.workspace_id)
    ).first()
    if transaction is None or invoice is None:
        raise NotFound
    record(
        session,
        workspace_id=user.workspace_id,
        actor_user_id=user.id,
        action="match.rejected",
        entity_type="transaction",
        entity_id=transaction_id,
        data={"transaction_id": str(transaction_id), "invoice_id": str(invoice_id)},
    )
    session.commit()
