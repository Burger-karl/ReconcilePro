"""Feature 2 — customers: CRUD, alias search, audit trail, and workspace isolation (invariant 8)."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.audit.models import AuditEvent

KOLA = {"name": "Kola & Sons", "email": "accounts@kolasons.ng", "phone": "08031234567", "aliases": ["KOLA AND SONS", "KOLA&SONS LTD"]}


def create_customer(client: TestClient, headers: dict, **overrides) -> dict:
    response = client.post("/api/v1/customers", json={**KOLA, **overrides}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_customer(client: TestClient, auth_headers: dict) -> None:
    body = create_customer(client, auth_headers)

    assert body["name"] == "Kola & Sons"
    assert body["aliases"] == ["KOLA AND SONS", "KOLA&SONS LTD"]
    assert body["outstanding_kobo"] == 0


def test_create_customer_only_name_is_required(client: TestClient, auth_headers: dict) -> None:
    response = client.post("/api/v1/customers", json={"name": "Tunde Print"}, headers=auth_headers)

    assert response.status_code == 201
    assert response.json()["aliases"] == []
    assert response.json()["email"] is None


def test_create_customer_trims_and_drops_blank_aliases(client: TestClient, auth_headers: dict) -> None:
    body = create_customer(client, auth_headers, aliases=["  KOLA AND SONS ", "", "   "])

    assert body["aliases"] == ["KOLA AND SONS"]


def test_create_customer_rejects_blank_name(client: TestClient, auth_headers: dict) -> None:
    response = client.post("/api/v1/customers", json={"name": "  "}, headers=auth_headers)

    assert response.status_code == 422


def test_customers_need_login(client: TestClient) -> None:
    assert client.get("/api/v1/customers").status_code == 401


def test_list_and_search_by_name_or_alias(client: TestClient, auth_headers: dict) -> None:
    create_customer(client, auth_headers)
    create_customer(client, auth_headers, name="Tunde Print", email=None, aliases=["T. ADEBAYO"])

    everyone = client.get("/api/v1/customers", headers=auth_headers).json()
    by_name = client.get("/api/v1/customers", params={"q": "tunde"}, headers=auth_headers).json()
    by_alias = client.get("/api/v1/customers", params={"q": "adebayo"}, headers=auth_headers).json()

    assert everyone["total"] == 2
    assert [c["name"] for c in everyone["items"]] == ["Kola & Sons", "Tunde Print"]  # alphabetical
    assert [c["name"] for c in by_name["items"]] == ["Tunde Print"]
    assert [c["name"] for c in by_alias["items"]] == ["Tunde Print"]


def test_update_customer_writes_audit_event(client: TestClient, auth_headers: dict, session: Session) -> None:
    customer = create_customer(client, auth_headers)

    response = client.patch(
        f"/api/v1/customers/{customer['id']}", json={"aliases": ["KOLA AND SONS", "K&S"]}, headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["aliases"] == ["KOLA AND SONS", "K&S"]
    assert response.json()["name"] == "Kola & Sons"  # untouched fields stay
    events = session.exec(select(AuditEvent).where(AuditEvent.entity_id == customer["id"]).order_by(AuditEvent.created_at)).all()
    assert [e.action for e in events] == ["customer.created", "customer.updated"]
    assert events[1].data["changes"]["aliases"] == {
        "from": ["KOLA AND SONS", "KOLA&SONS LTD"],
        "to": ["KOLA AND SONS", "K&S"],
    }
    assert events[1].actor_user_id is not None


def test_get_customer_includes_their_invoices(client: TestClient, auth_headers: dict) -> None:
    customer = create_customer(client, auth_headers)
    client.post(
        "/api/v1/invoices",
        json={"customer_id": customer["id"], "description": "Oct supplies", "subtotal_kobo": 9_000_000,
              "issue_date": "2026-10-01", "due_date": "2026-10-15"},
        headers=auth_headers,
    )

    body = client.get(f"/api/v1/customers/{customer['id']}", headers=auth_headers).json()

    assert body["name"] == "Kola & Sons"
    assert [i["description"] for i in body["invoices"]] == ["Oct supplies"]


# --- Invariant 8: another workspace sees nothing -------------------------------------------------


def test_other_workspace_cannot_list_customers(client: TestClient, auth_headers: dict, other_auth_headers: dict) -> None:
    create_customer(client, auth_headers)

    assert client.get("/api/v1/customers", headers=other_auth_headers).json() == {"items": [], "total": 0}


def test_other_workspace_gets_404_for_customer(client: TestClient, auth_headers: dict, other_auth_headers: dict) -> None:
    customer = create_customer(client, auth_headers)
    url = f"/api/v1/customers/{customer['id']}"

    # 404, not 403: don't even confirm the id exists.
    assert client.get(url, headers=other_auth_headers).status_code == 404
    assert client.patch(url, json={"name": "Hacked"}, headers=other_auth_headers).status_code == 404
    assert client.get(url, headers=auth_headers).json()["name"] == "Kola & Sons"


def test_unknown_customer_is_404(client: TestClient, auth_headers: dict) -> None:
    response = client.get("/api/v1/customers/00000000-0000-0000-0000-000000000000", headers=auth_headers)

    assert response.status_code == 404


# --- email must be usable for online payment (Paystack needs a real address, D-34) ---------------------


@pytest.mark.parametrize("email", ["not-an-email", "ada@", "@kolasons.ng"])
def test_create_customer_rejects_invalid_email(client: TestClient, auth_headers: dict, email: str) -> None:
    response = client.post("/api/v1/customers", json={"name": "Kola & Sons", "email": email}, headers=auth_headers)

    assert response.status_code == 422


def test_blank_email_means_no_email(client: TestClient, auth_headers: dict) -> None:
    created = client.post("/api/v1/customers", json={"name": "Kola & Sons", "email": "  "}, headers=auth_headers)

    assert created.status_code == 201
    assert created.json()["email"] is None


def test_update_rejects_invalid_email_and_can_clear_it(client: TestClient, auth_headers: dict) -> None:
    customer = create_customer(client, auth_headers)

    bad = client.patch(f"/api/v1/customers/{customer['id']}", json={"email": "nope"}, headers=auth_headers)
    cleared = client.patch(f"/api/v1/customers/{customer['id']}", json={"email": ""}, headers=auth_headers)

    assert bad.status_code == 422
    assert cleared.status_code == 200
    assert cleared.json()["email"] is None
