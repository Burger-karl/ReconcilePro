"""Invoice rules: VAT, derived status, numbering, references, and the draft -> sent -> void lifecycle.

Routes call these functions; every query here filters by the caller's workspace_id (invariant 8).
Every change writes an audit event in the same commit (invariant 7).
"""

import secrets
import uuid
from collections import defaultdict
from datetime import date

from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.allocations import service as allocations
from app.audit.service import record
from app.auth.models import User, Workspace
from app.core.time import lagos_today, utc_now
from app.customers.models import Customer
from app.invoices.models import Invoice
from app.invoices.schemas import InvoiceCreate, InvoiceRead, InvoiceUpdate, PublicInvoice

__all__ = ["lagos_today"]  # re-exported for tests and other features: "today" always means Lagos today


class InvoiceNotFound(Exception):
    pass


class CustomerNotFound(Exception):
    pass


class InvoiceConflict(Exception):
    """The action is not allowed in the invoice's current state (route returns 409)."""


# --- pure rules (no database) ----------------------------------------------------------------------

VAT_RATE_PER_THOUSAND = 75  # 7.5% = 75 / 1000


def compute_vat(subtotal_kobo: int) -> int:
    """7.5% of the subtotal, rounded half UP to the nearest kobo (docs/DECISIONS.md D-02).

    Integer maths only: multiply by 75, add half of 1000, then floor-divide by 1000.
    Adding 500 first is what turns floor division into "round half up".
    Python's round() is NOT used: it rounds halves to the nearest even number (4.5 -> 4).
    """
    return (subtotal_kobo * VAT_RATE_PER_THOUSAND + 500) // 1000


def derive_status(stored: str, *, total_kobo: int, paid_kobo: int, due_date: date, today: date) -> str:
    """The status the user sees. Checked in this order (docs/DECISIONS.md D-05):

    void/draft (stored) -> paid -> overdue -> part_paid -> sent.
    Overdue beats part_paid: a late invoice needs chasing even if some money came in.
    """
    if stored in ("void", "draft"):
        return stored
    if paid_kobo >= total_kobo:
        return "paid"
    if today > due_date:
        return "overdue"
    if paid_kobo > 0:
        return "part_paid"
    return "sent"


# Payment references avoid characters people mistype when copying them into a banking app:
# no 0/O, no 1/I/L.
REFERENCE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def new_reference() -> str:
    """e.g. RCN-7K4Q2M. secrets (not random) so references can't be predicted."""
    return "RCN-" + "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(6))


# --- money paid so far ----------------------------------------------------------------------------


def paid_totals(session: Session, workspace_id: uuid.UUID, invoice_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """Kobo paid per invoice = sum of NON-reversed payment_allocations (computed by the allocations
    feature, which owns that table). Invoices with nothing paid are absent from the result."""
    return allocations.invoice_paid_totals(session, workspace_id, invoice_ids)


def to_read(invoice: Invoice, customer_name: str, paid_kobo: int, today: date | None = None) -> InvoiceRead:
    today = today or lagos_today()
    return InvoiceRead(
        id=invoice.id,
        number=invoice.number,
        reference=invoice.reference,
        customer_id=invoice.customer_id,
        customer_name=customer_name,
        description=invoice.description,
        status=derive_status(
            invoice.status, total_kobo=invoice.total_kobo, paid_kobo=paid_kobo, due_date=invoice.due_date, today=today
        ),
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
        sent_at=invoice.sent_at,
        subtotal_kobo=invoice.subtotal_kobo,
        vat_kobo=invoice.vat_kobo,
        total_kobo=invoice.total_kobo,
        paid_kobo=paid_kobo,
        outstanding_kobo=max(invoice.total_kobo - paid_kobo, 0),
        public_token=invoice.public_token,
        created_at=invoice.created_at,
    )


def _read_many(session: Session, workspace_id: uuid.UUID, rows: list[tuple[Invoice, str]]) -> list[InvoiceRead]:
    paid = paid_totals(session, workspace_id, [invoice.id for invoice, _ in rows])
    today = lagos_today()
    return [to_read(invoice, name, paid.get(invoice.id, 0), today) for invoice, name in rows]


def outstanding_by_customer(session: Session, workspace_id: uuid.UUID) -> dict[uuid.UUID, int]:
    """What each customer still owes: outstanding on their sent / part_paid / overdue invoices."""
    rows = session.exec(
        select(Invoice, Customer.name)
        .join(Customer, Customer.id == Invoice.customer_id)
        .where(Invoice.workspace_id == workspace_id, Invoice.status == "sent")
    ).all()
    owed: dict[uuid.UUID, int] = defaultdict(int)
    for invoice in _read_many(session, workspace_id, list(rows)):
        if invoice.status in ("sent", "part_paid", "overdue"):
            owed[invoice.customer_id] += invoice.outstanding_kobo
    return owed


# --- lookups (always scoped to the user's workspace) ----------------------------------------------


def _get_customer(session: Session, user: User, customer_id: uuid.UUID) -> Customer:
    customer = session.exec(
        select(Customer).where(Customer.id == customer_id, Customer.workspace_id == user.workspace_id)
    ).first()
    if customer is None:
        raise CustomerNotFound
    return customer


def _get_invoice(session: Session, user: User, invoice_id: uuid.UUID) -> Invoice:
    # Another workspace's invoice is "not found", exactly like an id that doesn't exist.
    invoice = session.exec(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.workspace_id == user.workspace_id)
    ).first()
    if invoice is None:
        raise InvoiceNotFound
    return invoice


