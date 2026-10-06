"""Paystack: start a checkout from the public invoice page, then record the money once when the webhook arrives.

start_payment() only asks Paystack for a checkout URL; it writes nothing. The webhook is what records money.

Why each webhook step (docs/API.md, DECISIONS D-30 to D-33):
1. signature_is_valid(): Paystack signs the RAW request body with HMAC-SHA512 and our secret key. We check
   it on the bytes before parsing, so nothing unauthenticated reaches the JSON parser. Re-serialised JSON
   could differ in spacing or key order and give a different hash.
2. handle_event(): the webhook body is only a hint. We call verify-transaction and use ITS amount, status
   and metadata (D-30), so a replayed or forged body can't change what is recorded.
3. record_charge(): ONE database transaction holds the insert, the audit row and the allocation (invariant 3).
   - INSERT ... ON CONFLICT (source, external_reference) DO NOTHING: a retried webhook inserts nothing,
     so allocate() is never reached a second time. If two copies arrive at the same instant, the second
     INSERT waits on the unique index until the first commits, then does nothing.
   - If the money can't be allocated (invoice void, or more than is owed), it is still recorded as an
     unallocated credit and shows up in the exception queue (D-31).
"""

import hashlib
import hmac
import uuid
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, select

from app.allocations.service import AllocationNotAllowed, OverAllocated, allocate
from app.audit.service import record
from app.core.config import settings
from app.core.time import LAGOS, utc_now
from app.customers.models import Customer
from app.invoices import service as invoices
from app.invoices.models import Invoice
from app.paystack import client
from app.paystack.schemas import PaymentLink, VerifiedCharge
from app.transactions.models import Transaction

SOURCE = "paystack"
# Derived statuses (D-05) that still have money owing. paid, void and draft can't be paid online.
PAYABLE_STATUSES = ("sent", "part_paid", "overdue")


class PaymentNotPossible(Exception):
    """This invoice can't be paid online right now; the message is safe to show the customer."""


# --- starting a payment (public invoice page) ---------------------------------------------------------


def start_payment(session: Session, token: str) -> PaymentLink:
    """Start a Paystack checkout for what is still owed on the invoice behind this public token.

    Raises invoices.InvoiceNotFound, PaymentNotPossible, or client.PaystackUnavailable.
    Writes nothing: the money is only recorded when the webhook arrives.
    """
    row = session.exec(
        select(Invoice, Customer.name, Customer.email)
        .join(Customer, Customer.id == Invoice.customer_id)
        .where(Invoice.public_token == token)
    ).first()
    if row is None:
        raise invoices.InvoiceNotFound
    invoice, customer_name, customer_email = row

    # Status and outstanding are derived from allocations (invariant 5), the same way the invoice page shows them.
    paid_kobo = invoices.paid_totals(session, invoice.workspace_id, [invoice.id]).get(invoice.id, 0)
    read = invoices.to_read(invoice, customer_name, paid_kobo)
    if read.status not in PAYABLE_STATUSES or read.outstanding_kobo <= 0:
        raise PaymentNotPossible(f"This invoice is {read.status.replace('_', ' ')} and can't be paid online")
    if not customer_email:
        # Paystack's initialise requires an email address (D-34).
        raise PaymentNotPossible("Online payment isn't set up for this invoice. Please pay by bank transfer.")

    url = client.initialize_transaction(
        email=customer_email,
        amount_kobo=read.outstanding_kobo,  # only what is still owed, so a card payment can't overpay
        invoice_id=invoice.id,
        callback_url=f"{settings.frontend_url}/i/{token}",  # Paystack sends the customer back to the invoice page
    )
    return PaymentLink(authorization_url=url)


# --- the webhook ---------------------------------------------------------------------------------------


def signature_is_valid(raw_body: bytes, signature: str | None, secret: str) -> bool:
    """True if `signature` is HMAC-SHA512(raw_body, secret) in hex."""
    if not secret or not signature:
        # No secret configured means we can't tell real events from fakes: refuse them all.
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha512).hexdigest()
    # compare_digest takes the same time however many characters match, so an attacker can't
    # guess the signature one character at a time by timing our responses.
    return hmac.compare_digest(expected, signature)


