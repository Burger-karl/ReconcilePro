# Backend notes

Layout:
- app/core: config (pydantic-settings), security (JWT, password hashing), db (engine, session), deps (current_user, require_owner)
- app/models: one SQLModel table per file — workspace, user, customer, invoice, transaction, payment_allocation, audit_event
- app/schemas: request/response models (never return table models directly)
- app/api: routers — auth, customers, invoices, public, statements, transactions, reconciliation, dashboard, audit, webhooks
- app/services: allocation, matching, statements, paystack, invoices, audit
- app/parsers: base (NormalizedLine dataclass), detect (pick parser from header row), bank_a, bank_b

Rules:
- Money fields end in _kobo and are int.
- VAT: computed on the invoice subtotal at 7.5%, rounded half up to the nearest kobo. Record this in docs/DECISIONS.md.
- Fingerprint = sha256 of workspace_id|source|value_date|amount_kobo|normalised narration|bank_reference|balance_kobo.
  If a parser has no balance column, append the occurrence index of that identical line within the file.
- Webhook: verify x-paystack-signature = HMAC-SHA512(raw body, PAYSTACK_SECRET_KEY) before parsing JSON,
  then confirm with Paystack's verify-transaction endpoint, then respond 200 quickly.
- Concurrency tests use two separate sessions against real Postgres (SQLite has no SELECT ... FOR UPDATE).
- Tests run against a Postgres test database from docker compose; each test inside a rolled-back transaction.
