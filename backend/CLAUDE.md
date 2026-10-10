# Backend notes

Layout — one folder per feature (docs/DECISIONS.md D-06). Each feature folder holds only the files it needs from:
models.py (SQLModel tables), schemas.py (request/response models — never return table models directly),
service.py (logic), router.py (thin FastAPI routes).
- app/main.py: creates the app and includes every feature's router
- app/core: shared plumbing, not a feature — config (pydantic-settings), security (JWT, password hashing),
  db (engine, session), deps (current_user, require_owner)
- app/db_models.py: imports every feature's models.py so Alembic and scripts/erd.py see all tables
- app/auth: Workspace + User models, register/login/me
- app/customers: Customer model, CRUD
- app/invoices: Invoice model, VAT + derived status in service.py, router.py, public_router.py (/api/v1/public/invoices/{token})
- app/transactions: Transaction model, list/detail
- app/statements: import service (fingerprint, ON CONFLICT DO NOTHING), router.py,
  parsers/ — base (NormalizedLine dataclass), detect (pick parser from header row), bank_a, bank_b
- app/allocations: PaymentAllocation model, service.py with allocate()/reverse() — the ONLY writer of payment_allocations
- app/matching: pure scoring + human-readable reasons, no DB writes
- app/reconciliation: router for queue / allocate / reject / reverse; calls matching and allocations services
- app/paystack: client (verify-transaction, initialise), service, router (webhook)
- app/dashboard: summary, collections, ageing
- app/audit: AuditEvent model, record() helper, router
- tests stay flat in backend/tests/test_*.py
- Models in different features refer to each other with string type hints ("Invoice") to avoid circular imports.

Rules:
- Money fields end in _kobo and are int.
- VAT: computed on the invoice subtotal at 7.5%, rounded half up to the nearest kobo. Record this in docs/DECISIONS.md.
- Fingerprint = sha256 of workspace_id|source|value_date|amount_kobo|normalised narration|bank_reference|balance_kobo.
  If a parser has no balance column, append the occurrence index of that identical line within the file.
- Webhook: verify x-paystack-signature = HMAC-SHA512(raw body, PAYSTACK_SECRET_KEY) before parsing JSON,
  then confirm with Paystack's verify-transaction endpoint, then respond 200 quickly.
- Concurrency tests use two separate sessions against real Postgres (SQLite has no SELECT ... FOR UPDATE).
- Tests run against a Postgres test database from docker compose; each test inside a rolled-back transaction.