def _read_one(session: Session, invoice: Invoice) -> InvoiceRead:
    customer = session.get(Customer, invoice.customer_id)
    return to_read(invoice, customer.name, paid_totals(session, invoice.workspace_id, [invoice.id]).get(invoice.id, 0))


def get_invoice(session: Session, user: User, invoice_id: uuid.UUID) -> InvoiceRead:
    return _read_one(session, _get_invoice(session, user, invoice_id))


def list_invoices(
    session: Session,
    user: User,
    *,
    status: str | None = None,
    customer_id: uuid.UUID | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[InvoiceRead], int]:
    query = (
        select(Invoice, Customer.name)
        .join(Customer, Customer.id == Invoice.customer_id)
        .where(Invoice.workspace_id == user.workspace_id)
        .order_by(Invoice.created_at.desc())
    )
    if customer_id is not None:
        query = query.where(Invoice.customer_id == customer_id)
    if q and q.strip():
        term = q.strip()
        query = query.where(
            or_(
                Invoice.number.icontains(term, autoescape=True),
                Invoice.reference.icontains(term, autoescape=True),
                Customer.name.icontains(term, autoescape=True),
            )
        )
    invoices = _read_many(session, user.workspace_id, list(session.exec(query).all()))
    # Status is derived, so it can't be a SQL WHERE (paid/overdue aren't columns). We filter after
    # deriving; fine for an SME's few thousand invoices, and keeps one definition of status.
    if status is not None:
        invoices = [invoice for invoice in invoices if invoice.status == status]
    return invoices[offset : offset + limit], len(invoices)


# --- changes ---------------------------------------------------------------------------------------


def _next_number(session: Session, workspace_id: uuid.UUID) -> str:
    """INV-0001, INV-0002, ... per workspace.

    SELECT ... FOR UPDATE on the workspace row makes two simultaneous "create invoice" requests
    take turns, so they can't both count the same number of invoices and pick the same number.
    The lock is released when the transaction commits. Invoices are never deleted (only voided),
    so count + 1 never reuses a number.
    """
    session.exec(select(Workspace).where(Workspace.id == workspace_id).with_for_update()).one()
    count = session.exec(select(func.count()).select_from(Invoice).where(Invoice.workspace_id == workspace_id)).one()
    return f"INV-{count + 1:04d}"


def _unused_reference(session: Session, workspace_id: uuid.UUID) -> str:
    # 31^6 ≈ 887 million codes, so a clash is very unlikely; checking anyway is cheap.
    for _ in range(10):
        reference = new_reference()
        clash = session.exec(
            select(Invoice.id).where(Invoice.workspace_id == workspace_id, Invoice.reference == reference)
        ).first()
        if clash is None:
            return reference
    raise RuntimeError("Could not generate a unique payment reference")


def create_invoice(session: Session, user: User, data: InvoiceCreate) -> InvoiceRead:
    customer = _get_customer(session, user, data.customer_id)
    vat_kobo = compute_vat(data.subtotal_kobo)
    invoice = Invoice(
        workspace_id=user.workspace_id,
        customer_id=customer.id,
        number=_next_number(session, user.workspace_id),
        reference=_unused_reference(session, user.workspace_id),
        description=data.description,
        status="draft",
        issue_date=data.issue_date,
        due_date=data.due_date,
        subtotal_kobo=data.subtotal_kobo,
        vat_kobo=vat_kobo,
        total_kobo=data.subtotal_kobo + vat_kobo,
    )
    session.add(invoice)
    record(
        session,
        workspace_id=user.workspace_id,
        actor_user_id=user.id,
        action="invoice.created",
        entity_type="invoice",
        entity_id=invoice.id,
        data={"number": invoice.number, "customer_id": str(customer.id), "total_kobo": invoice.total_kobo},
    )
    session.commit()
    return to_read(invoice, customer.name, 0)


