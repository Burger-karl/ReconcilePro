"""Feature 4 — statement import through the API, and the transactions list.

Invariant 2: re-importing a statement adds nothing.
Invariant 6: Paystack settlement lines are stored as kind=settlement.
Invariant 8: imports and transactions belong to one workspace.
"""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.audit.models import AuditEvent
from app.transactions.models import Transaction

FIXTURES = Path(__file__).parent / "fixtures" / "statements"


def upload(client: TestClient, headers: dict, name: str, content: bytes | None = None, content_type: str = "text/csv"):
    data = content if content is not None else (FIXTURES / name).read_bytes()
    return client.post("/api/statements/import", files={"file": (name, data, content_type)}, headers=headers)


def import_ok(client: TestClient, headers: dict, name: str) -> dict:
    response = upload(client, headers, name)
    assert response.status_code == 200, response.text
    return response.json()


def count_transactions(session: Session) -> int:
    return session.exec(select(func.count()).select_from(Transaction)).one()


# --- importing ---------------------------------------------------------------------------------------


def test_import_bank_a(client: TestClient, auth_headers: dict, session: Session) -> None:
    result = import_ok(client, auth_headers, "bank_a.csv")

    assert result == {
        "bank": "bank_a",
        "rows_read": 6,
        "added": 4,  # 4 credits (incl. 1 settlement)
        "skipped_duplicates": 0,
        "settlements": 1,
        "debits_ignored": 2,
    }
    rows = session.exec(select(Transaction).order_by(Transaction.value_date, Transaction.amount_kobo)).all()
    assert [(r.amount_kobo, r.kind) for r in rows] == [
        (9_675_000, "credit"),
        (5_000_000, "credit"),
        (24_530_000, "settlement"),
        (1_075_050, "credit"),
    ]
    assert all(type(r.amount_kobo) is int for r in rows)
    assert rows[0].payer_name == "KOLA AND SONS"
    assert rows[0].bank_reference == "FT26274A001"
    assert rows[0].source == "bank_statement"


def test_reimporting_the_same_statement_adds_nothing(client: TestClient, auth_headers: dict, session: Session) -> None:
    import_ok(client, auth_headers, "bank_a.csv")
    before = count_transactions(session)

    again = import_ok(client, auth_headers, "bank_a.csv")

    assert (again["added"], again["skipped_duplicates"]) == (0, 4)
    assert count_transactions(session) == before


def test_overlapping_statement_adds_only_new_lines(client: TestClient, auth_headers: dict, session: Session) -> None:
    import_ok(client, auth_headers, "bank_a.csv")

    overlap = import_ok(client, auth_headers, "bank_a_overlap.csv")

    assert (overlap["added"], overlap["skipped_duplicates"], overlap["debits_ignored"]) == (2, 1, 1)
    assert count_transactions(session) == 6


def test_identical_payments_without_balance_are_both_kept_and_reimport_is_still_a_no_op(
    client: TestClient, auth_headers: dict, session: Session
) -> None:
    first = import_ok(client, auth_headers, "bank_b.csv")
    second = import_ok(client, auth_headers, "bank_b.csv")

    assert (first["bank"], first["added"], first["settlements"], first["debits_ignored"]) == ("bank_b", 4, 1, 1)
    ifeoma = session.exec(select(Transaction).where(Transaction.payer_name == "IFEOMA CATERING")).all()
    assert len(ifeoma) == 2
    assert (second["added"], second["skipped_duplicates"]) == (0, 4)


def test_import_is_audited(client: TestClient, auth_headers: dict, session: Session) -> None:
    import_ok(client, auth_headers, "bank_a.csv")

    event = session.exec(select(AuditEvent).where(AuditEvent.action == "statement.imported")).one()
    assert event.data["filename"] == "bank_a.csv"
    assert event.data["added"] == 4
    assert event.actor_user_id is not None


def test_same_file_in_another_workspace_is_imported_separately(
    client: TestClient, auth_headers: dict, other_auth_headers: dict
) -> None:
    import_ok(client, auth_headers, "bank_a.csv")

    other = import_ok(client, other_auth_headers, "bank_a.csv")

    assert other["added"] == 4  # the fingerprint includes the workspace


