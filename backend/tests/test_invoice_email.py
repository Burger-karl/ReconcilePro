"""Emailing the invoice link to the customer (DECISIONS D-60).

Sending an invoice emails its public link when the customer has an email address; POST /invoices/{id}/email
sends it again while money is still owed. The email is never really sent: app.email.service.send_email is
replaced by a function that keeps each message, like the password reset tests.
"""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.audit.models import AuditEvent
from app.core.config import settings
from app.core.time import lagos_today
from app.email import service as email_service

TODAY = lagos_today()


@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    sent: list[dict] = []
    monkeypatch.setattr(email_service, "send_email", lambda **message: sent.append(message))
    return sent


def new_customer(client: TestClient, headers: dict, email: str | None = "accounts@kolasons.ng") -> dict:
    response = client.post("/api/v1/customers", json={"name": "Kola & Sons", "email": email}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def draft(client: TestClient, headers: dict, customer_id: str) -> dict:
    response = client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "description": "October supplies",
            "subtotal_kobo": 9_000_000,  # + 7.5% VAT = 9,675,000 kobo
            "issue_date": TODAY.isoformat(),
            "due_date": (TODAY + timedelta(days=14)).isoformat(),
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def send(client: TestClient, headers: dict, invoice_id: str) -> dict:
    response = client.post(f"/api/v1/invoices/{invoice_id}/send", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# --- emailed when sent ---------------------------------------------------------------------------------


def test_sending_emails_the_customer_the_payment_link(
    client: TestClient, auth_headers: dict, outbox: list[dict]
) -> None:
    invoice = draft(client, auth_headers, new_customer(client, auth_headers)["id"])

    sent = send(client, auth_headers, invoice["id"])

    assert sent["emailed_to"] == "accounts@kolasons.ng"
    assert len(outbox) == 1
    message = outbox[0]
    assert message["to"] == "accounts@kolasons.ng"
    assert sent["number"] in message["subject"]
    assert "Adaeze Foods" in message["subject"]  # the business name, from the workspace
    assert f"{settings.frontend_url}/i/{sent['public_token']}" in message["text"]
    assert "₦96,750.00" in message["text"]  # what is owed, formatted from kobo
    assert sent["reference"] in message["text"]  # for paying by bank transfer


def test_sending_without_a_customer_email_sends_nothing(
    client: TestClient, auth_headers: dict, outbox: list[dict]
) -> None:
    invoice = draft(client, auth_headers, new_customer(client, auth_headers, email=None)["id"])

    sent = send(client, auth_headers, invoice["id"])

    assert sent["status"] == "sent"
    assert sent["emailed_to"] is None
    assert outbox == []


def test_sent_audit_event_records_where_it_was_emailed(
    client: TestClient, auth_headers: dict, session: Session, outbox: list[dict]
) -> None:
    invoice = draft(client, auth_headers, new_customer(client, auth_headers)["id"])
    send(client, auth_headers, invoice["id"])

    event = session.exec(select(AuditEvent).where(AuditEvent.action == "invoice.sent")).one()
    assert event.data["emailed_to"] == "accounts@kolasons.ng"


# --- emailing again -------------------------------------------------------------------------------------


def test_email_again_resends_the_link_and_is_audited(
    client: TestClient, auth_headers: dict, session: Session, outbox: list[dict]
) -> None:
    invoice = send(client, auth_headers, draft(client, auth_headers, new_customer(client, auth_headers)["id"])["id"])

    response = client.post(f"/api/v1/invoices/{invoice['id']}/email", headers=auth_headers)

    assert response.status_code == 202, response.text
    assert response.json() == {"emailed_to": "accounts@kolasons.ng"}
    assert len(outbox) == 2
    assert outbox[1]["text"] == outbox[0]["text"]
    event = session.exec(select(AuditEvent).where(AuditEvent.action == "invoice.emailed")).one()
    assert event.data == {"number": invoice["number"], "emailed_to": "accounts@kolasons.ng"}


def test_email_again_uses_the_customers_current_email(
    client: TestClient, auth_headers: dict, outbox: list[dict]
) -> None:
    customer = new_customer(client, auth_headers)
    invoice = send(client, auth_headers, draft(client, auth_headers, customer["id"])["id"])
    client.patch(f"/api/v1/customers/{customer['id']}", json={"email": "pay@kolasons.ng"}, headers=auth_headers)

    response = client.post(f"/api/v1/invoices/{invoice['id']}/email", headers=auth_headers)

    assert response.json() == {"emailed_to": "pay@kolasons.ng"}
    assert outbox[-1]["to"] == "pay@kolasons.ng"


def test_email_again_refuses_a_draft(client: TestClient, auth_headers: dict, outbox: list[dict]) -> None:
    invoice = draft(client, auth_headers, new_customer(client, auth_headers)["id"])

    response = client.post(f"/api/v1/invoices/{invoice['id']}/email", headers=auth_headers)

    assert response.status_code == 409
    assert outbox == []


def test_email_again_refuses_a_void_invoice(client: TestClient, auth_headers: dict, outbox: list[dict]) -> None:
    invoice = send(client, auth_headers, draft(client, auth_headers, new_customer(client, auth_headers)["id"])["id"])
    client.post(f"/api/v1/invoices/{invoice['id']}/void", json={"reason": "Raised twice"}, headers=auth_headers)

    response = client.post(f"/api/v1/invoices/{invoice['id']}/email", headers=auth_headers)

    assert response.status_code == 409
    assert len(outbox) == 1  # only the email from sending


def test_email_again_refuses_when_customer_has_no_email(
    client: TestClient, auth_headers: dict, outbox: list[dict]
) -> None:
    invoice = send(client, auth_headers, draft(client, auth_headers, new_customer(client, auth_headers, email=None)["id"])["id"])

    response = client.post(f"/api/v1/invoices/{invoice['id']}/email", headers=auth_headers)

    assert response.status_code == 409
    assert "email" in response.json()["detail"].lower()
    assert outbox == []


def test_other_workspace_cannot_email_the_invoice(
    client: TestClient, auth_headers: dict, other_auth_headers: dict, outbox: list[dict]
) -> None:
    invoice = send(client, auth_headers, draft(client, auth_headers, new_customer(client, auth_headers)["id"])["id"])

    response = client.post(f"/api/v1/invoices/{invoice['id']}/email", headers=other_auth_headers)

    assert response.status_code == 404
    assert len(outbox) == 1


def test_email_needs_login(client: TestClient) -> None:
    assert client.post("/api/v1/invoices/00000000-0000-0000-0000-000000000000/email").status_code == 401
