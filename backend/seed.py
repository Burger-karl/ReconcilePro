"""Fill an EMPTY development database with a believable demo workspace.

Usage (from backend/, with DATABASE_URL pointing at a dev database and ENVIRONMENT=development):
    python seed.py

It goes through the real API (FastAPI's TestClient calls the routes in-process), so every rule still
applies: VAT is computed by the server, money moves only through allocate() (invariant 4), and every
change writes its audit row (invariant 7). Dates are relative to today, so the dashboard always has
something in every chart.

Sign in afterwards with the email and password printed at the end (test values for local use only).
"""

import sys
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.time import lagos_today
from app.main import app

EMAIL = "demo@adaezefoods.ng"
PASSWORD = "demo-password-1"  # local demo data only; never a real password
API = "/api/v1"
TODAY = lagos_today()


def day(offset: int) -> date:
    return TODAY + timedelta(days=offset)


def ok(response, expected: int = 200) -> dict:
    if response.status_code != expected:
        sys.exit(f"Seed failed: {response.request.method} {response.request.url.path} -> {response.status_code} {response.text}")
    return response.json() if response.content else {}


def main() -> None:
    if settings.environment != "development":
        sys.exit("Refusing to seed: set ENVIRONMENT=development (this script creates a known demo password).")

    client = TestClient(app)
    existing = client.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    if existing.status_code == 200:
        sys.exit(f"Already seeded: sign in as {EMAIL}.")

    token = ok(
        client.post(f"{API}/auth/register", json={"email": EMAIL, "password": PASSWORD, "workspace_name": "Adaeze Foods"}),
        201,
    )["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"

    # --- customers (aliases = the names they appear under on bank statements) -------------------------
    customers = {}
    for name, aliases, email in [
        ("Kola & Sons", ["KOLA AND SONS"], "accounts@kolasons.ng"),
        ("Bisi Stores", ["BISI STORES LTD"], "bisi@bisistores.ng"),
        ("Tunde Print", ["TUNDE PRINTING"], None),
        ("Chika Logistics", [], "pay@chikalogistics.ng"),
        ("Emeka Farms", ["EMEKA FARMS"], None),
        ("Ngozi Catering", ["NGOZI CATERING"], "ngozi@catering.ng"),
    ]:
        customers[name] = ok(client.post(f"{API}/customers", json={"name": name, "aliases": aliases, "email": email}), 201)

    # --- invoices: (customer, naira subtotal, issued, due, send?) ----------------------------------------
    def invoice(customer: str, naira: int, issued: int, due: int, send: bool = True) -> dict:
        created = ok(
            client.post(
                f"{API}/invoices",
                json={
                    "customer_id": customers[customer]["id"],
                    "description": "Supplies",
                    "subtotal_kobo": naira * 100,
                    "issue_date": day(issued).isoformat(),
                    "due_date": day(due).isoformat(),
                },
            ),
            201,
        )
        return ok(client.post(f"{API}/invoices/{created['id']}/send")) if send else created

    kola_paid = invoice("Kola & Sons", 90_000, -60, -46)  # paid in full by reference
    bisi_part = invoice("Bisi Stores", 250_000, -50, -36)  # part paid: 31-60 days late
    invoice("Tunde Print", 40_000, -100, -86)  # nothing paid: over 60 days late
    invoice("Chika Logistics", 120_000, -25, -11)  # 1-30 days late
    emeka = invoice("Emeka Farms", 75_000, -20, -6)  # paid without a reference: matched by hand below
    ngozi = invoice("Ngozi Catering", 60_000, -10, 4)  # paid without a reference: left in the queue
    invoice("Kola & Sons", 30_000, -5, 9)  # not due yet
    invoice("Bisi Stores", 15_000, 0, 14, send=False)  # a draft

    # --- one bank statement (bank_b format) covering the last eight weeks ----------------------------
    def money(kobo: int) -> str:
        return f"{kobo // 100}.{kobo % 100:02d}"

    lines = [
        (-40, f"NIP/KOLA AND SONS/{kola_paid['reference']}", kola_paid["total_kobo"]),
        (-30, f"NIP/BISI STORES LTD/{bisi_part['reference']}", 10_000_000),
        (-18, "NIP/ADEBAYO OKON/TRANSFER", 5_000_000),  # nobody recognises this payer
        (-4, "NIP/EMEKA FARMS/PAYMENT FOR SUPPLIES", emeka["total_kobo"]),  # recent, so "collected this month" shows it
        (-7, "PAYSTACK SETTLEMENT 0071234", 4_500_000),  # a settlement: never matched (invariant 6)
        (-3, "NIP/NGOZI CATERING/INVOICE PAYMENT", ngozi["total_kobo"]),
    ]
    csv = ["DATE POSTED,VALUE DATE,DESCRIPTION,DEBIT,CREDIT"]
    for offset, narration, kobo in lines:
        posted = day(offset).strftime("%Y/%m/%d")
        csv.append(f"{posted},{posted},{narration},,{money(kobo)}")
    posted = day(-1).strftime("%Y/%m/%d")
    csv.append(f"{posted},{posted},POS PURCHASE SHOPRITE LEKKI,15000.00,")  # debits are counted, not stored
    result = ok(
        client.post(
            f"{API}/statements/import",
            files={"file": ("statement.csv", ("\n".join(csv) + "\n").encode(), "text/csv")},
        )
    )

    # --- the accountant accepts the Emeka suggestion from the queue -----------------------------------
    queue = ok(client.get(f"{API}/reconciliation/queue"))["items"]
    emeka_credit = next(item for item in queue if "EMEKA" in item["transaction"]["narration"])
    ok(
        client.post(
            f"{API}/reconciliation/allocate",
            json={
                "transaction_id": emeka_credit["transaction"]["id"],
                "invoice_id": emeka["id"],
                "amount_kobo": emeka["total_kobo"],
                "method": "suggested",
            },
        ),
        201,
    )

    print(f"Seeded workspace 'Adaeze Foods': {result['added']} bank lines, {result['auto_allocated']} matched automatically.")
    print(f"Sign in as {EMAIL} / {PASSWORD}")


if __name__ == "__main__":
    main()
