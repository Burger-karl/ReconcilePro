"""Feature 6 — POST /api/v1/public/invoices/{token}/pay: start a Paystack payment for what is still owed.

Paystack is never called for real: `initialize` swaps client.initialize_transaction for a fake that
records what it was asked and returns a checkout URL.
"""

import secrets
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.allocations.service import allocate
from app.auth.models import User
from app.core.config import settings
from app.customers.models import Customer
from app.invoices.models import Invoice
from app.paystack import client as paystack_client
from app.paystack.client import PaystackUnavailable
from tests.factories import make_invoice, make_owner, make_transaction

CHECKOUT_URL = "https://checkout.paystack.com/test-access-code"
INVOICE_TOTAL = 10_750_000  # make_invoice default


def publish(session: Session, invoice: Invoice, customer_email: str | None = "kola@kolasons.ng") -> str:
    """Give the invoice a public token (as send does) and its customer an email address."""
    invoice.public_token = secrets.token_urlsafe(32)
    customer = session.get(Customer, invoice.customer_id)
    customer.email = customer_email
    session.add_all([invoice, customer])
    session.commit()
    return invoice.public_token


@pytest.fixture
def initialize(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Every call made to the fake Paystack initialise, in order."""
    calls: list[dict] = []

    def fake_initialize(**kwargs) -> str:
        calls.append(kwargs)
        return CHECKOUT_URL

    monkeypatch.setattr(paystack_client, "initialize_transaction", fake_initialize)
    return calls


@pytest.fixture
def owner(session: Session) -> User:
    return make_owner(session)


def pay(client: TestClient, token: str):
    return client.post(f"/api/v1/public/invoices/{token}/pay")


def test_pay_returns_paystack_checkout_url(client: TestClient, session: Session, owner: User,
                                           initialize: list[dict]) -> None:
    invoice = make_invoice(session, owner)
    token = publish(session, invoice)

    response = pay(client, token)  # no Authorization header: the customer isn't a user

    assert response.status_code == 200, response.text
    # Only the URL: no invoice, customer or workspace ids reach the public page.
    assert response.json() == {"authorization_url": CHECKOUT_URL}
    assert initialize == [{
        "email": "kola@kolasons.ng",
        "amount_kobo": INVOICE_TOTAL,
        "invoice_id": invoice.id,  # the webhook reads it back from metadata
        "callback_url": f"{settings.frontend_url}/i/{token}",
    }]


def test_pay_asks_only_for_what_is_outstanding(client: TestClient, session: Session, owner: User,
                                               initialize: list[dict]) -> None:
    invoice = make_invoice(session, owner)
    token = publish(session, invoice)
    credit = make_transaction(session, owner, amount_kobo=750_000)
    allocate(session, workspace_id=owner.workspace_id, transaction_id=credit.id, invoice_id=invoice.id,
             amount_kobo=750_000, method="manual", actor_user_id=owner.id)
    session.commit()

    response = pay(client, token)

    assert response.status_code == 200
    assert initialize[0]["amount_kobo"] == INVOICE_TOTAL - 750_000
    assert type(initialize[0]["amount_kobo"]) is int  # invariant 1


def test_paid_invoice_cannot_be_paid_again(client: TestClient, session: Session, owner: User,
                                           initialize: list[dict]) -> None:
    invoice = make_invoice(session, owner)
    token = publish(session, invoice)
    credit = make_transaction(session, owner, amount_kobo=INVOICE_TOTAL)
    allocate(session, workspace_id=owner.workspace_id, transaction_id=credit.id, invoice_id=invoice.id,
             amount_kobo=INVOICE_TOTAL, method="manual", actor_user_id=owner.id)
    session.commit()

    response = pay(client, token)

    assert response.status_code == 409
    assert initialize == []


def test_void_invoice_cannot_be_paid(client: TestClient, session: Session, owner: User,
                                     initialize: list[dict]) -> None:
    invoice = make_invoice(session, owner, status="void")
    token = publish(session, invoice)

    response = pay(client, token)

    assert response.status_code == 409
    assert initialize == []


def test_unknown_token_is_404(client: TestClient, initialize: list[dict]) -> None:
    response = pay(client, "not-a-real-token")

    assert response.status_code == 404
    assert initialize == []


def test_customer_without_email_cannot_pay_online(client: TestClient, session: Session, owner: User,
                                                  initialize: list[dict]) -> None:
    # Paystack's initialise requires an email address (D-34).
    invoice = make_invoice(session, owner)
    token = publish(session, invoice, customer_email=None)

    response = pay(client, token)

    assert response.status_code == 409
    assert initialize == []


def test_paystack_unreachable_is_502(client: TestClient, session: Session, owner: User,
                                     monkeypatch: pytest.MonkeyPatch) -> None:
    invoice = make_invoice(session, owner)
    token = publish(session, invoice)

    def down(**kwargs) -> str:
        raise PaystackUnavailable("timed out")

    monkeypatch.setattr(paystack_client, "initialize_transaction", down)

    assert pay(client, token).status_code == 502


def test_pay_then_webhook_round_trip_marks_invoice_paid(client: TestClient, session: Session, owner: User,
                                                        initialize: list[dict]) -> None:
    # The invoice_id we hand to initialise is exactly what record_charge needs back from verify.
    from datetime import UTC, datetime

    from app.invoices import service as invoices
    from app.paystack.schemas import VerifiedCharge
    from app.paystack.service import record_charge

    invoice = make_invoice(session, owner)
    pay(client, publish(session, invoice))
    sent = initialize[0]

    outcome = record_charge(session, VerifiedCharge(
        reference=f"ref-{uuid.uuid4().hex[:8]}", status="success", currency="NGN", amount_kobo=sent["amount_kobo"],
        paid_at=datetime(2026, 10, 6, 9, 30, tzinfo=UTC), invoice_id=sent["invoice_id"],
        payer_name=None, channel="card",
    ))

    assert outcome == "allocated"
    assert invoices.get_invoice(session, owner, invoice.id).status == "paid"


def test_no_database_transaction_is_held_open_during_paystack_call(client: TestClient, session: Session, owner: User,
                                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    # The Paystack call can take up to 10 seconds. Holding a database transaction across it would tie up a
    # pooled connection for nothing, since start_payment only reads.
    invoice = make_invoice(session, owner)
    token = publish(session, invoice)
    seen: list[bool] = []

    def fake_initialize(**kwargs) -> str:
        seen.append(session.in_transaction())
        return CHECKOUT_URL

    monkeypatch.setattr(paystack_client, "initialize_transaction", fake_initialize)

    assert pay(client, token).status_code == 200
    assert seen == [False]


@pytest.mark.parametrize("body", [
    {"status": True, "data": None},
    {"status": True, "data": {"access_code": "abc"}},  # no authorization_url
], ids=["no-data", "no-url"])
def test_initialize_malformed_answer_is_unavailable(monkeypatch: pytest.MonkeyPatch, body: dict) -> None:
    import httpx

    def fake_post(url: str, **kwargs) -> httpx.Response:
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(paystack_client.httpx, "post", fake_post)

    with pytest.raises(PaystackUnavailable):
        paystack_client.initialize_transaction(
            email="kola@kolasons.ng", amount_kobo=INVOICE_TOTAL, invoice_id=uuid.uuid4(), callback_url="http://x/i/t"
        )
