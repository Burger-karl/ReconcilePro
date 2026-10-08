"""The hard part: every kobo that moves goes through allocate() (CLAUDE.md invariants 4, 5, 6, 7).

allocate() must:
- lock the bank line and the invoice (SELECT ... FOR UPDATE),
- re-sum their existing NON-reversed allocations after taking the locks,
- refuse if the bank line OR the invoice would be over-allocated,
- never commit itself (the caller commits; the Paystack webhook needs the insert + allocation in one transaction).
Allocations are reversed, never deleted, and every allocation and reversal is audited.

/hardpart-check runs this file.
"""

import threading
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, text
from sqlmodel import Session, SQLModel, func, select

from app.allocations.models import PaymentAllocation
from app.allocations.service import (
    AllocationAlreadyReversed,
    AllocationNotAllowed,
    AllocationNotFound,
    OverAllocated,
    allocate,
    allocated_totals,
    reverse,
)
from app.audit.models import AuditEvent
from app.auth.models import User
from app.invoices import service as invoices
from app.invoices.models import Invoice
from tests.factories import make_invoice, make_owner, make_transaction

INVOICE_TOTAL = 10_750_000  # make_invoice default: 10,000,000 + 7.5% VAT


@pytest.fixture
def owner(session: Session) -> User:
    return make_owner(session)


def pay(session: Session, owner: User, transaction, invoice, amount_kobo: int, method: str = "manual") -> PaymentAllocation:
    allocation = allocate(
        session,
        workspace_id=owner.workspace_id,
        transaction_id=transaction.id,
        invoice_id=invoice.id,
        amount_kobo=amount_kobo,
        method=method,
        actor_user_id=owner.id,
    )
    session.commit()
    return allocation


def paid(session: Session, invoice: Invoice) -> int:
    return invoices.paid_totals(session, invoice.workspace_id, [invoice.id]).get(invoice.id, 0)


def status_of(session: Session, owner: User, invoice: Invoice) -> str:
    return invoices.get_invoice(session, owner, invoice.id).status


# --- exact amounts and boundaries ----------------------------------------------------------------


def test_allocating_exactly_the_invoice_total_marks_it_paid(session: Session, owner: User) -> None:
    invoice = make_invoice(session, owner)
    credit = make_transaction(session, owner, amount_kobo=INVOICE_TOTAL)

    pay(session, owner, credit, invoice, INVOICE_TOTAL)

    assert paid(session, invoice) == INVOICE_TOTAL
    assert status_of(session, owner, invoice) == "paid"


def test_part_payment_marks_invoice_part_paid(session: Session, owner: User) -> None:
    invoice = make_invoice(session, owner)
    credit = make_transaction(session, owner, amount_kobo=5_000_000)

    pay(session, owner, credit, invoice, 5_000_000)

    detail = invoices.get_invoice(session, owner, invoice.id)
    assert (detail.status, detail.paid_kobo, detail.outstanding_kobo) == ("part_paid", 5_000_000, 5_750_000)


def test_one_kobo_over_the_invoice_is_rejected(session: Session, owner: User) -> None:
    invoice = make_invoice(session, owner)
    credit = make_transaction(session, owner, amount_kobo=INVOICE_TOTAL + 1)

    with pytest.raises(OverAllocated) as error:
        pay(session, owner, credit, invoice, INVOICE_TOTAL + 1)

    assert error.value.side == "invoice"
    assert error.value.available_kobo == INVOICE_TOTAL
    assert paid(session, invoice) == 0


def test_one_kobo_over_the_bank_line_is_rejected(session: Session, owner: User) -> None:
    invoice = make_invoice(session, owner)
    credit = make_transaction(session, owner, amount_kobo=5_000_000)

    with pytest.raises(OverAllocated) as error:
        pay(session, owner, credit, invoice, 5_000_001)

    assert error.value.side == "transaction"
    assert error.value.available_kobo == 5_000_000