def _json_value(value: object) -> object:
    """Audit data is JSON: dates and ids become strings."""
    return value.isoformat() if isinstance(value, date) else str(value) if isinstance(value, uuid.UUID) else value


def update_invoice(session: Session, user: User, invoice_id: uuid.UUID, data: InvoiceUpdate) -> InvoiceRead:
    invoice = _get_invoice(session, user, invoice_id)
    if invoice.status != "draft":
        raise InvoiceConflict("Only draft invoices can be edited")

    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if "customer_id" in changes:
        _get_customer(session, user, changes["customer_id"])  # must be in the same workspace
    issue_date = changes.get("issue_date", invoice.issue_date)
    due_date = changes.get("due_date", invoice.due_date)
    if due_date < issue_date:
        raise InvoiceConflict("Due date cannot be before the issue date")

    audit_changes = {}
    for field, new_value in changes.items():
        old_value = getattr(invoice, field)
        if old_value != new_value:
            audit_changes[field] = {"from": _json_value(old_value), "to": _json_value(new_value)}
            setattr(invoice, field, new_value)
    # VAT and total always follow the subtotal; they are never taken from the client.
    invoice.vat_kobo = compute_vat(invoice.subtotal_kobo)
    invoice.total_kobo = invoice.subtotal_kobo + invoice.vat_kobo

    if audit_changes:
        record(
            session,
            workspace_id=user.workspace_id,
            actor_user_id=user.id,
            action="invoice.updated",
            entity_type="invoice",
            entity_id=invoice.id,
            data={"changes": audit_changes},
        )
    session.add(invoice)
    session.commit()
    return _read_one(session, invoice)


def send_invoice(session: Session, user: User, invoice_id: uuid.UUID) -> InvoiceRead:
    """draft -> sent. Creates the public link token. (Emailing the customer comes in feature 7.)"""
    invoice = _get_invoice(session, user, invoice_id)
    if invoice.status != "draft":
        raise InvoiceConflict("Only draft invoices can be sent")
    invoice.status = "sent"
    invoice.sent_at = utc_now()
    # 32 random bytes -> 43 URL-safe characters: impossible to guess, safe in a URL.
    invoice.public_token = secrets.token_urlsafe(32)
    record(
        session,
        workspace_id=user.workspace_id,
        actor_user_id=user.id,
        action="invoice.sent",
        entity_type="invoice",
        entity_id=invoice.id,
        data={"number": invoice.number, "total_kobo": invoice.total_kobo},
    )
    session.add(invoice)
    session.commit()
    return _read_one(session, invoice)


def void_invoice(session: Session, user: User, invoice_id: uuid.UUID, reason: str) -> InvoiceRead:
    """Cancel an invoice. Refused if money is allocated to it: reverse those allocations first,
    otherwise the payment would silently disappear from the books."""
    invoice = _get_invoice(session, user, invoice_id)
    if invoice.status == "void":
        raise InvoiceConflict("Invoice is already void")
    if paid_totals(session, invoice.workspace_id, [invoice.id]).get(invoice.id, 0) > 0:
        raise InvoiceConflict("Reverse the payments allocated to this invoice before voiding it")
    invoice.status = "void"
    record(
        session,
        workspace_id=user.workspace_id,
        actor_user_id=user.id,
        action="invoice.voided",
        entity_type="invoice",
        entity_id=invoice.id,
        data={"number": invoice.number, "reason": reason},
    )
    session.add(invoice)
    session.commit()
    return _read_one(session, invoice)


# --- public page (no login) ------------------------------------------------------------------------


def get_public_invoice(session: Session, token: str) -> PublicInvoice:
    """Look up by the secret token only. Drafts have no token, so they can never be shown."""
    row = session.exec(
        select(Invoice, Customer.name, Workspace.name)
        .join(Customer, Customer.id == Invoice.customer_id)
        .join(Workspace, Workspace.id == Invoice.workspace_id)
        .where(Invoice.public_token == token)
    ).first()
    if row is None:
        raise InvoiceNotFound
    invoice, customer_name, business_name = row
    read = to_read(invoice, customer_name, paid_totals(session, invoice.workspace_id, [invoice.id]).get(invoice.id, 0))
    return PublicInvoice(business_name=business_name, **read.model_dump(include=set(PublicInvoice.model_fields) - {"business_name"}))