def handle_event(session: Session, payload: dict[str, Any]) -> str:
    """Process one signed webhook event. Raises client.PaystackUnavailable if Paystack can't be asked."""
    if payload.get("event") != "charge.success":
        return "ignored"
    data = payload.get("data")
    reference = data.get("reference") if isinstance(data, dict) else None
    if not isinstance(reference, str) or not reference:
        return "ignored"
    # Called through the module (not imported by name) so tests can replace it with a fake.
    charge = client.verify_transaction(reference)
    if charge is None:
        return "ignored"
    return record_charge(session, charge)


def record_charge(session: Session, charge: VerifiedCharge) -> str:
    """Save a verified Paystack payment and allocate it to its invoice. Commits.

    Returns "allocated", "unallocated" (recorded, waiting in the queue), "duplicate" or "ignored".
    """
    # Kobo only means something for naira: 10,000 US cents are not ₦100.
    if charge.status != "success" or charge.currency != "NGN" or charge.amount_kobo <= 0:
        return "ignored"
    if charge.invoice_id is None:
        return "ignored"

    # The one lookup NOT filtered by workspace: a webhook has no logged-in user. The invoice id comes from
    # Paystack-verified metadata, and from here on the invoice's own workspace_id scopes everything (invariant 8).
    invoice = session.exec(select(Invoice).where(Invoice.id == charge.invoice_id)).first()
    if invoice is None:
        return "ignored"  # no invoice means no workspace to put the money in
    workspace_id = invoice.workspace_id

    row = {
        # A Core insert doesn't run the model's default_factory, so ids and timestamps are set here.
        "id": uuid.uuid4(),
        "workspace_id": workspace_id,
        "source": SOURCE,
        # A customer's payment. Paystack's later payout on the bank statement is kind=settlement (invariant 6).
        "kind": "credit",
        "value_date": charge.paid_at.astimezone(LAGOS).date(),  # D-13
        "amount_kobo": charge.amount_kobo,
        "narration": f"Paystack {charge.channel or 'payment'} {charge.reference}",
        "payer_name": charge.payer_name[:200] if charge.payer_name else None,
        "external_reference": charge.reference,
        # fingerprint is NOT NULL; for Paystack the reference alone already identifies the payment.
        "fingerprint": hashlib.sha256(f"{SOURCE}|{charge.reference}".encode()).hexdigest(),
        "created_at": utc_now(),
    }
    statement = (
        insert(Transaction)
        .values(row)
        .on_conflict_do_nothing(constraint="uq_transactions_source_external_reference")
        .returning(Transaction.id)
    )
    transaction_id = session.exec(statement).scalar_one_or_none()
    if transaction_id is None:
        session.rollback()  # nothing to save; just end the database transaction
        return "duplicate"

    record(
        session,
        workspace_id=workspace_id,
        actor_user_id=None,  # the system, on Paystack's word
        action="paystack.payment_received",
        entity_type="transaction",
        entity_id=transaction_id,
        data={
            "reference": charge.reference,
            "amount_kobo": charge.amount_kobo,
            "invoice_id": str(invoice.id),
            "invoice_number": invoice.number,
        },
    )

    try:
        allocate(
            session,
            workspace_id=workspace_id,
            transaction_id=transaction_id,
            invoice_id=invoice.id,
            amount_kobo=charge.amount_kobo,
            method="auto",
            actor_user_id=None,
        )
        outcome = "allocated"
    except (OverAllocated, AllocationNotAllowed):
        # allocate() checks before it adds anything, so the session still holds only the transaction and
        # its audit row. Keep them: the money really arrived; the accountant decides where it goes (D-31).
        outcome = "unallocated"

    # One commit for the transaction row, its audit row and the allocation (invariant 3, D-18).
    session.commit()
    return outcome