# --- rejected files ----------------------------------------------------------------------------------


def test_unknown_format_is_400_and_inserts_nothing(client: TestClient, auth_headers: dict, session: Session) -> None:
    response = upload(client, auth_headers, "mystery.csv", b"Date,Amount,Who\n2026-10-01,100,ME\n")

    assert response.status_code == 400
    assert "Unrecognised statement format" in response.json()["detail"]
    assert count_transactions(session) == 0


def test_one_bad_row_rejects_the_whole_file(client: TestClient, auth_headers: dict, session: Session) -> None:
    bad = (FIXTURES / "bank_b.csv").read_bytes().replace(b"120450.75", b"12O450.75")

    response = upload(client, auth_headers, "bank_b.csv", bad)

    assert response.status_code == 400
    assert "Line 6" in response.json()["detail"]
    assert count_transactions(session) == 0  # all or nothing


def test_empty_file_is_400(client: TestClient, auth_headers: dict) -> None:
    assert upload(client, auth_headers, "empty.csv", b"").status_code == 400


def test_non_csv_is_400(client: TestClient, auth_headers: dict) -> None:
    response = upload(client, auth_headers, "statement.pdf", b"%PDF-1.7 ...", "application/pdf")

    assert response.status_code == 400
    assert "CSV" in response.json()["detail"]


def test_file_too_large_is_413(client: TestClient, auth_headers: dict) -> None:
    huge = b"x" * (5 * 1024 * 1024 + 1)

    assert upload(client, auth_headers, "huge.csv", huge).status_code == 413


def test_windows_excel_encoding_is_accepted(client: TestClient, auth_headers: dict) -> None:
    # Excel on Windows often saves CSV as cp1252 (e.g. the naira sign isn't representable, but é is).
    content = (FIXTURES / "bank_b.csv").read_text(encoding="utf-8").replace("IKEJA", "IKÉJA").encode("cp1252")

    assert upload(client, auth_headers, "bank_b.csv", content).status_code == 200


def test_import_needs_login(client: TestClient) -> None:
    assert upload(client, {}, "bank_a.csv").status_code == 401


# --- transactions list --------------------------------------------------------------------------------


def test_list_transactions_with_unallocated_amounts(client: TestClient, auth_headers: dict) -> None:
    import_ok(client, auth_headers, "bank_a.csv")

    body = client.get("/api/transactions", headers=auth_headers).json()

    assert body["total"] == 4
    newest = body["items"][0]  # newest value date first
    assert newest["amount_kobo"] == 1_075_050
    assert newest["unallocated_kobo"] == 1_075_050
    assert newest["allocated_kobo"] == 0


def test_list_transactions_filters_by_kind_and_state(client: TestClient, auth_headers: dict) -> None:
    import_ok(client, auth_headers, "bank_a.csv")

    settlements = client.get("/api/transactions", params={"kind": "settlement"}, headers=auth_headers).json()
    unallocated = client.get("/api/transactions", params={"state": "unallocated"}, headers=auth_headers).json()
    allocated = client.get("/api/transactions", params={"state": "allocated"}, headers=auth_headers).json()

    assert [t["amount_kobo"] for t in settlements["items"]] == [24_530_000]
    assert unallocated["total"] == 4
    assert allocated["total"] == 0


def test_transaction_detail_and_isolation(client: TestClient, auth_headers: dict, other_auth_headers: dict) -> None:
    import_ok(client, auth_headers, "bank_a.csv")
    transaction_id = client.get("/api/transactions", headers=auth_headers).json()["items"][0]["id"]

    mine = client.get(f"/api/transactions/{transaction_id}", headers=auth_headers)
    theirs = client.get(f"/api/transactions/{transaction_id}", headers=other_auth_headers)

    assert mine.status_code == 200
    assert mine.json()["allocations"] == []
    assert theirs.status_code == 404
    assert client.get("/api/transactions", headers=other_auth_headers).json()["total"] == 0
