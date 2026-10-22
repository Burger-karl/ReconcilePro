"""Dashboard numbers (DECISIONS D-48): summary tiles, collections by week, ageing.

Every number is derived from stored rows (invariant 5): invoices and non-reversed allocations.
Test data is built with chosen dates; money is always moved through allocations.service.allocate()
(invariant 4), never by inserting allocation rows here.
"""

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.allocations import service as allocations
from app.allocations.models import PaymentAllocation
from app.core.time import lagos_today, utc_now
from app.transactions.models import Transaction

TODAY = lagos_today()
SUMMARY = "/api/v1/dashboard/summary"
COLLECTIONS = "/api/v1/dashboard/collections"
AGEING = "/api/v1/dashboard/ageing"


def workspace_id(client: TestClient, headers: dict) -> uuid.UUID:
    return uuid.UUID(client.get("/api/v1/auth/me", headers=headers).json()["workspace"]["id"])


def invoice(client: TestClient, headers: dict, *, subtotal_kobo: int = 10_000_000, due: date | None = None,
            send: bool = True) -> dict:
    """An invoice for subtotal + 7.5% VAT (10,000,000 -> total 10,750,000), issued 100 days ago."""
    due = due or TODAY + timedelta(days=14)
    customer = client.post("/api/v1/customers", json={"name": f"Customer {uuid.uuid4().hex[:6]}"}, headers=headers).json()
    created = client.post(
        "/api/v1/invoices",
        json={"customer_id": customer["id"], "description": "Supplies", "subtotal_kobo": subtotal_kobo,
              "issue_date": (TODAY - timedelta(days=100)).isoformat(), "due_date": due.isoformat()},
        headers=headers,
    ).json()
    if not send:
        return created
    response = client.post(f"/api/v1/invoices/{created['id']}/send", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def credit(session: Session, ws: uuid.UUID, amount_kobo: int, value_date: date = TODAY, kind: str = "credit") -> Transaction:
    transaction = Transaction(
        workspace_id=ws, source="bank_statement", kind=kind, value_date=value_date, amount_kobo=amount_kobo,
        narration=f"TRF {uuid.uuid4().hex}", fingerprint=uuid.uuid4().hex + uuid.uuid4().hex,
    )
    session.add(transaction)
    session.flush()
    return transaction


def pay(session: Session, ws: uuid.UUID, transaction: Transaction, invoice_id: str, amount_kobo: int,
        method: str = "manual") -> PaymentAllocation:
    allocation = allocations.allocate(
        session, workspace_id=ws, transaction_id=transaction.id, invoice_id=uuid.UUID(invoice_id),
        amount_kobo=amount_kobo, method=method, actor_user_id=None,
    )
    session.flush()
    return allocation


def get(client: TestClient, headers: dict, url: str):
    response = client.get(url, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# --- summary ----------------------------------------------------------------------------------------


def test_summary_for_a_new_workspace(client: TestClient, auth_headers: dict) -> None:
    assert get(client, auth_headers, SUMMARY) == {
        "outstanding_kobo": 0,
        "open_invoice_count": 0,
        "collected_this_month_kobo": 0,
        "auto_match_rate": None,  # nothing matched yet: no rate, rather than a misleading 0%
        "needs_review_count": 0,
    }


def test_outstanding_counts_only_open_invoices(client: TestClient, auth_headers: dict, session: Session) -> None:
    ws = workspace_id(client, auth_headers)
    invoice(client, auth_headers, send=False)  # draft: not owed yet
    open_one = invoice(client, auth_headers)  # 10,750,000 owed
    part_paid = invoice(client, auth_headers)
    paid = invoice(client, auth_headers)
    voided = invoice(client, auth_headers)
    client.post(f"/api/v1/invoices/{voided['id']}/void", json={"reason": "Raised twice"}, headers=auth_headers)
    pay(session, ws, credit(session, ws, 4_000_000), part_paid["id"], 4_000_000)
    pay(session, ws, credit(session, ws, 10_750_000), paid["id"], 10_750_000)

    summary = get(client, auth_headers, SUMMARY)

    assert summary["outstanding_kobo"] == open_one["total_kobo"] + (10_750_000 - 4_000_000)
    assert summary["open_invoice_count"] == 2
    assert isinstance(summary["outstanding_kobo"], int)


def test_collected_this_month_counts_matched_money_by_the_date_it_arrived(
    client: TestClient, auth_headers: dict, session: Session
) -> None:
    ws = workspace_id(client, auth_headers)
    target = invoice(client, auth_headers, subtotal_kobo=100_000_000)
    first_of_month = TODAY.replace(day=1)
    pay(session, ws, credit(session, ws, 3_000_000, TODAY), target["id"], 3_000_000)
    pay(session, ws, credit(session, ws, 1_000_000, first_of_month), target["id"], 1_000_000)
    pay(session, ws, credit(session, ws, 7_000_000, first_of_month - timedelta(days=1)), target["id"], 7_000_000)
    credit(session, ws, 9_000_000, TODAY)  # arrived, but not matched to an invoice yet
    reversed_one = pay(session, ws, credit(session, ws, 2_000_000, TODAY), target["id"], 2_000_000)
    allocations.reverse(session, workspace_id=ws, allocation_id=reversed_one.id, actor_user_id=None, reason="Wrong")
    session.flush()

    assert get(client, auth_headers, SUMMARY)["collected_this_month_kobo"] == 4_000_000


def test_auto_match_rate_is_the_share_matched_automatically_in_the_last_30_days(
    client: TestClient, auth_headers: dict, session: Session
) -> None:
    ws = workspace_id(client, auth_headers)
    target = invoice(client, auth_headers, subtotal_kobo=100_000_000)
    for method in ("auto", "auto", "auto", "manual"):
        pay(session, ws, credit(session, ws, 100_000), target["id"], 100_000, method=method)
    old = pay(session, ws, credit(session, ws, 100_000), target["id"], 100_000, method="manual")
    old.created_at = utc_now() - timedelta(days=31)
    session.add(old)
    session.flush()

    assert get(client, auth_headers, SUMMARY)["auto_match_rate"] == 75


def test_auto_match_rate_ignores_reversed_allocations(client: TestClient, auth_headers: dict, session: Session) -> None:
    ws = workspace_id(client, auth_headers)
    target = invoice(client, auth_headers)
    pay(session, ws, credit(session, ws, 100_000), target["id"], 100_000, method="auto")
    wrong = pay(session, ws, credit(session, ws, 100_000), target["id"], 100_000, method="auto")
    pay(session, ws, credit(session, ws, 100_000), target["id"], 100_000, method="manual")
    allocations.reverse(session, workspace_id=ws, allocation_id=wrong.id, actor_user_id=None, reason="Wrong")
    session.flush()

    assert get(client, auth_headers, SUMMARY)["auto_match_rate"] == 50


def test_needs_review_counts_credits_with_money_still_unmatched(
    client: TestClient, auth_headers: dict, session: Session
) -> None:
    ws = workspace_id(client, auth_headers)
    target = invoice(client, auth_headers)
    credit(session, ws, 500_000)  # nothing matched
    partly = credit(session, ws, 500_000)
    pay(session, ws, partly, target["id"], 200_000)  # 300,000 still unmatched
    fully = credit(session, ws, 500_000)
    pay(session, ws, fully, target["id"], 500_000)
    credit(session, ws, 9_000_000, kind="settlement")  # never matched, never reviewed (invariant 6)

    assert get(client, auth_headers, SUMMARY)["needs_review_count"] == 2


# --- collections by week -----------------------------------------------------------------------------


def test_collections_returns_each_week_oldest_first_with_empty_weeks_as_zero(
    client: TestClient, auth_headers: dict, session: Session
) -> None:
    ws = workspace_id(client, auth_headers)
    target = invoice(client, auth_headers, subtotal_kobo=100_000_000)
    this_monday = TODAY - timedelta(days=TODAY.weekday())
    pay(session, ws, credit(session, ws, 1_000_000, TODAY), target["id"], 1_000_000)
    pay(session, ws, credit(session, ws, 2_000_000, this_monday), target["id"], 2_000_000)
    pay(session, ws, credit(session, ws, 5_000_000, this_monday - timedelta(days=8)), target["id"], 5_000_000)
    pay(session, ws, credit(session, ws, 9_000_000, this_monday - timedelta(days=30)), target["id"], 9_000_000)

    weeks = get(client, auth_headers, f"{COLLECTIONS}?weeks=3")

    assert weeks == [
        {"week_start": (this_monday - timedelta(days=14)).isoformat(), "collected_kobo": 5_000_000},
        {"week_start": (this_monday - timedelta(days=7)).isoformat(), "collected_kobo": 0},
        {"week_start": this_monday.isoformat(), "collected_kobo": 3_000_000},
    ]


def test_collections_defaults_to_8_weeks(client: TestClient, auth_headers: dict) -> None:
    weeks = get(client, auth_headers, COLLECTIONS)

    assert len(weeks) == 8
    assert all(week["collected_kobo"] == 0 for week in weeks)
    assert all(date.fromisoformat(week["week_start"]).weekday() == 0 for week in weeks)  # Mondays


@pytest.mark.parametrize("weeks", [0, 53, -1])
def test_collections_weeks_must_be_1_to_52(client: TestClient, auth_headers: dict, weeks: int) -> None:
    assert client.get(f"{COLLECTIONS}?weeks={weeks}", headers=auth_headers).status_code == 422


# --- ageing -----------------------------------------------------------------------------------------


def test_ageing_buckets_by_days_past_due(client: TestClient, auth_headers: dict, session: Session) -> None:
    ws = workspace_id(client, auth_headers)
    invoice(client, auth_headers, due=TODAY)  # due today: not late yet
    invoice(client, auth_headers, due=TODAY + timedelta(days=5))
    late_10 = invoice(client, auth_headers, due=TODAY - timedelta(days=10))
    invoice(client, auth_headers, due=TODAY - timedelta(days=30))
    invoice(client, auth_headers, due=TODAY - timedelta(days=31))
    invoice(client, auth_headers, due=TODAY - timedelta(days=60))
    invoice(client, auth_headers, due=TODAY - timedelta(days=61))
    paid_late = invoice(client, auth_headers, due=TODAY - timedelta(days=90))
    pay(session, ws, credit(session, ws, 4_000_000), late_10["id"], 4_000_000)
    pay(session, ws, credit(session, ws, 10_750_000), paid_late["id"], 10_750_000)  # paid: not owed, not aged

    assert get(client, auth_headers, AGEING) == [
        {"bucket": "current", "outstanding_kobo": 2 * 10_750_000, "count": 2},
        {"bucket": "1_30", "outstanding_kobo": (10_750_000 - 4_000_000) + 10_750_000, "count": 2},
        {"bucket": "31_60", "outstanding_kobo": 2 * 10_750_000, "count": 2},
        {"bucket": "60_plus", "outstanding_kobo": 10_750_000, "count": 1},
    ]


def test_ageing_always_lists_all_four_buckets(client: TestClient, auth_headers: dict) -> None:
    assert [row["bucket"] for row in get(client, auth_headers, AGEING)] == ["current", "1_30", "31_60", "60_plus"]


# --- from a dashboard bucket to the invoices in it ---------------------------------------------------------


def _ageing_numbers(client: TestClient, headers: dict, bucket: str) -> list[str]:
    body = get(client, headers, f"/api/v1/invoices?ageing={bucket}")
    assert body["total"] == len(body["items"])
    return sorted(item["number"] for item in body["items"])


def test_invoice_list_filters_by_ageing_bucket(client: TestClient, auth_headers: dict, session: Session) -> None:
    # Clicking an ageing bucket on the dashboard opens the invoices list filtered to that bucket.
    ws = workspace_id(client, auth_headers)
    not_due = invoice(client, auth_headers, due=TODAY)
    late_30 = invoice(client, auth_headers, due=TODAY - timedelta(days=30))
    late_31 = invoice(client, auth_headers, due=TODAY - timedelta(days=31))
    late_61 = invoice(client, auth_headers, due=TODAY - timedelta(days=61))
    paid_late = invoice(client, auth_headers, due=TODAY - timedelta(days=90))
    invoice(client, auth_headers, due=TODAY - timedelta(days=90), send=False)  # a draft is never owed
    pay(session, ws, credit(session, ws, 10_750_000), paid_late["id"], 10_750_000)

    assert _ageing_numbers(client, auth_headers, "current") == [not_due["number"]]
    assert _ageing_numbers(client, auth_headers, "1_30") == [late_30["number"]]
    assert _ageing_numbers(client, auth_headers, "31_60") == [late_31["number"]]
    assert _ageing_numbers(client, auth_headers, "60_plus") == [late_61["number"]]


def test_ageing_filter_agrees_with_the_dashboard(client: TestClient, auth_headers: dict, session: Session) -> None:
    # The list behind a bucket must hold exactly the invoices the bucket counts, part-paid ones included.
    ws = workspace_id(client, auth_headers)
    for days in (0, 5, 10, 45, 75):
        invoice(client, auth_headers, due=TODAY - timedelta(days=days))
    part = invoice(client, auth_headers, due=TODAY - timedelta(days=10))
    pay(session, ws, credit(session, ws, 1_000_000), part["id"], 1_000_000)

    for bucket in get(client, auth_headers, AGEING):
        listed = get(client, auth_headers, f"/api/v1/invoices?ageing={bucket['bucket']}")
        assert listed["total"] == bucket["count"]
        assert sum(item["outstanding_kobo"] for item in listed["items"]) == bucket["outstanding_kobo"]


def test_open_status_lists_what_the_outstanding_tile_counts(
    client: TestClient, auth_headers: dict, session: Session
) -> None:
    # Clicking "Outstanding" opens invoices?status=open: every invoice still owed, and nothing else.
    ws = workspace_id(client, auth_headers)
    sent = invoice(client, auth_headers)
    overdue = invoice(client, auth_headers, due=TODAY - timedelta(days=5))
    part = invoice(client, auth_headers)
    paid = invoice(client, auth_headers)
    invoice(client, auth_headers, send=False)  # draft
    pay(session, ws, credit(session, ws, 1_000_000), part["id"], 1_000_000)
    pay(session, ws, credit(session, ws, 10_750_000), paid["id"], 10_750_000)

    listed = get(client, auth_headers, "/api/v1/invoices?status=open")
    assert sorted(item["number"] for item in listed["items"]) == sorted([sent["number"], overdue["number"], part["number"]])
    summary = get(client, auth_headers, SUMMARY)
    assert listed["total"] == summary["open_invoice_count"]
    assert sum(item["outstanding_kobo"] for item in listed["items"]) == summary["outstanding_kobo"]


def test_unknown_ageing_bucket_is_422(client: TestClient, auth_headers: dict) -> None:
    assert client.get("/api/v1/invoices?ageing=90_plus", headers=auth_headers).status_code == 422


def test_ageing_filter_only_lists_the_callers_workspace(
    client: TestClient, auth_headers: dict, other_auth_headers: dict
) -> None:
    invoice(client, other_auth_headers, due=TODAY - timedelta(days=40))
    assert get(client, auth_headers, "/api/v1/invoices?ageing=31_60")["total"] == 0


# --- scope and access ---------------------------------------------------------------------------------


def test_dashboard_only_counts_the_callers_workspace(
    client: TestClient, auth_headers: dict, other_auth_headers: dict, session: Session
) -> None:
    other_ws = workspace_id(client, other_auth_headers)
    theirs = invoice(client, other_auth_headers, due=TODAY - timedelta(days=40))
    pay(session, other_ws, credit(session, other_ws, 1_000_000), theirs["id"], 1_000_000, method="auto")
    credit(session, other_ws, 500_000)

    assert get(client, auth_headers, SUMMARY) == {
        "outstanding_kobo": 0, "open_invoice_count": 0, "collected_this_month_kobo": 0,
        "auto_match_rate": None, "needs_review_count": 0,
    }
    assert all(week["collected_kobo"] == 0 for week in get(client, auth_headers, COLLECTIONS))
    assert all(row["count"] == 0 for row in get(client, auth_headers, AGEING))


@pytest.mark.parametrize("url", [SUMMARY, COLLECTIONS, AGEING])
def test_dashboard_needs_login(client: TestClient, url: str) -> None:
    assert client.get(url).status_code == 401
