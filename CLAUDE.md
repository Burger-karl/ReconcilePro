# Reconcile — project memory

Reconcile matches SME bank-statement credits and Paystack payments to invoices automatically,
and sends anything uncertain to an exception queue for the accountant.
Two-week MVP for a bootcamp. The author must be able to explain every line in a viva,
so prefer simple, readable code over clever code, and explain non-obvious choices in comments.

## Stack
- backend/: FastAPI, SQLModel, PostgreSQL, Alembic, pytest. Python 3.12.
- frontend/: Next.js App Router, TypeScript, Tailwind, shadcn/ui, Recharts.
- Paystack (test mode), Resend (email). Deploy: Render (API + DB), Vercel (web).
- Local: `docker compose up` runs postgres, api, web.

## Non-negotiable invariants (the hard part)
1. All money is integer kobo (BIGINT / int). Never float, never Decimal in the DB. Format to ₦ only in the UI.
2. Re-importing a statement adds nothing: unique(workspace_id, fingerprint) + INSERT ... ON CONFLICT DO NOTHING.
3. A duplicate Paystack webhook pays once: unique(source, external_reference) and the allocation is
   created in the same DB transaction as the transaction insert.
4. Every money movement goes through `backend/app/allocations/service.py::allocate()`. It locks rows
   with SELECT ... FOR UPDATE, re-sums existing allocations, and rejects if the bank line OR the invoice
   would be over-allocated. Never insert into payment_allocations anywhere else.
5. Invoice paid/part_paid/overdue status is DERIVED from non-reversed allocations. Only draft/sent/void are stored.
6. Paystack settlement lines on bank statements are kind=settlement and are never matched to invoices.
7. Allocations are reversed (reversed_at), never deleted. Every manual action writes an audit_events row.
8. Every query is scoped by the current user's workspace_id. No exceptions.

## Matching
- Exact reference in narration/reference field (case- and space-insensitive) → auto-allocate if amount ≤ outstanding.
- Otherwise score: amount == outstanding (50), payer name fuzzy ≥ 85 vs name/aliases (30, scaled),
  value date 0–14 days after send (20, decaying). Score ≥ 70 with one clear top candidate → suggested.
- Only sent / part_paid / overdue invoices are candidates. Always return human-readable reasons.

## Conventions
- Backend is organised by feature: `app/<feature>/` holds models.py, schemas.py, service.py, router.py (docs/DECISIONS.md D-06).
- Routers are thin: validate, call their own feature's service, return. Logic lives in service.py.
  A feature may call another feature's service, never its router.
- Matching functions are pure (no DB writes); allocation is the only writer of allocations.
- Write tests first for anything touching money. Test files: backend/tests/test_*.py.
- Small diffs, one feature per session. Do not add features listed under "Later" in docs/ (bank feeds, FIRS integration, WhatsApp).
- Never read or print .env files or secrets.

## Commands
- Backend tests: `cd backend && pytest -q`
- Migrations: `cd backend && alembic revision --autogenerate -m "msg"` then `alembic upgrade head`
- Seed: `cd backend && python seed.py`
- Frontend: `cd frontend && npm run dev` / `npm run lint` / `npm run build`
- API types: `cd frontend && npx openapi-typescript http://localhost:8000/openapi.json -o types/api.ts`

## Docs to read before planning a feature
docs/RESEARCH.md, docs/ERD.md, docs/API.md, docs/DECISIONS.md.
For UI work also read design-system/reconcile/MASTER.md and the matching pages/<page>.md override.
