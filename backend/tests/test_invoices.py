"""Feature 2 — invoices: create (server-side VAT), edit drafts, send, void, derived status,
the public invoice page, audit events, and workspace isolation (invariant 8)."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.audit.models import AuditEvent
from app.invoices.models import Invoice
from app.invoices.service import lagos_today

TODAY = lagos_today()


@pytest.fixture
def customer(client: TestClient, auth_headers: dict) -> dict:
    response = client.post("/api/v1/customers", json={"name": "Kola & Sons"}, headers=auth_headers)
    assert response.status_code == 201
    return response.json()


def invoice_body(customer_id: str, **overrides) -> dict:
    return {
        "customer_id": customer_id,
        "description": "October supplies",
        "subtotal_kobo": 9_000_000,
        "issue_date": TODAY.isoformat(),
        "due_date": (TODAY + timedelta(days=14)).isoformat(),
        **overrides,
    }


def create_invoice(client: TestClient, headers: dict, customer_id: str, **overrides) -> dict:
    response = client.post("/api/v1/invoices", json=invoice_body(customer_id, **overrides), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def send(client: TestClient, headers: dict, invoice_id: str) -> dict:
    response = client.post(f"/api/v1/invoices/{invoice_id}/send", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# --- create ------------------------------------------------------------------------------------


def test_create_invoice_computes_vat_and_total_on_the_server(client: TestClient, auth_headers: dict, customer: dict) -> None:
    body = create_invoice(client, auth_headers, customer["id"])

    assert body["subtotal_kobo"] == 9_000_000
    assert body["vat_kobo"] == 675_000
    assert body["total_kobo"] == 9_675_000
    assert body["paid_kobo"] == 0
    assert body["outstanding_kobo"] == 9_675_000
    assert body["status"] == "draft"
    assert body["customer_name"] == "Kola & Sons"
    assert body["public_token"] is None  # only set when sent


def test_client_cannot_set_vat_or_total(client: TestClient, auth_headers: dict, customer: dict) -> None:
    body = create_invoice(client, auth_headers, customer["id"], vat_kobo=1, total_kobo=1)

    assert body["vat_kobo"] == 675_000
    assert body["total_kobo"] == 9_675_000


def test_invoice_numbers_count_up_per_workspace(
    client: TestClient, auth_headers: dict, other_auth_headers: dict, customer: dict
) -> None:
    first = create_invoice(client, auth_headers, customer["id"])
    second = create_invoice(client, auth_headers, customer["id"])
    other_customer = client.post("/api/v1/customers", json={"name": "Someone"}, headers=other_auth_headers).json()
    other_first = create_invoice(client, other_auth_headers, other_customer["id"])

    assert (first["number"], second["number"]) == ("INV-0001", "INV-0002")
    assert other_first["number"] == "INV-0001"  # numbering restarts in each workspace


def test_each_invoice_gets_a_distinct_payment_reference(client: TestClient, auth_headers: dict, customer: dict) -> None:
    references = {create_invoice(client, auth_headers, customer["id"])["reference"] for _ in range(5)}

    assert len(references) == 5
    assert all(r.startswith("RCN-") for r in references)


@pytest.mark.parametrize(
    "bad",
    [
        {"subtotal_kobo": 0},
        {"subtotal_kobo": -100},
        {"subtotal_kobo": 1500.5},  # invariant 1: money is whole kobo
        {"subtotal_kobo": "90000"},
        {"description": "   "},
    ],
)
def test_create_invoice_rejects_bad_input(client: TestClient, auth_headers: dict, customer: dict, bad: dict) -> None:
    response = client.post("/api/v1/invoices", json=invoice_body(customer["id"], **bad), headers=auth_headers)

    assert response.status_code == 422


def test_due_date_cannot_be_before_issue_date(client: TestClient, auth_headers: dict, customer: dict) -> None:
    response = client.post(
        "/api/v1/invoices",
        json=invoice_body(customer["id"], issue_date="2026-10-10", due_date="2026-10-09"),
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_create_invoice_writes_audit_event(client: TestClient, auth_headers: dict, customer: dict, session: Session) -> None:
    invoice = create_invoice(client, auth_headers, customer["id"])

    event = session.exec(select(AuditEvent).where(AuditEvent.entity_id == invoice["id"])).one()
    assert event.action == "invoice.created"
    assert event.data["total_kobo"] == 9_675_000


# --- edit drafts ---------------------------------------------------------------------------------


def test_patch_draft_recomputes_vat(client: TestClient, auth_headers: dict, customer: dict) -> None:
    invoice = create_invoice(client, auth_headers, customer["id"])

    response = client.patch(f"/api/v1/invoices/{invoice['id']}", json={"subtotal_kobo": 60}, headers=auth_headers)

    assert response.status_code == 200
    assert (response.json()["vat_kobo"], response.json()["total_kobo"]) == (5, 65)


def test_cannot_edit_after_sending(client: TestClient, auth_headers: dict, customer: dict) -> None:
    invoice = create_invoice(client, auth_headers, customer["id"])
    send(client, auth_headers, invoice["id"])

    response = client.patch(f"/api/v1/invoices/{invoice['id']}", json={"subtotal_kobo": 1}, headers=auth_headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "Only draft invoices can be edited"


# --- send ----------------------------------------------------------------------------------------


def test_send_sets_status_sent_at_and_public_token(client: TestClient, auth_headers: dict, customer: dict) -> None:
    invoice = create_invoice(client, auth_headers, customer["id"])

    body = send(client, auth_headers, invoice["id"])

    assert body["status"] == "sent"
    assert body["sent_at"] is not None
    assert len(body["public_token"]) >= 32


def test_cannot_send_twice(client: TestClient, auth_headers: dict, customer: dict) -> None:
    invoice = create_invoice(client, auth_headers, customer["id"])
    send(client, auth_headers, invoice["id"])

    assert client.post(f"/api/v1/invoices/{invoice['id']}/send", headers=auth_headers).status_code == 409


def test_sent_invoice_past_due_is_overdue(client: TestClient, auth_headers: dict, customer: dict) -> None:
    invoice = create_invoice(
        client, auth_headers, customer["id"],
        issue_date=(TODAY - timedelta(days=30)).isoformat(),
        due_date=(TODAY - timedelta(days=1)).isoformat(),
    )

    assert send(client, auth_headers, invoice["id"])["status"] == "overdue"


def test_status_column_only_ever_stores_draft_sent_or_void(
    client: TestClient, auth_headers: dict, customer: dict, session: Session
) -> None:
    # Invariant 5: overdue is shown to the user but never written to the database.
    invoice = create_invoice(
        client, auth_headers, customer["id"],
        issue_date=(TODAY - timedelta(days=30)).isoformat(),
        due_date=(TODAY - timedelta(days=1)).isoformat(),
    )
    send(client, auth_headers, invoice["id"])

    stored = session.get(Invoice, invoice["id"])
    assert stored.status == "sent"


# --- void ----------------------------------------------------------------------------------------


def test_void_needs_a_reason_and_is_audited(client: TestClient, auth_headers: dict, customer: dict, session: Session) -> None:
    invoice = create_invoice(client, auth_headers, customer["id"])
    send(client, auth_headers, invoice["id"])

    no_reason = client.post(f"/api/v1/invoices/{invoice['id']}/void", json={"reason": " "}, headers=auth_headers)
    voided = client.post(f"/api/v1/invoices/{invoice['id']}/void", json={"reason": "Duplicate invoice"}, headers=auth_headers)

    assert no_reason.status_code == 422
    assert voided.status_code == 200
    assert voided.json()["status"] == "void"
    actions = [e.action for e in session.exec(select(AuditEvent).where(AuditEvent.entity_id == invoice["id"]).order_by(AuditEvent.created_at)).all()]
    assert actions == ["invoice.created", "invoice.sent", "invoice.voided"]


def test_cannot_void_twice(client: TestClient, auth_headers: dict, customer: dict) -> None:
    invoice = create_invoice(client, auth_headers, customer["id"])
    url = f"/api/v1/invoices/{invoice['id']}/void"
    client.post(url, json={"reason": "Mistake"}, headers=auth_headers)

    assert client.post(url, json={"reason": "Mistake"}, headers=auth_headers).status_code == 409


# --- list + filters ------------------------------------------------------------------------------


def test_list_filters_on_derived_status(client: TestClient, auth_headers: dict, customer: dict) -> None:
    create_invoice(client, auth_headers, customer["id"])  # draft
    late = create_invoice(
        client, auth_headers, customer["id"],
        issue_date=(TODAY - timedelta(days=30)).isoformat(),
        due_date=(TODAY - timedelta(days=1)).isoformat(),
    )
    send(client, auth_headers, late["id"])

    overdue = client.get("/api/v1/invoices", params={"status": "overdue"}, headers=auth_headers).json()
    drafts = client.get("/api/v1/invoices", params={"status": "draft"}, headers=auth_headers).json()
    everything = client.get("/api/v1/invoices", headers=auth_headers).json()

    assert [i["id"] for i in overdue["items"]] == [late["id"]]
    assert drafts["total"] == 1
    assert everything["total"] == 2


def test_list_search_by_number_reference_or_customer(client: TestClient, auth_headers: dict, customer: dict) -> None:
    invoice = create_invoice(client, auth_headers, customer["id"])

    for q in ["inv-0001", invoice["reference"].lower(), "kola"]:
        found = client.get("/api/v1/invoices", params={"q": q}, headers=auth_headers).json()
        assert [i["id"] for i in found["items"]] == [invoice["id"]], q


# --- public page ---------------------------------------------------------------------------------


def test_public_invoice_page_needs_no_login(client: TestClient, auth_headers: dict, customer: dict) -> None:
    invoice = send(client, auth_headers, create_invoice(client, auth_headers, customer["id"])["id"])

    response = client.get(f"/api/v1/public/invoices/{invoice['public_token']}")

    assert response.status_code == 200
    body = response.json()
    assert body["business_name"] == "Adaeze Foods"
    assert body["customer_name"] == "Kola & Sons"
    assert body["outstanding_kobo"] == 9_675_000
    assert body["reference"] == invoice["reference"]
    # Nothing that would let someone reach other records.
    assert "id" not in body and "customer_id" not in body and "workspace_id" not in body


def test_public_invoice_unknown_token_is_404(client: TestClient) -> None:
    assert client.get("/api/v1/public/invoices/not-a-real-token").status_code == 404


# --- Invariant 8 ---------------------------------------------------------------------------------


def test_other_workspace_cannot_see_or_touch_invoices(
    client: TestClient, auth_headers: dict, other_auth_headers: dict, customer: dict
) -> None:
    invoice = create_invoice(client, auth_headers, customer["id"])
    url = f"/api/v1/invoices/{invoice['id']}"

    assert client.get("/api/v1/invoices", headers=other_auth_headers).json() == {"items": [], "total": 0}
    assert client.get(url, headers=other_auth_headers).status_code == 404
    assert client.patch(url, json={"subtotal_kobo": 1}, headers=other_auth_headers).status_code == 404
    assert client.post(f"{url}/send", headers=other_auth_headers).status_code == 404
    assert client.post(f"{url}/void", json={"reason": "x"}, headers=other_auth_headers).status_code == 404
    assert client.get(url, headers=auth_headers).json()["status"] == "draft"  # untouched


def test_cannot_invoice_another_workspaces_customer(client: TestClient, other_auth_headers: dict, customer: dict) -> None:
    response = client.post("/api/v1/invoices", json=invoice_body(customer["id"]), headers=other_auth_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Customer not found"


def test_customer_outstanding_counts_sent_invoices_only(client: TestClient, auth_headers: dict, customer: dict) -> None:
    create_invoice(client, auth_headers, customer["id"])  # draft: not owed yet
    sent = create_invoice(client, auth_headers, customer["id"], subtotal_kobo=1_000)
    send(client, auth_headers, sent["id"])
    voided = create_invoice(client, auth_headers, customer["id"])
    send(client, auth_headers, voided["id"])
    client.post(f"/api/v1/invoices/{voided['id']}/void", json={"reason": "Wrong"}, headers=auth_headers)

    listed = client.get("/api/v1/customers", headers=auth_headers).json()["items"][0]

    assert listed["outstanding_kobo"] == 1_075


def test_dates_round_trip(client: TestClient, auth_headers: dict, customer: dict) -> None:
    invoice = create_invoice(client, auth_headers, customer["id"], issue_date="2026-10-01", due_date="2026-10-15")

    assert date.fromisoformat(invoice["issue_date"]) == date(2026, 10, 1)
    assert date.fromisoformat(invoice["due_date"]) == date(2026, 10, 15)
