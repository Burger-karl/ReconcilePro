"""Feature 5 — auto-matching on import, the exception queue, accept / reject / manual allocate / reverse.

Statements are built on the fly in bank_b format so narrations can quote each invoice's real
(random) payment reference.
"""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.allocations.models import PaymentAllocation
from app.audit.models import AuditEvent
from app.invoices.service import lagos_today

TODAY = lagos_today()


def statement(*lines: tuple[str, int]) -> bytes:
    """bank_b CSV with one credit per (narration, kobo) line, all dated today."""
    rows = ["DATE POSTED,VALUE DATE,DESCRIPTION,DEBIT,CREDIT"]
    for narration, kobo in lines:
        day = TODAY.strftime("%Y/%m/%d")
        rows.append(f"{day},{day},{narration},,{kobo // 100}.{kobo % 100:02d}")
    return ("\n".join(rows) + "\n").encode()


def import_statement(client: TestClient, headers: dict, *lines: tuple[str, int]) -> dict:
    response = client.post(
        "/api/statements/import", files={"file": ("s.csv", statement(*lines), "text/csv")}, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


def sent_invoice(client: TestClient, headers: dict, customer_name: str = "Kola & Sons", subtotal_kobo: int = 9_000_000,
                 aliases: list[str] | None = None) -> dict:
    customer = client.post("/api/customers", json={"name": customer_name, "aliases": aliases or []}, headers=headers).json()
    invoice = client.post(
        "/api/invoices",
        json={"customer_id": customer["id"], "description": "Supplies", "subtotal_kobo": subtotal_kobo,
              "issue_date": TODAY.isoformat(), "due_date": (TODAY + timedelta(days=14)).isoformat()},
        headers=headers,
    ).json()
    response = client.post(f"/api/invoices/{invoice['id']}/send", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()  # total = subtotal + 7.5% VAT


def queue(client: TestClient, headers: dict) -> list[dict]:
    response = client.get("/api/reconciliation/queue", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def invoice_status(client: TestClient, headers: dict, invoice_id: str) -> str:
    return client.get(f"/api/invoices/{invoice_id}", headers=headers).json()["status"]


# --- auto-match on import ---------------------------------------------------------------------------------


def test_import_auto_allocates_exact_reference(client: TestClient, auth_headers: dict, session: Session) -> None:
    invoice = sent_invoice(client, auth_headers)

    result = import_statement(client, auth_headers, (f"NIP/KOLA AND SONS/{invoice['reference']}", 9_675_000))

    assert (result["auto_allocated"], result["needs_review"]) == (1, 0)
    assert invoice_status(client, auth_headers, invoice["id"]) == "paid"
    allocation = session.exec(select(PaymentAllocation)).one()
    assert (allocation.method, allocation.created_by) == ("auto", None)  # the system did it
    assert queue(client, auth_headers) == []


def test_import_auto_allocates_a_part_payment_by_reference(client: TestClient, auth_headers: dict) -> None:
    invoice = sent_invoice(client, auth_headers)

    import_statement(client, auth_headers, (f"PART PAYMENT {invoice['reference'].lower()}", 5_000_000))

    detail = client.get(f"/api/invoices/{invoice['id']}", headers=auth_headers).json()
    assert (detail["status"], detail["outstanding_kobo"]) == ("part_paid", 4_675_000)


def test_reference_with_too_much_money_goes_to_the_queue(client: TestClient, auth_headers: dict) -> None:
    invoice = sent_invoice(client, auth_headers)

    result = import_statement(client, auth_headers, (f"NIP/KOLA AND SONS/{invoice['reference']}", 10_000_000))

    assert (result["auto_allocated"], result["needs_review"]) == (0, 1)
    item = queue(client, auth_headers)[0]
    assert item["candidates"][0]["invoice_id"] == invoice["id"]
    assert item["candidates"][0]["reference_match"] is True


def test_settlements_are_not_matched_or_queued(client: TestClient, auth_headers: dict) -> None:
    invoice = sent_invoice(client, auth_headers)

    result = import_statement(client, auth_headers, (f"PAYSTACK SETTLEMENT {invoice['reference']}", 9_675_000))

    assert (result["settlements"], result["auto_allocated"], result["needs_review"]) == (1, 0, 0)
    assert queue(client, auth_headers) == []
    assert invoice_status(client, auth_headers, invoice["id"]) == "sent"


def test_auto_match_endpoint_catches_up_after_an_invoice_is_sent(client: TestClient, auth_headers: dict) -> None:
    # The customer paid quoting a reference while the invoice was still a draft (drafts are never
    # candidates). Once the invoice is sent, re-running auto-match allocates it.
    customer = client.post("/api/customers", json={"name": "Kola & Sons"}, headers=auth_headers).json()
    draft = client.post(
        "/api/invoices",
        json={"customer_id": customer["id"], "description": "Supplies", "subtotal_kobo": 9_000_000,
              "issue_date": TODAY.isoformat(), "due_date": (TODAY + timedelta(days=14)).isoformat()},
        headers=auth_headers,
    ).json()
    first = import_statement(client, auth_headers, (f"NIP/KOLA AND SONS/{draft['reference']}", 9_675_000))
    assert (first["auto_allocated"], first["needs_review"]) == (0, 1)
    client.post(f"/api/invoices/{draft['id']}/send", headers=auth_headers)

    response = client.post("/api/reconciliation/auto-match", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {"auto_allocated": 1}
    assert invoice_status(client, auth_headers, draft["id"]) == "paid"
    assert client.post("/api/reconciliation/auto-match", headers=auth_headers).json() == {"auto_allocated": 0}


# --- the queue ----------------------------------------------------------------------------------------------


def test_queue_suggests_a_strong_match(client: TestClient, auth_headers: dict) -> None:
    invoice = sent_invoice(client, auth_headers)
    import_statement(client, auth_headers, ("NIP/KOLA AND SONS/OCT SUPPLIES", 9_675_000))

    items = queue(client, auth_headers)

    assert len(items) == 1
    item = items[0]
    assert item["transaction"]["unallocated_kobo"] == 9_675_000
    assert item["suggested_invoice_id"] == invoice["id"]
    top = item["candidates"][0]
    assert (top["score"], top["breakdown"]) == (100, {"amount": 50, "name": 30, "date": 20})
    assert top["invoice_number"] == invoice["number"]
    assert top["customer_name"] == "Kola & Sons"
    assert top["reasons"]


def test_queue_without_a_clear_winner_has_no_suggestion(client: TestClient, auth_headers: dict) -> None:
    sent_invoice(client, auth_headers)
    sent_invoice(client, auth_headers)  # identical second invoice for the same customer name
    import_statement(client, auth_headers, ("NIP/KOLA AND SONS/OCT", 9_675_000))

    item = queue(client, auth_headers)[0]

    assert item["suggested_invoice_id"] is None
    assert len(item["candidates"]) == 2


# --- accept / manual allocate ------------------------------------------------------------------------------


def accept(client: TestClient, headers: dict, transaction_id: str, invoice_id: str, amount_kobo: int, method: str = "suggested"):
    return client.post(
        "/api/reconciliation/allocate",
        json={"transaction_id": transaction_id, "invoice_id": invoice_id, "amount_kobo": amount_kobo, "method": method},
        headers=headers,
    )


def test_accepting_a_suggestion_pays_the_invoice_and_clears_the_queue(
    client: TestClient, auth_headers: dict, session: Session
) -> None:
    invoice = sent_invoice(client, auth_headers)
    import_statement(client, auth_headers, ("NIP/KOLA AND SONS/OCT", 9_675_000))
    item = queue(client, auth_headers)[0]

    response = accept(client, auth_headers, item["transaction"]["id"], invoice["id"], 9_675_000)

    assert response.status_code == 201
    assert response.json()["method"] == "suggested"
    assert invoice_status(client, auth_headers, invoice["id"]) == "paid"
    assert queue(client, auth_headers) == []
    assert session.exec(select(PaymentAllocation)).one().created_by is not None  # a person did it


def test_split_one_credit_across_two_invoices(client: TestClient, auth_headers: dict) -> None:
    first = sent_invoice(client, auth_headers, subtotal_kobo=1_000_000)  # total 1,075,000
    second = sent_invoice(client, auth_headers, customer_name="Tunde Print", subtotal_kobo=2_000_000)  # 2,150,000
    import_statement(client, auth_headers, ("NIP/KOLA AND SONS/TWO INVOICES", 3_225_000))
    transaction_id = queue(client, auth_headers)[0]["transaction"]["id"]

    assert accept(client, auth_headers, transaction_id, first["id"], 1_075_000, "manual").status_code == 201
    assert queue(client, auth_headers)[0]["transaction"]["unallocated_kobo"] == 2_150_000  # still queued, less left
    assert accept(client, auth_headers, transaction_id, second["id"], 2_150_000, "manual").status_code == 201
    assert queue(client, auth_headers) == []


def test_over_allocation_is_409_with_a_clear_message(client: TestClient, auth_headers: dict) -> None:
    invoice = sent_invoice(client, auth_headers)
    import_statement(client, auth_headers, ("NIP/KOLA AND SONS/OCT", 5_000_000))
    transaction_id = queue(client, auth_headers)[0]["transaction"]["id"]

    response = accept(client, auth_headers, transaction_id, invoice["id"], 5_000_001, "manual")

    assert response.status_code == 409
    assert response.json()["detail"] == "Amount is more than is left on the bank line"


@pytest.mark.parametrize("bad", [{"amount_kobo": 0}, {"amount_kobo": 1.5}, {"method": "auto"}, {"method": "magic"}])
def test_allocate_rejects_bad_input(client: TestClient, auth_headers: dict, bad: dict) -> None:
    # People can't claim the "auto" method: only the system auto-matches.
    invoice = sent_invoice(client, auth_headers)
    import_statement(client, auth_headers, ("NIP/KOLA AND SONS/OCT", 9_675_000))
    transaction_id = queue(client, auth_headers)[0]["transaction"]["id"]
    body = {"transaction_id": transaction_id, "invoice_id": invoice["id"], "amount_kobo": 1_000, "method": "manual", **bad}

    assert client.post("/api/reconciliation/allocate", json=body, headers=auth_headers).status_code == 422


# --- reject ---------------------------------------------------------------------------------------------


def test_rejected_candidate_is_not_suggested_again(client: TestClient, auth_headers: dict, session: Session) -> None:
    invoice = sent_invoice(client, auth_headers)
    import_statement(client, auth_headers, ("NIP/KOLA AND SONS/OCT", 9_675_000))
    transaction_id = queue(client, auth_headers)[0]["transaction"]["id"]

    response = client.post(
        "/api/reconciliation/reject", json={"transaction_id": transaction_id, "invoice_id": invoice["id"]}, headers=auth_headers
    )

    assert response.status_code == 204
    item = queue(client, auth_headers)[0]  # the credit still needs a home...
    assert item["candidates"] == []  # ...but not that invoice
    assert item["suggested_invoice_id"] is None
    assert session.exec(select(AuditEvent).where(AuditEvent.action == "match.rejected")).one()


# --- reverse ---------------------------------------------------------------------------------------------


def test_reverse_puts_the_credit_back_in_the_queue(client: TestClient, auth_headers: dict) -> None:
    invoice = sent_invoice(client, auth_headers)
    import_statement(client, auth_headers, (f"NIP/KOLA AND SONS/{invoice['reference']}", 9_675_000))
    allocation_id = client.get(
        f"/api/transactions/{client.get('/api/transactions', headers=auth_headers).json()['items'][0]['id']}",
        headers=auth_headers,
    ).json()["allocations"][0]["id"]

    no_reason = client.post(f"/api/allocations/{allocation_id}/reverse", json={"reason": " "}, headers=auth_headers)
    reversed_ = client.post(f"/api/allocations/{allocation_id}/reverse", json={"reason": "Wrong invoice"}, headers=auth_headers)
    again = client.post(f"/api/allocations/{allocation_id}/reverse", json={"reason": "Again"}, headers=auth_headers)

    assert no_reason.status_code == 422
    assert reversed_.status_code == 200
    assert reversed_.json()["reversed_at"] is not None
    assert again.status_code == 409
    assert invoice_status(client, auth_headers, invoice["id"]) == "sent"
    assert len(queue(client, auth_headers)) == 1


# --- invariant 8 ---------------------------------------------------------------------------------------


def test_other_workspace_sees_no_queue_and_cannot_allocate_or_reverse(
    client: TestClient, auth_headers: dict, other_auth_headers: dict
) -> None:
    invoice = sent_invoice(client, auth_headers)
    import_statement(client, auth_headers, ("NIP/KOLA AND SONS/OCT", 9_675_000))
    transaction_id = queue(client, auth_headers)[0]["transaction"]["id"]

    assert queue(client, other_auth_headers) == []
    assert accept(client, other_auth_headers, transaction_id, invoice["id"], 1_000, "manual").status_code == 404
    rejected = client.post(
        "/api/reconciliation/reject", json={"transaction_id": transaction_id, "invoice_id": invoice["id"]},
        headers=other_auth_headers,
    )
    assert rejected.status_code == 404

    accept(client, auth_headers, transaction_id, invoice["id"], 9_675_000)
    allocation_id = client.get(f"/api/transactions/{transaction_id}", headers=auth_headers).json()["allocations"][0]["id"]
    assert client.post(
        f"/api/allocations/{allocation_id}/reverse", json={"reason": "x"}, headers=other_auth_headers
    ).status_code == 404


def test_invoices_from_another_workspace_are_never_candidates(
    client: TestClient, auth_headers: dict, other_auth_headers: dict
) -> None:
    theirs = sent_invoice(client, other_auth_headers)

    result = import_statement(client, auth_headers, (f"NIP/KOLA AND SONS/{theirs['reference']}", 9_675_000))

    assert result["auto_allocated"] == 0
    assert queue(client, auth_headers)[0]["candidates"] == []
