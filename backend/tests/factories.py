"""Build rows directly in the database for tests that don't go through the API.

Factories commit, so a test can then roll back the code under test without losing its setup.
(With the rolled-back `session` fixture a commit only releases a savepoint; everything is
still undone after the test.)

There is deliberately NO factory for payment_allocations: tests create them through
allocate(), the only code allowed to insert them (invariant 4).
"""

import uuid
from datetime import date, timedelta

from sqlmodel import Session

from app.auth.models import User, Workspace
from app.core.security import hash_password
from app.core.time import lagos_today, utc_now
from app.customers.models import Customer
from app.invoices.models import Invoice
from app.invoices.service import compute_vat
from app.transactions.models import Transaction

# Hashing is slow on purpose; hash once for every test user.
_PASSWORD_HASH = hash_password("correct-horse-1")


def make_owner(session: Session, workspace_name: str = "Adaeze Foods") -> User:
    workspace = Workspace(name=workspace_name)
    session.add(workspace)
    session.flush()
    user = User(workspace_id=workspace.id, email=f"{uuid.uuid4().hex[:8]}@example.com", password_hash=_PASSWORD_HASH)
    session.add(user)
    session.commit()
    return user


def make_invoice(
    session: Session,
    owner: User,
    *,
    subtotal_kobo: int = 10_000_000,
    status: str = "sent",
    due_date: date | None = None,
) -> Invoice:
    """A sent invoice by default. subtotal 10,000,000 -> VAT 750,000 -> total 10,750,000 kobo (₦107,500)."""
    customer = Customer(workspace_id=owner.workspace_id, name="Kola & Sons")
    session.add(customer)
    session.flush()
    vat = compute_vat(subtotal_kobo)
    code = uuid.uuid4().hex[:6].upper()
    today = lagos_today()
    invoice = Invoice(
        workspace_id=owner.workspace_id,
        customer_id=customer.id,
        number=f"INV-{code}",
        reference=f"RCN-{code}",
        description="Test invoice",
        status=status,
        issue_date=today,
        due_date=due_date or today + timedelta(days=14),
        sent_at=utc_now() if status != "draft" else None,
        subtotal_kobo=subtotal_kobo,
        vat_kobo=vat,
        total_kobo=subtotal_kobo + vat,
    )
    session.add(invoice)
    session.commit()
    return invoice


def make_transaction(session: Session, owner: User, *, amount_kobo: int, kind: str = "credit") -> Transaction:
    """A bank-statement line. The fingerprint is random here; real imports compute it (feature 4)."""
    transaction = Transaction(
        workspace_id=owner.workspace_id,
        source="bank_statement",
        kind=kind,
        value_date=lagos_today(),
        amount_kobo=amount_kobo,
        narration="TRF/KOLA AND SONS/RCN-TEST",
        payer_name="KOLA AND SONS",
        fingerprint=uuid.uuid4().hex,
    )
    session.add(transaction)
    session.commit()
    return transaction