def test_existing_allocations_are_re_summed_on_the_invoice_side(session: Session, owner: User) -> None:
    invoice = make_invoice(session, owner)
    first = make_transaction(session, owner, amount_kobo=6_000_000)
    second = make_transaction(session, owner, amount_kobo=6_000_000)
    pay(session, owner, first, invoice, 6_000_000)

    with pytest.raises(OverAllocated) as error:
        pay(session, owner, second, invoice, 4_750_001)  # 6,000,000 + 4,750,001 = total + 1

    assert (error.value.side, error.value.available_kobo) == ("invoice", 4_750_000)
    pay(session, owner, second, invoice, 4_750_000)  # exactly the rest is fine
    assert status_of(session, owner, invoice) == "paid"


def test_one_credit_split_across_two_invoices_cannot_exceed_the_credit(session: Session, owner: User) -> None:
    first_invoice = make_invoice(session, owner)
    second_invoice = make_invoice(session, owner)
    credit = make_transaction(session, owner, amount_kobo=15_000_000)
    pay(session, owner, credit, first_invoice, INVOICE_TOTAL)

    with pytest.raises(OverAllocated) as error:
        pay(session, owner, credit, second_invoice, 4_250_001)

    assert (error.value.side, error.value.available_kobo) == ("transaction", 4_250_000)
    pay(session, owner, credit, second_invoice, 4_250_000)
    assert allocated_totals(session, owner.workspace_id, [credit.id])[credit.id] == 15_000_000


@pytest.mark.parametrize("bad_amount", [0, -1, 1.5, 100.0, True, "100"])
def test_amount_must_be_a_positive_whole_number_of_kobo(session: Session, owner: User, bad_amount: object) -> None:
    # invariant 1: kobo are ints. bool is rejected too: True is an int in Python.
    invoice = make_invoice(session, owner)
    credit = make_transaction(session, owner, amount_kobo=INVOICE_TOTAL)

    with pytest.raises(AllocationNotAllowed):
        pay(session, owner, credit, invoice, bad_amount)  # type: ignore[arg-type]


# --- what can be allocated -------------------------------------------------------------------------


def test_settlement_lines_are_never_allocated(session: Session, owner: User) -> None:
    # invariant 6: a Paystack settlement on the bank statement is money we already counted via the webhook.
    invoice = make_invoice(session, owner)
    settlement = make_transaction(session, owner, amount_kobo=INVOICE_TOTAL, kind="settlement")

    with pytest.raises(AllocationNotAllowed, match="settlement"):
        pay(session, owner, settlement, invoice, INVOICE_TOTAL)


@pytest.mark.parametrize("invoice_status", ["draft", "void"])
def test_only_sent_invoices_can_receive_money(session: Session, owner: User, invoice_status: str) -> None:
    invoice = make_invoice(session, owner, status=invoice_status)
    credit = make_transaction(session, owner, amount_kobo=INVOICE_TOTAL)

    with pytest.raises(AllocationNotAllowed):
        pay(session, owner, credit, invoice, 1_000)


def test_unknown_method_is_rejected(session: Session, owner: User) -> None:
    invoice = make_invoice(session, owner)
    credit = make_transaction(session, owner, amount_kobo=INVOICE_TOTAL)

    with pytest.raises(AllocationNotAllowed):
        pay(session, owner, credit, invoice, 1_000, method="magic")


# --- invariant 8: workspaces -----------------------------------------------------------------------


def test_cannot_allocate_across_workspaces(session: Session, owner: User) -> None:
    other = make_owner(session, "Kola & Sons")
    my_invoice = make_invoice(session, owner)
    their_credit = make_transaction(session, other, amount_kobo=INVOICE_TOTAL)
    their_invoice = make_invoice(session, other)
    my_credit = make_transaction(session, owner, amount_kobo=INVOICE_TOTAL)

    with pytest.raises(AllocationNotFound):
        pay(session, owner, their_credit, my_invoice, 1_000)
    with pytest.raises(AllocationNotFound):
        pay(session, owner, my_credit, their_invoice, 1_000)
    # Even the other workspace's own owner can't mix them.
    with pytest.raises(AllocationNotFound):
        pay(session, other, their_credit, my_invoice, 1_000)


