"""Feature 6 — POST /api/v1/webhooks/paystack (docs/API.md, DECISIONS D-30 to D-33).

Paystack is never called for real: `paystack_api` swaps client.verify_transaction for a fake that
returns whatever the test put in `verified`. The webhook body and the verified data are kept
separate on purpose, so tests can prove that only the verified data is trusted (D-30).
"""

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.allocations.models import PaymentAllocation
from app.audit.models import AuditEvent
from app.auth.models import User
from app.core.config import settings
from app.invoices import service as invoices
from app.invoices.models import Invoice
from app.paystack import client as paystack_client
from app.paystack.client import PaystackUnavailable
from app.paystack.schemas import VerifiedCharge
from app.paystack.service import signature_is_valid
from app.transactions.models import Transaction
from tests.conftest import register_headers
from tests.factories import make_invoice, make_owner

TEST_SECRET = "sk_test_reconcile_webhook_secret"
URL = "/api/v1/webhooks/paystack"
INVOICE_TOTAL = 10_750_000  # make_invoice default


# --- helpers ------------------------------------------------------------------------------------------


def sign(body: bytes, secret: str = TEST_SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()


def event_body(reference: str, invoice_id: uuid.UUID | str, amount_kobo: int = INVOICE_TOTAL,
               event: str = "charge.success") -> bytes:
    """What Paystack POSTs to us (only the fields we read)."""
    payload = {
        "event": event,
        "data": {
            "reference": reference,
            "amount": amount_kobo,
            "currency": "NGN",
            "status": "success",
            "channel": "card",
            "metadata": {"invoice_id": str(invoice_id)},
            "customer": {"first_name": "Kola", "last_name": "Adeyemi", "email": "kola@kolasons.ng"},
        },
    }
    return json.dumps(payload).encode()


def post(client: TestClient, body: bytes, signature: str | None = "sign") -> httpx.Response:
    headers = {"Content-Type": "application/json"}
    if signature == "sign":
        headers["x-paystack-signature"] = sign(body)
    elif signature is not None:
        headers["x-paystack-signature"] = signature
    return client.post(URL, content=body, headers=headers)


def charge(reference: str, invoice_id: uuid.UUID | None, amount_kobo: int = INVOICE_TOTAL,
           status: str = "success", currency: str = "NGN") -> VerifiedCharge:
    """What Paystack's verify-transaction endpoint says really happened."""
    return VerifiedCharge(
        reference=reference,
        status=status,
        currency=currency,
        amount_kobo=amount_kobo,
        paid_at=datetime(2026, 10, 6, 9, 30, tzinfo=UTC),
        invoice_id=invoice_id,
        payer_name="Kola Adeyemi",
        channel="card",
    )


def count(session: Session, model) -> int:
    return session.exec(select(func.count()).select_from(model)).one()


def paid(session: Session, invoice: Invoice) -> int:
    return invoices.paid_totals(session, invoice.workspace_id, [invoice.id]).get(invoice.id, 0)


# --- fixtures -----------------------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def webhook_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "paystack_secret_key", TEST_SECRET)


@pytest.fixture
def verified(monkeypatch: pytest.MonkeyPatch) -> dict[str, VerifiedCharge | Exception]:
    """reference -> the VerifiedCharge the fake Paystack returns, or an exception it raises."""
    answers: dict[str, VerifiedCharge | Exception] = {}

    def fake_verify(reference: str) -> VerifiedCharge:
        answer = answers[reference]
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(paystack_client, "verify_transaction", fake_verify)
    return answers


@pytest.fixture
def owner(session: Session) -> User:
    return make_owner(session)


@pytest.fixture
def invoice(session: Session, owner: User) -> Invoice:
    return make_invoice(session, owner)


# --- signature (checked before anything else) ----------------------------------------------------------


def test_signature_is_valid_matches_hmac_sha512() -> None:
    body = b'{"event":"charge.success"}'
    expected = hmac.new(b"secret", body, hashlib.sha512).hexdigest()

    assert signature_is_valid(body, expected, "secret") is True
    assert signature_is_valid(body, expected, "other-secret") is False
    assert signature_is_valid(body + b" ", expected, "secret") is False  # raw bytes, not re-serialised JSON
    assert signature_is_valid(body, None, "secret") is False
    # No secret configured: refuse everything rather than accept an HMAC keyed with "".
    assert signature_is_valid(body, hmac.new(b"", body, hashlib.sha512).hexdigest(), "") is False


def test_missing_signature_returns_401_and_writes_nothing(client: TestClient, session: Session, invoice: Invoice,
                                                          verified: dict) -> None:
    verified["ref-1"] = charge("ref-1", invoice.id)

    response = post(client, event_body("ref-1", invoice.id), signature=None)

    assert response.status_code == 401
    assert count(session, Transaction) == 0


def test_wrong_signature_returns_401_and_writes_nothing(client: TestClient, session: Session, invoice: Invoice,
                                                        verified: dict) -> None:
    verified["ref-1"] = charge("ref-1", invoice.id)
    body = event_body("ref-1", invoice.id)

    response = post(client, body, signature=sign(body, secret="sk_test_someone_else"))

    assert response.status_code == 401
    assert count(session, Transaction) == 0
    assert count(session, PaymentAllocation) == 0


def test_non_ascii_signature_is_401_not_500(client: TestClient) -> None:
    # hmac.compare_digest raises TypeError on non-ASCII str; a junk header must still just be refused.
    body = b'{"event":"charge.success"}'
    assert signature_is_valid(body, "é" * 128, TEST_SECRET) is False

    response = client.post(URL, content=body, headers={"x-paystack-signature": ("é" * 128).encode("latin-1")})

    assert response.status_code == 401


def test_signature_checked_before_json_parsed(client: TestClient) -> None:
    # Garbage with a bad signature must be a 401, not a 400: unauthenticated bytes never reach the parser.
    response = post(client, b"{not json", signature="0" * 128)

    assert response.status_code == 401


def test_signed_but_invalid_json_returns_400(client: TestClient) -> None:
    response = post(client, b"{not json")

    assert response.status_code == 400


# --- what gets recorded ----------------------------------------------------------------------------------


def test_non_charge_event_is_ignored(client: TestClient, session: Session, invoice: Invoice, verified: dict) -> None:
    response = post(client, event_body("ref-1", invoice.id, event="transfer.success"))

    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    assert count(session, Transaction) == 0


def test_charge_success_records_and_allocates(client: TestClient, session: Session, owner: User, invoice: Invoice,
                                              verified: dict) -> None:
    verified["ref-1"] = charge("ref-1", invoice.id)

    response = post(client, event_body("ref-1", invoice.id))

    assert response.status_code == 200, response.text
    assert response.json() == {"status": "allocated"}

    transaction = session.exec(select(Transaction)).one()
    assert transaction.workspace_id == owner.workspace_id
    assert transaction.source == "paystack"
    assert transaction.kind == "credit"  # never "settlement" (invariant 6)
    assert transaction.external_reference == "ref-1"
    assert transaction.amount_kobo == INVOICE_TOTAL
    assert type(transaction.amount_kobo) is int  # invariant 1
    assert transaction.value_date.isoformat() == "2026-10-06"  # paid_at as a Lagos date (D-13)

    allocation = session.exec(select(PaymentAllocation)).one()
    assert allocation.transaction_id == transaction.id
    assert allocation.invoice_id == invoice.id
    assert allocation.amount_kobo == INVOICE_TOTAL
    assert allocation.method == "auto"
    assert allocation.created_by is None  # the system did it

    assert invoices.get_invoice(session, owner, invoice.id).status == "paid"

    actions = session.exec(select(AuditEvent.action).where(AuditEvent.workspace_id == owner.workspace_id)).all()
    assert "allocation.created" in actions
    assert "paystack.payment_received" in actions


def test_duplicate_webhook_pays_once(client: TestClient, session: Session, invoice: Invoice, verified: dict) -> None:
    # Invariant 3: Paystack retries, so the same event can arrive more than once.
    verified["ref-1"] = charge("ref-1", invoice.id)
    body = event_body("ref-1", invoice.id)

    first = post(client, body)
    second = post(client, body)

    assert first.json() == {"status": "allocated"}
    assert second.status_code == 200
    assert second.json() == {"status": "duplicate"}
    assert count(session, Transaction) == 1
    assert count(session, PaymentAllocation) == 1
    assert paid(session, invoice) == INVOICE_TOTAL


def test_uses_verified_amount_not_webhook_amount(client: TestClient, session: Session, invoice: Invoice,
                                                 verified: dict) -> None:
    # D-30: the webhook body is only a prompt to go and ask Paystack. A forged or replayed body
    # claiming a bigger amount must not change what is recorded.
    verified["ref-1"] = charge("ref-1", invoice.id, amount_kobo=5_000_000)

    post(client, event_body("ref-1", invoice.id, amount_kobo=INVOICE_TOTAL))

    assert session.exec(select(Transaction)).one().amount_kobo == 5_000_000
    assert paid(session, invoice) == 5_000_000


def test_verify_not_success_records_nothing(client: TestClient, session: Session, invoice: Invoice,
                                            verified: dict) -> None:
    verified["ref-1"] = charge("ref-1", invoice.id, status="failed")

    response = post(client, event_body("ref-1", invoice.id))

    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    assert count(session, Transaction) == 0


def test_non_ngn_currency_records_nothing(client: TestClient, session: Session, invoice: Invoice,
                                          verified: dict) -> None:
    # Amounts are kobo only if the currency is naira; 10,750,000 cents is not ₦107,500.
    verified["ref-1"] = charge("ref-1", invoice.id, currency="USD")

    response = post(client, event_body("ref-1", invoice.id))

    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    assert count(session, Transaction) == 0


def test_paystack_unreachable_returns_502_and_records_nothing(client: TestClient, session: Session,
                                                              invoice: Invoice, verified: dict) -> None:
    # D-32: a non-2xx makes Paystack retry later; retries are safe because of invariant 3.
    verified["ref-1"] = PaystackUnavailable("timed out")

    response = post(client, event_body("ref-1", invoice.id))

    assert response.status_code == 502
    assert count(session, Transaction) == 0


def test_unknown_invoice_records_nothing(client: TestClient, session: Session, owner: User, verified: dict) -> None:
    # No invoice means no workspace to put the money in.
    missing = uuid.uuid4()
    verified["ref-1"] = charge("ref-1", missing)

    response = post(client, event_body("ref-1", missing))

    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    assert count(session, Transaction) == 0


def test_missing_invoice_id_records_nothing(client: TestClient, session: Session, owner: User,
                                            verified: dict) -> None:
    verified["ref-1"] = charge("ref-1", None)

    response = post(client, event_body("ref-1", "not-a-uuid"))

    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    assert count(session, Transaction) == 0


# --- money arrived but can't be allocated: record it, send it to the queue (D-31) ------------------------


def test_more_than_outstanding_lands_unallocated_in_queue(client: TestClient, session: Session,
                                                          verified: dict) -> None:
    headers = register_headers(client, "ada@adaezefoods.ng", "Adaeze Foods")
    owner = session.exec(select(User).where(User.email == "ada@adaezefoods.ng")).one()
    invoice = make_invoice(session, owner)
    # Paid by card for more than is owed (e.g. a bank transfer paid part of it after the link was opened).
    too_much = INVOICE_TOTAL + 100_000

    verified["ref-1"] = charge("ref-1", invoice.id, amount_kobo=too_much)

    response = post(client, event_body("ref-1", invoice.id, amount_kobo=too_much))

    assert response.status_code == 200
    assert response.json() == {"status": "unallocated"}
    transaction = session.exec(select(Transaction)).one()
    assert transaction.amount_kobo == too_much
    assert count(session, PaymentAllocation) == 0

    queue = client.get("/api/v1/reconciliation/queue", headers=headers).json()["items"]
    assert [item["transaction"]["id"] for item in queue] == [str(transaction.id)]


def test_void_invoice_lands_unallocated(client: TestClient, session: Session, owner: User, verified: dict) -> None:
    void = make_invoice(session, owner, status="void")
    verified["ref-1"] = charge("ref-1", void.id)

    response = post(client, event_body("ref-1", void.id))

    assert response.status_code == 200
    assert response.json() == {"status": "unallocated"}
    assert count(session, Transaction) == 1
    assert count(session, PaymentAllocation) == 0


def test_unallocated_payment_is_still_audited(client: TestClient, session: Session, owner: User,
                                              verified: dict) -> None:
    void = make_invoice(session, owner, status="void")
    verified["ref-1"] = charge("ref-1", void.id)

    post(client, event_body("ref-1", void.id))

    event = session.exec(select(AuditEvent).where(AuditEvent.action == "paystack.payment_received")).one()
    assert event.workspace_id == owner.workspace_id
    assert event.actor_user_id is None
    assert event.data["amount_kobo"] == INVOICE_TOTAL
    assert event.data["reference"] == "ref-1"


# --- invariant 8 ---------------------------------------------------------------------------------------------


def test_transaction_belongs_to_the_invoices_workspace(client: TestClient, session: Session, verified: dict) -> None:
    ada = register_headers(client, "ada@adaezefoods.ng", "Adaeze Foods")
    kola = register_headers(client, "kola@kolasons.ng", "Kola & Sons")
    ada_owner = session.exec(select(User).where(User.email == "ada@adaezefoods.ng")).one()
    invoice = make_invoice(session, ada_owner)
    verified["ref-1"] = charge("ref-1", invoice.id)

    post(client, event_body("ref-1", invoice.id))

    assert client.get("/api/v1/transactions", headers=ada).json()["total"] == 1
    assert client.get("/api/v1/transactions", headers=kola).json()["total"] == 0


# --- invariant 3 holds on every unique index -----------------------------------------------------------------


def test_clash_on_fingerprint_index_is_a_duplicate_not_a_500(client: TestClient, session: Session, owner: User,
                                                             invoice: Invoice, verified: dict) -> None:
    # transactions has TWO unique indexes a Paystack row can hit: (source, external_reference) and
    # (workspace_id, fingerprint). When two copies race, the clash can land on either one. Here we force
    # the fingerprint one: whichever index catches it, a repeat must be "duplicate", never an error.
    from tests.factories import make_transaction

    existing = make_transaction(session, owner, amount_kobo=INVOICE_TOTAL)
    existing.fingerprint = hashlib.sha256(b"paystack|ref-1").hexdigest()
    session.add(existing)
    session.commit()
    verified["ref-1"] = charge("ref-1", invoice.id)

    response = post(client, event_body("ref-1", invoice.id))

    assert response.status_code == 200, response.text
    assert response.json() == {"status": "duplicate"}
    assert count(session, PaymentAllocation) == 0


# --- client.verify_transaction: which Paystack answers mean "retry later" -------------------------------------


def paystack_answers(monkeypatch: pytest.MonkeyPatch, status_code: int, body: dict | None = None) -> None:
    """Make httpx.get return this response, as if Paystack had sent it."""
    def fake_get(url: str, **kwargs) -> httpx.Response:
        return httpx.Response(status_code, json=body or {"status": False, "message": "nope"},
                              request=httpx.Request("GET", url))

    monkeypatch.setattr(paystack_client.httpx, "get", fake_get)


@pytest.mark.parametrize("status_code", [400, 404])
def test_verify_unknown_reference_is_none(monkeypatch: pytest.MonkeyPatch, status_code: int) -> None:
    # Paystack has never heard of this reference (e.g. a forged event): safe to ignore for good.
    paystack_answers(monkeypatch, status_code)

    assert paystack_client.verify_transaction("ref-1") is None


@pytest.mark.parametrize("status_code", [401, 403, 408, 429, 500, 503])
def test_verify_other_failures_mean_retry_later(monkeypatch: pytest.MonkeyPatch, status_code: int) -> None:
    # A revoked key, rate limit or timeout says nothing about the payment. Treating it as "ignored" would
    # answer 200, Paystack would stop retrying, and a real payment would never be recorded.
    paystack_answers(monkeypatch, status_code)

    with pytest.raises(PaystackUnavailable):
        paystack_client.verify_transaction("ref-1")


def test_rate_limited_verify_makes_webhook_answer_502(client: TestClient, session: Session, invoice: Invoice,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    paystack_answers(monkeypatch, 429)

    response = post(client, event_body("ref-1", invoice.id))

    assert response.status_code == 502
    assert count(session, Transaction) == 0


def test_verify_success_is_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    invoice_id = uuid.uuid4()
    paystack_answers(monkeypatch, 200, {"status": True, "data": {
        "reference": "ref-1", "status": "success", "currency": "NGN", "amount": INVOICE_TOTAL,
        "paid_at": "2026-10-06T09:30:00.000Z", "channel": "card", "metadata": {"invoice_id": str(invoice_id)},
        "customer": {"first_name": "Kola", "last_name": "Adeyemi", "email": "kola@kolasons.ng"},
    }})

    verified_charge = paystack_client.verify_transaction("ref-1")

    assert verified_charge == charge("ref-1", invoice_id)


# --- malformed Paystack answers: retry later, never a 500 or a wrong row ---------------------------------------


def good_verify_data(**changes) -> dict:
    data = {
        "reference": "ref-1", "status": "success", "currency": "NGN", "amount": INVOICE_TOTAL,
        "paid_at": "2026-10-06T09:30:00.000Z", "channel": "card", "metadata": {"invoice_id": str(uuid.uuid4())},
        "customer": {"first_name": "Kola", "last_name": "Adeyemi", "email": "kola@kolasons.ng"},
    }
    data.update(changes)
    return data


@pytest.mark.parametrize("body", [
    {"status": True, "data": None},  # no data at all
    {"status": True, "data": good_verify_data(paid_at=None)},  # missing payment time
    {"status": True, "data": good_verify_data(amount="lots")},  # amount not a number
    {"status": True, "data": good_verify_data(amount=107_500.5)},  # half a kobo is not money
    {"status": True, "data": good_verify_data(paid_at="yesterday")},  # unreadable date
], ids=["no-data", "no-paid-at", "amount-text", "amount-fraction", "bad-date"])
def test_verify_malformed_answer_means_retry_later(monkeypatch: pytest.MonkeyPatch, body: dict) -> None:
    paystack_answers(monkeypatch, 200, body)

    with pytest.raises(PaystackUnavailable):
        paystack_client.verify_transaction("ref-1")


def test_verify_non_json_answer_means_retry_later(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, **kwargs) -> httpx.Response:
        return httpx.Response(200, text="<html>Bad gateway</html>", request=httpx.Request("GET", url))

    monkeypatch.setattr(paystack_client.httpx, "get", fake_get)

    with pytest.raises(PaystackUnavailable):
        paystack_client.verify_transaction("ref-1")


def test_malformed_verify_makes_webhook_answer_502(client: TestClient, session: Session, invoice: Invoice,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    paystack_answers(monkeypatch, 200, {"status": True, "data": None})

    response = post(client, event_body("ref-1", invoice.id))

    assert response.status_code == 502
    assert count(session, Transaction) == 0


def test_verify_paid_at_without_timezone_is_read_as_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    # 23:30 UTC is 00:30 next day in Lagos (D-13). Without this, a naive time would be read in the server's zone.
    paystack_answers(monkeypatch, 200, {"status": True, "data": good_verify_data(paid_at="2026-10-06T23:30:00")})

    verified_charge = paystack_client.verify_transaction("ref-1")

    assert verified_charge.paid_at == datetime(2026, 10, 6, 23, 30, tzinfo=UTC)


# --- long references are stored, not refused ---------------------------------------------------------------------


def test_long_paystack_reference_is_recorded(client: TestClient, session: Session, invoice: Invoice,
                                             verified: dict) -> None:
    # Payments started outside our pay endpoint can carry any reference the merchant chose. A too-narrow column
    # would fail the insert, answer 500, and Paystack would retry forever without the money ever landing.
    reference = "R" * 150
    verified[reference] = charge(reference, invoice.id)

    response = post(client, event_body(reference, invoice.id))

    assert response.status_code == 200, response.text
    assert response.json() == {"status": "allocated"}
    assert session.exec(select(Transaction)).one().external_reference == reference


# --- a refused allocation can't leave half of itself behind -----------------------------------------------------


def test_allocation_refused_after_writing_leaves_nothing_behind(client: TestClient, session: Session, owner: User,
                                                               invoice: Invoice, verified: dict,
                                                               monkeypatch: pytest.MonkeyPatch) -> None:
    # Today allocate() checks everything before it writes, so a refusal leaves the session clean. If a future
    # edit moved a check after the INSERT, the webhook's commit would save a half-made allocation. The savepoint
    # around allocate() must undo whatever it wrote, while keeping the Paystack transaction and its audit row.
    from app.allocations import service as allocations
    from app.paystack import service as paystack_service

    def writes_then_refuses(session: Session, **kwargs):
        allocations.allocate(session, **kwargs)  # the allocation row and its audit row are flushed
        raise allocations.OverAllocated("invoice", 0)

    monkeypatch.setattr(paystack_service, "allocate", writes_then_refuses)
    verified["ref-1"] = charge("ref-1", invoice.id)

    response = post(client, event_body("ref-1", invoice.id))

    assert response.json() == {"status": "unallocated"}
    assert count(session, Transaction) == 1  # the money is still recorded (D-31)
    assert count(session, PaymentAllocation) == 0
    actions = session.exec(select(AuditEvent.action).where(AuditEvent.workspace_id == owner.workspace_id)).all()
    assert actions == ["paystack.payment_received"]  # no orphan allocation.created
    assert paid(session, invoice) == 0


# --- sequences the reviewer walked through ---------------------------------------------------------------------


def test_two_checkouts_paid_for_one_invoice_fill_it_exactly_once(client: TestClient, session: Session,
                                                                 invoice: Invoice, verified: dict) -> None:
    # The customer double-clicks "Pay", gets two checkouts and completes both. Each is a different Paystack
    # reference for the full amount. The first pays the invoice; the second can't over-fill it (invariant 4)
    # and waits in the queue for the accountant to refund or reassign (D-31).
    verified["ref-1"] = charge("ref-1", invoice.id)
    verified["ref-2"] = charge("ref-2", invoice.id)

    first = post(client, event_body("ref-1", invoice.id))
    second = post(client, event_body("ref-2", invoice.id))

    assert first.json() == {"status": "allocated"}
    assert second.json() == {"status": "unallocated"}
    assert count(session, Transaction) == 2
    assert count(session, PaymentAllocation) == 1
    assert paid(session, invoice) == INVOICE_TOTAL


def test_retry_after_accountant_reversed_the_allocation_changes_nothing(client: TestClient, session: Session,
                                                                         owner: User, invoice: Invoice,
                                                                         verified: dict) -> None:
    # The accountant undoes the automatic allocation (e.g. it was the wrong invoice). A late Paystack retry of the
    # same event must not quietly put it back: the reference is already recorded, so it is a duplicate.
    from app.allocations.service import reverse

    verified["ref-1"] = charge("ref-1", invoice.id)
    body = event_body("ref-1", invoice.id)
    post(client, body)
    allocation = session.exec(select(PaymentAllocation)).one()
    reverse(session, workspace_id=owner.workspace_id, allocation_id=allocation.id, actor_user_id=owner.id,
            reason="Customer meant a different invoice")
    session.commit()

    retry = post(client, body)

    assert retry.json() == {"status": "duplicate"}
    assert count(session, PaymentAllocation) == 1  # only the reversed one
    assert paid(session, invoice) == 0


# --- client.verify_transaction: field spellings and metadata shapes ----------------------------------------------


def test_verify_accepts_the_paidAt_spelling(monkeypatch: pytest.MonkeyPatch) -> None:
    data = good_verify_data(paid_at=None)
    data["paidAt"] = "2026-10-06T09:30:00.000Z"
    paystack_answers(monkeypatch, 200, {"status": True, "data": data})

    assert paystack_client.verify_transaction("ref-1").paid_at == datetime(2026, 10, 6, 9, 30, tzinfo=UTC)


@pytest.mark.parametrize("metadata", ["", None, {}, {"invoice_id": "not-a-uuid"}, {"invoice_id": None}],
                         ids=["empty-string", "null", "empty-dict", "bad-uuid", "null-id"])
def test_verify_payment_not_started_by_us_has_no_invoice(monkeypatch: pytest.MonkeyPatch, metadata) -> None:
    # Payments made on the same Paystack account without our pay button carry whatever metadata they were
    # given. That is not an error: the charge is read, with no invoice, and record_charge ignores it.
    paystack_answers(monkeypatch, 200, {"status": True, "data": good_verify_data(metadata=metadata)})

    verified_charge = paystack_client.verify_transaction("ref-1")

    assert verified_charge is not None
    assert verified_charge.invoice_id is None
