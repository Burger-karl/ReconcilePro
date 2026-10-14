"""Bank details for transfers and the payment date on the public invoice page (DECISIONS D-61).

The owner saves the business bank account once (PUT /workspace/bank-details); every public invoice then
shows it next to the reference to quote. The public page also says when the invoice was last paid.
"""

import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.allocations import service as allocations
from app.audit.models import AuditEvent
from app.auth.models import User
from app.core.security import create_access_token, hash_password
from app.core.time import lagos_today
from app.transactions.models import Transaction

TODAY = lagos_today()
URL = "/api/v1/workspace/bank-details"
GTBANK = {"bank_name": "GTBank", "bank_account_number": "0123456789", "bank_account_name": "Adaeze Foods Ltd"}


def workspace_id(client: TestClient, headers: dict) -> uuid.UUID:
    return uuid.UUID(client.get("/api/v1/auth/me", headers=headers).json()["workspace"]["id"])


def sent_invoice(client: TestClient, headers: dict) -> dict:
    customer = client.post("/api/v1/customers", json={"name": "Kola & Sons"}, headers=headers).json()
    created = client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer["id"],
            "description": "October supplies",
            "subtotal_kobo": 9_000_000,  # + 7.5% VAT = 9,675,000 kobo
            "issue_date": TODAY.isoformat(),
            "due_date": (TODAY + timedelta(days=14)).isoformat(),
        },
        headers=headers,
    ).json()
    response = client.post(f"/api/v1/invoices/{created['id']}/send", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def pay(session: Session, client: TestClient, headers: dict, invoice: dict, kobo: int, days_ago: int):
    """A bank credit dated `days_ago`, allocated to `invoice` through allocate() (invariant 4)."""
    workspace = workspace_id(client, headers)
    credit = Transaction(
        workspace_id=workspace, source="bank_statement", kind="credit", value_date=TODAY - timedelta(days=days_ago),
        amount_kobo=kobo, narration=f"NIP/KOLA AND SONS/{invoice['reference']}", fingerprint=uuid.uuid4().hex * 2,
    )
    session.add(credit)
    session.flush()
    allocation = allocations.allocate(
        session, workspace_id=workspace, transaction_id=credit.id, invoice_id=uuid.UUID(invoice["id"]),
        amount_kobo=kobo, method="manual", actor_user_id=None,
    )
    session.flush()
    return allocation


def public(client: TestClient, invoice: dict) -> dict:
    return client.get(f"/api/v1/public/invoices/{invoice['public_token']}").json()


# --- saving bank details ---------------------------------------------------------------------------------


def test_owner_saves_bank_details_and_me_returns_them(client: TestClient, auth_headers: dict) -> None:
    response = client.put(URL, json=GTBANK, headers=auth_headers)

    assert response.status_code == 200, response.text
    workspace = client.get("/api/v1/auth/me", headers=auth_headers).json()["workspace"]
    assert {key: workspace[key] for key in GTBANK} == GTBANK


def test_new_workspace_has_no_bank_details(client: TestClient, auth_headers: dict) -> None:
    workspace = client.get("/api/v1/auth/me", headers=auth_headers).json()["workspace"]

    assert workspace["bank_name"] is None
    assert workspace["bank_account_number"] is None
    assert workspace["bank_account_name"] is None


def test_spaces_are_trimmed(client: TestClient, auth_headers: dict) -> None:
    body = {"bank_name": "  GTBank ", "bank_account_number": " 0123456789 ", "bank_account_name": " Adaeze Foods Ltd "}

    assert client.put(URL, json=body, headers=auth_headers).json()["bank_account_number"] == "0123456789"


@pytest.mark.parametrize("number", ["012345678", "01234567890", "01234abcde", ""])
def test_account_number_must_be_ten_digits(client: TestClient, auth_headers: dict, number: str) -> None:
    # Nigerian bank accounts are 10-digit NUBAN numbers; a typo here sends customers' money nowhere.
    response = client.put(URL, json={**GTBANK, "bank_account_number": number}, headers=auth_headers)

    assert response.status_code == 422


@pytest.mark.parametrize("field", ["bank_name", "bank_account_name"])
def test_bank_and_account_name_are_required(client: TestClient, auth_headers: dict, field: str) -> None:
    assert client.put(URL, json={**GTBANK, field: "  "}, headers=auth_headers).status_code == 422


def test_changing_bank_details_is_audited_with_before_and_after(
    client: TestClient, auth_headers: dict, session: Session
) -> None:
    client.put(URL, json=GTBANK, headers=auth_headers)
    client.put(URL, json={**GTBANK, "bank_account_number": "9876543210"}, headers=auth_headers)

    events = session.exec(
        select(AuditEvent)
        .where(AuditEvent.action == "workspace.bank_details_updated")
        .order_by(AuditEvent.created_at)
    ).all()
    assert len(events) == 2
    assert events[0].data == {"before": None, "after": GTBANK}
    assert events[1].data == {"before": GTBANK, "after": {**GTBANK, "bank_account_number": "9876543210"}}
    assert events[1].entity_type == "workspace"


def test_member_cannot_change_bank_details(client: TestClient, auth_headers: dict, session: Session) -> None:
    # Where customers send money is the owner's call only.
    member = User(
        workspace_id=workspace_id(client, auth_headers), email="clerk@adaezefoods.ng",
        password_hash=hash_password("correct-horse-1"), role="member",
    )
    session.add(member)
    session.flush()
    member_headers = {"Authorization": f"Bearer {create_access_token(member.id, token_version=0)}"}

    response = client.put(URL, json=GTBANK, headers=member_headers)

    assert response.status_code == 403
    assert client.get("/api/v1/auth/me", headers=auth_headers).json()["workspace"]["bank_name"] is None


def test_bank_details_need_login(client: TestClient) -> None:
    assert client.put(URL, json=GTBANK).status_code == 401


def test_saving_changes_only_your_own_workspace(
    client: TestClient, auth_headers: dict, other_auth_headers: dict
) -> None:
    client.put(URL, json=GTBANK, headers=other_auth_headers)

    assert client.get("/api/v1/auth/me", headers=auth_headers).json()["workspace"]["bank_name"] is None


# --- the public invoice page -------------------------------------------------------------------------------


def test_public_invoice_shows_the_business_bank_details(client: TestClient, auth_headers: dict) -> None:
    client.put(URL, json=GTBANK, headers=auth_headers)
    invoice = sent_invoice(client, auth_headers)

    body = public(client, invoice)

    assert {key: body[key] for key in GTBANK} == GTBANK


def test_public_invoice_without_bank_details_says_so_with_nulls(client: TestClient, auth_headers: dict) -> None:
    body = public(client, sent_invoice(client, auth_headers))

    assert body["bank_name"] is None and body["bank_account_number"] is None and body["bank_account_name"] is None


def test_unpaid_invoice_has_no_payment_date(client: TestClient, auth_headers: dict) -> None:
    assert public(client, sent_invoice(client, auth_headers))["last_paid_on"] is None


def test_payment_date_is_the_latest_payment(client: TestClient, auth_headers: dict, session: Session) -> None:
    invoice = sent_invoice(client, auth_headers)
    pay(session, client, auth_headers, invoice, 4_000_000, days_ago=5)
    pay(session, client, auth_headers, invoice, 5_675_000, days_ago=2)  # the rest: now fully paid

    body = public(client, invoice)

    assert body["status"] == "paid"
    assert body["last_paid_on"] == (TODAY - timedelta(days=2)).isoformat()


def test_reversed_payment_does_not_count_as_paid_on(
    client: TestClient, auth_headers: dict, session: Session
) -> None:
    invoice = sent_invoice(client, auth_headers)
    pay(session, client, auth_headers, invoice, 4_000_000, days_ago=5)
    wrong = pay(session, client, auth_headers, invoice, 1_000_000, days_ago=1)
    client.post(f"/api/v1/allocations/{wrong.id}/reverse", json={"reason": "Wrong invoice"}, headers=auth_headers)

    assert public(client, invoice)["last_paid_on"] == (TODAY - timedelta(days=5)).isoformat()