# --- reversal (invariant 7) ------------------------------------------------------------------------


def test_reversed_allocations_no_longer_count(session: Session, owner: User) -> None:
    invoice = make_invoice(session, owner)
    wrong_credit = make_transaction(session, owner, amount_kobo=INVOICE_TOTAL)
    right_credit = make_transaction(session, owner, amount_kobo=INVOICE_TOTAL)
    mistake = pay(session, owner, wrong_credit, invoice, INVOICE_TOTAL)

    reverse(session, workspace_id=owner.workspace_id, allocation_id=mistake.id, actor_user_id=owner.id, reason="Wrong customer")
    session.commit()

    assert paid(session, invoice) == 0
    assert status_of(session, owner, invoice) == "sent"
    assert allocated_totals(session, owner.workspace_id, [wrong_credit.id]).get(wrong_credit.id, 0) == 0
    pay(session, owner, right_credit, invoice, INVOICE_TOTAL)  # the invoice can be paid again
    assert status_of(session, owner, invoice) == "paid"


def test_reverse_keeps_the_row(session: Session, owner: User) -> None:
    invoice = make_invoice(session, owner)
    credit = make_transaction(session, owner, amount_kobo=INVOICE_TOTAL)
    allocation = pay(session, owner, credit, invoice, INVOICE_TOTAL)

    reverse(session, workspace_id=owner.workspace_id, allocation_id=allocation.id, actor_user_id=owner.id, reason="Duplicate")
    session.commit()

    row = session.get(PaymentAllocation, allocation.id)
    assert row is not None  # never deleted
    assert row.reversed_at is not None
    assert row.reversed_by == owner.id
    assert row.reversal_reason == "Duplicate"
    assert row.amount_kobo == INVOICE_TOTAL  # history keeps the original amount


def test_cannot_reverse_twice(session: Session, owner: User) -> None:
    invoice = make_invoice(session, owner)
    credit = make_transaction(session, owner, amount_kobo=INVOICE_TOTAL)
    allocation = pay(session, owner, credit, invoice, INVOICE_TOTAL)
    reverse(session, workspace_id=owner.workspace_id, allocation_id=allocation.id, actor_user_id=owner.id, reason="Oops")
    session.commit()

    with pytest.raises(AllocationAlreadyReversed):
        reverse(session, workspace_id=owner.workspace_id, allocation_id=allocation.id, actor_user_id=owner.id, reason="Again")


def test_reverse_needs_a_reason(session: Session, owner: User) -> None:
    invoice = make_invoice(session, owner)
    credit = make_transaction(session, owner, amount_kobo=INVOICE_TOTAL)
    allocation = pay(session, owner, credit, invoice, INVOICE_TOTAL)

    with pytest.raises(AllocationNotAllowed):
        reverse(session, workspace_id=owner.workspace_id, allocation_id=allocation.id, actor_user_id=owner.id, reason="  ")


def test_cannot_reverse_another_workspaces_allocation(session: Session, owner: User) -> None:
    other = make_owner(session, "Kola & Sons")
    invoice = make_invoice(session, owner)
    credit = make_transaction(session, owner, amount_kobo=INVOICE_TOTAL)
    allocation = pay(session, owner, credit, invoice, INVOICE_TOTAL)

    with pytest.raises(AllocationNotFound):
        reverse(session, workspace_id=other.workspace_id, allocation_id=allocation.id, actor_user_id=other.id, reason="x")


def test_allocate_and_reverse_are_audited(session: Session, owner: User) -> None:
    invoice = make_invoice(session, owner)
    credit = make_transaction(session, owner, amount_kobo=INVOICE_TOTAL)
    allocation = pay(session, owner, credit, invoice, INVOICE_TOTAL)
    reverse(session, workspace_id=owner.workspace_id, allocation_id=allocation.id, actor_user_id=owner.id, reason="Oops")
    session.commit()

    events = session.exec(
        select(AuditEvent).where(AuditEvent.entity_id == allocation.id).order_by(AuditEvent.created_at)
    ).all()
    assert [e.action for e in events] == ["allocation.created", "allocation.reversed"]
    assert events[0].data["amount_kobo"] == INVOICE_TOTAL
    assert events[0].data["invoice_id"] == str(invoice.id)
    assert events[1].data["reason"] == "Oops"


