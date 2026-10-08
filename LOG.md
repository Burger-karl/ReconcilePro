# Build log

Template (copy per day):

## Day N — YYYY-MM-DD
- **Built:**
- **Broke:**
- **Learned:**
- **Next:**

---


## Day 1 — 2026-10-05
- **Built:** Starter files, then the docs I plan from: ERD (7 tables), API, DECISIONS D-01–D-11, design system with my navy palette. Switched the backend to feature folders (D-06). Scaffolded FastAPI + Postgres + Alembic, Next 16 + Tailwind 4 + shadcn, and docker compose. Then auth (register/login/me, workspace per sign-up, argon2 + JWT, 17 tests), customers and invoices (server-side VAT, derived status, audit events, 60 tests), `allocate()`/`reverse()` with row locks (31 tests incl. 3 threaded race tests), and CSV statement import with fingerprints and ON CONFLICT DO NOTHING.
- **Broke:** The ERD script printed the wrong column types (fixed in 2e2b5dd). /hardpart-check found the allocation totals helpers weren't filtering by workspace_id (invariant 8) — fixed before committing.
- **Learned:** Locking alone isn't enough: allocate() has to re-sum allocations *after* taking the locks, and the race tests only fail without the locks, which proves they matter (D-17). Letting the database stop duplicates beats checking first (D-21).
- **Next:** Matching and the exception queue.

## Day 2 — 2026-10-06
- **Built:** Just after midnight: matching (exact reference → auto; otherwise score amount 50 / name 30 / date 20), the exception queue, accept/reject/auto-match, reverse endpoint (53 tests, D-25–D-29). Then the Paystack webhook (signature checked on the raw body, trust only verify-transaction, insert + allocate in one transaction) and the public pay endpoint (D-30–D-34).
- **Broke:** The webhook had several holes after the first commit: a verify error was treated as "ignore" instead of "retry", a clash on the fingerprint constraint gave a 500, a non-ASCII signature header gave a TypeError, a 200 that wasn't JSON gave a 500, and long Paystack references didn't fit VARCHAR(100) (now TEXT). Fixed across three commits.
- **Learned:** Only 400/404 from Paystack means "ignore"; anything else should return 502 so Paystack retries (D-35). Wrapping allocate() in a savepoint means a refusal can't leave half-written rows, while the Paystack money is still recorded (D-31). Added tests for double-pay and a retry after a reversal.
- **Next:** Tidy the backend packaging, then start on the UI.

## Day 3 — 2026-10-07
- **Built:** Moved backend dependencies from requirements.txt to pyproject.toml (pinned, with a `dev` extra for pytest); the Dockerfile now installs `".[dev]"`; ignored `build/` and `*.egg-info`. On branch prototype/ui-layout, built a throwaway layout prototype at /prototype/layout-options with three variants (A sidebar + master-detail, B top nav inbox-first, C matching board + inspector) and a switcher bar, using mock data only.
- **Broke:** Nothing recorded. None of this is committed yet.
- **Learned:** —
- **Next:** Compare the three layouts and pick one.

## Day 4 — 2026-10-08
- **Built:** API versioning: every feature route now lives under `/api/v1` (one `API_V1_PREFIX` in `app/main.py`; routers only know their own path, like `/invoices`). `/api/health` stays unversioned because it's a probe for docker compose and Render, not part of the API. Updated the tests, docs/API.md and backend/CLAUDE.md, and wrote D-36. Also checked the prototype type-checks and that all three variants load in the dev server, and listed every page the app still needs (invoice detail and form, customers, statement import, transactions, audit log, public invoice page, payment return page, plus login/register/landing).
- **Broke:** Docker Desktop wouldn't start, so the 158 database tests couldn't connect (they hit a different local Postgres on 5432 that rejects the `reconcile` user). The 114 tests that don't need the database pass, and the OpenAPI schema shows all 21 routes under `/api/v1`. The old webhook URL now gives 404. The first compile of the prototype page took ~2 minutes (Next warned about a slow filesystem).
- **Learned:** Putting the version in the URL (not a header) matters because Paystack can't send custom headers to a webhook, and the webhook URL and public invoice links are given to outsiders — a v2 can run beside v1 later instead of breaking them. In this FastAPI version `app.routes` doesn't list included routers' paths; `app.openapi()['paths']` does. Login and register don't need a layout prototype — they're a centred form. The layout question is only about the signed-in shell.
- **Next:** Get Docker running and run the full test suite. Change the webhook URL in the Paystack dashboard to `/api/v1/webhooks/paystack`. Commit the versioning and the pyproject change on their own branch from main. Then pick a layout.