def test_system_allocations_have_no_actor(session: Session, owner: User) -> None:
    invoice = make_invoice(session, owner)
    credit = make_transaction(session, owner, amount_kobo=INVOICE_TOTAL)

    allocation = allocate(
        session, workspace_id=owner.workspace_id, transaction_id=credit.id, invoice_id=invoice.id,
        amount_kobo=INVOICE_TOTAL, method="auto", actor_user_id=None,
    )
    session.commit()

    assert allocation.created_by is None
    assert allocation.method == "auto"


# --- allocate() never commits (needed by invariant 3) --------------------------------------------


def test_allocate_does_not_commit(session: Session, owner: User) -> None:
    invoice = make_invoice(session, owner)
    credit = make_transaction(session, owner, amount_kobo=INVOICE_TOTAL)

    allocate(
        session, workspace_id=owner.workspace_id, transaction_id=credit.id, invoice_id=invoice.id,
        amount_kobo=INVOICE_TOTAL, method="manual", actor_user_id=owner.id,
    )
    session.rollback()  # the caller decides: here it changes its mind

    assert session.exec(select(func.count()).select_from(PaymentAllocation)).one() == 0
    assert session.exec(select(func.count()).select_from(AuditEvent)).one() == 0


# --- void now sees real payments ---------------------------------------------------------------------


def test_cannot_void_an_invoice_with_money_on_it(session: Session, owner: User) -> None:
    invoice = make_invoice(session, owner)
    credit = make_transaction(session, owner, amount_kobo=INVOICE_TOTAL)
    pay(session, owner, credit, invoice, 1_000)

    with pytest.raises(invoices.InvoiceConflict, match="Reverse"):
        invoices.void_invoice(session, owner, invoice.id, "Wrong customer")


# --- invariant 4: nobody else inserts allocations ---------------------------------------------------


def test_only_allocations_service_creates_allocations() -> None:
    """A cheap guard against someone adding a shortcut later: scan the app's source code."""
    app_dir = Path(__file__).resolve().parent.parent / "app"
    # models.py only defines the class (`class PaymentAllocation(SQLModel...`), it never inserts.
    allowed = {app_dir / "allocations" / "service.py", app_dir / "allocations" / "models.py"}
    # Ways to create a row: build the model, a Core insert(), or raw SQL. Reading (select) is fine anywhere.
    insert_patterns = ["PaymentAllocation(", "insert(PaymentAllocation", "insert into payment_allocations"]
    offenders = [
        str(path.relative_to(app_dir))
        for path in app_dir.rglob("*.py")
        if path not in allowed
        and any(pattern in path.read_text(encoding="utf-8").lower() for pattern in map(str.lower, insert_patterns))
    ]
    assert offenders == []


# --- concurrency: two requests at the same moment ------------------------------------------------------
# These need two real connections that COMMIT, so they can't use the rolled-back `session` fixture.


@pytest.fixture
def committed(engine: Engine) -> Iterator[Engine]:
    """Data committed for real; every table is emptied afterwards."""
    yield engine
    table_names = ", ".join(f'"{table.name}"' for table in SQLModel.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {table_names} CASCADE"))


def race(engine: Engine, attempts: list[tuple[uuid.UUID, uuid.UUID, uuid.UUID, int]]) -> list[str]:
    """Run each (workspace_id, transaction_id, invoice_id, amount) in its own thread and session,
    all released at the same instant. Returns "ok" or the error class name for each."""
    barrier = threading.Barrier(len(attempts))
    results: list[str] = [""] * len(attempts)

    def worker(index: int, workspace_id, transaction_id, invoice_id, amount) -> None:
        with Session(engine) as own_session:
            barrier.wait()
            try:
                allocate(
                    own_session, workspace_id=workspace_id, transaction_id=transaction_id, invoice_id=invoice_id,
                    amount_kobo=amount, method="manual", actor_user_id=None,
                )
                own_session.commit()
                results[index] = "ok"
            except OverAllocated:
                own_session.rollback()
                results[index] = "OverAllocated"

    threads = [threading.Thread(target=worker, args=(i, *attempt)) for i, attempt in enumerate(attempts)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return results


def test_two_simultaneous_payments_cannot_both_fill_one_invoice(committed: Engine) -> None:
    with Session(committed) as setup:
        owner = make_owner(setup)
        invoice = make_invoice(setup, owner)
        first = make_transaction(setup, owner, amount_kobo=INVOICE_TOTAL)
        second = make_transaction(setup, owner, amount_kobo=INVOICE_TOTAL)
        ids = (owner.workspace_id, first.id, second.id, invoice.id)
    workspace_id, first_id, second_id, invoice_id = ids

    results = race(committed, [(workspace_id, first_id, invoice_id, INVOICE_TOTAL), (workspace_id, second_id, invoice_id, INVOICE_TOTAL)])

    assert sorted(results) == ["OverAllocated", "ok"]
    with Session(committed) as check:
        assert invoices.paid_totals(check, workspace_id, [invoice_id])[invoice_id] == INVOICE_TOTAL


def test_two_simultaneous_payments_cannot_both_spend_one_bank_line(committed: Engine) -> None:
    with Session(committed) as setup:
        owner = make_owner(setup)
        first_invoice = make_invoice(setup, owner)
        second_invoice = make_invoice(setup, owner)
        credit = make_transaction(setup, owner, amount_kobo=INVOICE_TOTAL)
        workspace_id, credit_id, first_id, second_id = owner.workspace_id, credit.id, first_invoice.id, second_invoice.id

    results = race(committed, [(workspace_id, credit_id, first_id, INVOICE_TOTAL), (workspace_id, credit_id, second_id, INVOICE_TOTAL)])

    assert sorted(results) == ["OverAllocated", "ok"]
    with Session(committed) as check:
        assert allocated_totals(check, workspace_id, [credit_id])[credit_id] == INVOICE_TOTAL


def test_many_simultaneous_part_payments_never_overfill(committed: Engine) -> None:
    # 8 credits of ₦20,000 race for one ₦107,500 invoice: exactly 5 fit (₦100,000), the rest must fail.
    with Session(committed) as setup:
        owner = make_owner(setup)
        invoice = make_invoice(setup, owner)
        credits = [make_transaction(setup, owner, amount_kobo=2_000_000) for _ in range(8)]
        attempts = [(owner.workspace_id, credit.id, invoice.id, 2_000_000) for credit in credits]
        workspace_id, invoice_id = owner.workspace_id, invoice.id

    results = race(committed, attempts)

    assert results.count("ok") == 5
    assert results.count("OverAllocated") == 3
    with Session(committed) as check:
        assert invoices.paid_totals(check, workspace_id, [invoice_id])[invoice_id] == 10_000_000


def test_totals_ignore_other_workspaces(session: Session, owner: User) -> None:
    # Invariant 8 inside the totals helpers: asking with the wrong workspace returns nothing.
    other = make_owner(session, "Kola & Sons")
    invoice = make_invoice(session, owner)
    credit = make_transaction(session, owner, amount_kobo=INVOICE_TOTAL)
    pay(session, owner, credit, invoice, INVOICE_TOTAL)

    assert invoices.paid_totals(session, other.workspace_id, [invoice.id]) == {}
    assert allocated_totals(session, other.workspace_id, [credit.id]) == {}


# --- invariant 2: re-importing a statement adds nothing -----------------------------------------------


def test_reimporting_a_statement_adds_nothing(client, auth_headers: dict, session: Session) -> None:
    from app.transactions.models import Transaction

    statement = (Path(__file__).parent / "fixtures" / "statements" / "bank_a.csv").read_bytes()

    def import_statement() -> dict:
        response = client.post(
            "/api/v1/statements/import", files={"file": ("bank_a.csv", statement, "text/csv")}, headers=auth_headers
        )
        assert response.status_code == 200, response.text
        return response.json()

    first = import_statement()
    rows_after_first = session.exec(select(func.count()).select_from(Transaction)).one()
    second = import_statement()

    assert first["added"] == 4
    assert second["added"] == 0
    assert session.exec(select(func.count()).select_from(Transaction)).one() == rows_after_first


# --- invariant 3: a duplicate Paystack webhook pays once -------------------------------------------------------


def test_concurrent_duplicate_webhooks_pay_once(committed: Engine) -> None:
    # Paystack can deliver the same event twice at the same instant. Both reach the INSERT; the second
    # waits on the unique index until the first commits, then ON CONFLICT DO NOTHING makes it a no-op.
    from datetime import UTC, datetime

    from app.paystack.schemas import VerifiedCharge
    from app.paystack.service import record_charge
    from app.transactions.models import Transaction

    with Session(committed) as setup:
        owner = make_owner(setup)
        invoice = make_invoice(setup, owner)
        workspace_id, invoice_id = owner.workspace_id, invoice.id
    charge = VerifiedCharge(
        reference="ref-race", status="success", currency="NGN", amount_kobo=INVOICE_TOTAL,
        paid_at=datetime(2026, 10, 6, 9, 30, tzinfo=UTC), invoice_id=invoice_id, payer_name=None, channel="card",
    )
    barrier = threading.Barrier(2)
    results: list[str] = ["", ""]

    def worker(index: int) -> None:
        with Session(committed) as own_session:
            barrier.wait()
            results[index] = record_charge(own_session, charge)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert sorted(results) == ["allocated", "duplicate"]
    with Session(committed) as check:
        assert check.exec(select(func.count()).select_from(Transaction)).one() == 1
        assert check.exec(select(func.count()).select_from(PaymentAllocation)).one() == 1
        assert invoices.paid_totals(check, workspace_id, [invoice_id])[invoice_id] == INVOICE_TOTAL


def test_webhook_insert_and_allocation_share_one_db_transaction(committed: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    # If allocate() blows up after the transaction row was inserted, the insert must not survive on its own
    # (D-18). Uses real committing sessions, so a stray commit would leave a row behind.
    import hashlib
    import hmac
    import json
    from datetime import UTC, datetime

    from fastapi.testclient import TestClient

    from app.core.config import settings
    from app.core.db import get_session
    from app.main import app
    from app.paystack import client as paystack_client
    from app.paystack import service as paystack_service
    from app.paystack.schemas import VerifiedCharge
    from app.transactions.models import Transaction

    with Session(committed) as setup:
        owner = make_owner(setup)
        invoice_id = make_invoice(setup, owner).id

    def boom(*args, **kwargs):
        raise RuntimeError("database went away mid-allocation")

    monkeypatch.setattr(settings, "paystack_secret_key", "sk_test_secret")
    monkeypatch.setattr(paystack_service, "allocate", boom)
    monkeypatch.setattr(paystack_client, "verify_transaction", lambda reference: VerifiedCharge(
        reference=reference, status="success", currency="NGN", amount_kobo=INVOICE_TOTAL,
        paid_at=datetime(2026, 10, 6, 9, 30, tzinfo=UTC), invoice_id=invoice_id, payer_name=None, channel="card",
    ))

    def real_session():
        with Session(committed) as own_session:
            yield own_session

    body = json.dumps({"event": "charge.success", "data": {"reference": "ref-crash"}}).encode()
    signature = hmac.new(b"sk_test_secret", body, hashlib.sha512).hexdigest()
    app.dependency_overrides[get_session] = real_session
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            response = test_client.post(
                "/api/v1/webhooks/paystack", content=body,
                headers={"Content-Type": "application/json", "x-paystack-signature": signature},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    with Session(committed) as check:
        assert check.exec(select(func.count()).select_from(Transaction)).one() == 0
        assert check.exec(select(func.count()).select_from(PaymentAllocation)).one() == 0
