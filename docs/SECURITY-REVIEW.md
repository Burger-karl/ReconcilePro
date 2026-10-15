# Backend security review — 2026-10-10

Scope: the whole backend (`backend/app`) on branch `feat/auth-google-and-reset`, after adding Google sign-in and
password reset. Method: read every router and service, list every database query, then try the suspicious cases
against a real PostgreSQL database. Each fix has a test that fails without it (`tests/test_hardening.py`,
`tests/test_statements.py`, `tests/test_auth_google.py`, `tests/test_password_reset.py`).

## What was already sound

| Area | How it is protected |
|------|---------------------|
| Workspace isolation (invariant 8) | Every query in every feature service filters by `workspace_id`; the workspace comes from the user row, never from the token or the request. The only unscoped lookups are by secret token (public invoice, reset link) or Paystack-verified metadata (webhook), and each then uses the row's own workspace. |
| SQL injection | All queries go through SQLAlchemy with bound parameters; searches use `icontains(..., autoescape=True)`. |
| Login tokens | HS256 with the algorithm pinned (no `none`), `exp` required, workspace never in the token, user re-loaded on every request. |
| Passwords | argon2; unknown email and Google-only users run a dummy hash so timing doesn't reveal accounts; one message for wrong email or password. |
| Paystack webhook | HMAC-SHA512 checked on the raw bytes with `compare_digest` before parsing; refused if no secret is set; amount/status/invoice taken only from verify-transaction; duplicates stopped by unique constraints (invariant 3). |
| Money | Integer kobo with `StrictInt`, DB `CHECK`s, `allocate()` locks and re-sums (invariants 1, 4). |
| Public invoice page | 32-byte random token; response has no internal ids. |
| Google sign-in | RS256 only (blocks algorithm confusion), `aud`, `iss` (exact match), `exp`, `email_verified is True`; user found by `sub`. |
| Password reset | Same answer for every email, email sent in the background, token hashed, single use, 30 minutes, row locked, all sessions ended. |

## Findings and fixes

| # | Severity | Finding | Fix | Decision |
|---|----------|---------|-----|----------|
| 1 | High | **Development JWT secret in production.** If `JWT_SECRET` was not set on Render, the default (public in this repo) would sign tokens, so anyone could forge a login as any user. | `ENVIRONMENT` defaults to `production`; production refuses to start without a ≥32-byte secret. | D-43 |
| 2 | High | **Pre-account hijacking.** An attacker registers the victim's Gmail with a password; when the victim later signs in with Google the accounts link and the attacker keeps password access. | Linking removes the password and bumps `token_version`. | D-46 |
| 3 | Medium | **No request size limit.** Uploads are written to disk before the route checks size; an endless upload could fill the disk. Webhook and JSON bodies also unbounded. | ASGI middleware: 413 over 6 MB, by header and by counting bytes. | D-44 |
| 4 | Medium | **Password guessing / inbox flooding.** No limit on wrong passwords or on reset emails. | 10 failures per email per 15 min → 429; max 3 reset emails per account per hour. | D-42 |
| 5 | Medium | **Statement import crash (≥ ~5,000 lines).** One INSERT exceeded PostgreSQL's 65,535 parameters → 500. | Insert in batches of 1,000; cap at 20,000 lines. | D-47 |
| 6 | Low | **Statement import crash (long reference).** Reference > 100 chars overflowed `VARCHAR(100)` → 500. | 400 naming the line; long payer names cut to 200. | D-47 |
| 7 | Low | **Reset links in production logs.** Without `RESEND_API_KEY`, the email body (with a working link) was logged. | Body logged only in development. | D-45 |
| 8 | Low | **API docs public in production.** `/docs` and `/openapi.json` map every route. | Only in development. | D-45 |
| 9 | Low | **`httpx` only in the `dev` extra** although Paystack and email use it at runtime. | Moved to main dependencies. | — |

## Known gaps (accepted for the MVP, revisit later)

- **Per-IP rate limits** beyond login: login now has one (30 failures per address per 15 minutes, D-66), but
  `/public/invoices/{token}/pay` (calls Paystack on each request), register and forgot-password don't; best done
  at the edge (Render/Cloudflare). The login counters are in memory, per process.
- **Login lockout can be triggered on purpose** for 15 minutes by guessing wrong; forgot password still works.
- **Login tokens live 2 hours** (was 24) and sign-out cancels them on the server, on every device (D-67).
  No refresh tokens, so long sessions sign in again.
- **Token in browser `localStorage`** (frontend): readable by any script on the page, so the UI must avoid XSS
  (no `dangerouslySetInnerHTML` with user data). A Content-Security-Policy limits where a script can send it,
  but still allows inline scripts (D-67). An httpOnly cookie would need CSRF protection and a same-site API.
- **"PAYSTACK" in a customer's own transfer narration** marks that line as a settlement (never matched). It only
  hurts the payer, and the accountant can see it in the transactions list.
- **Forgot-password timing:** a known email does a few database writes before answering; an unknown one doesn't.
  The difference is milliseconds and the email itself is sent in the background.
- **Very large workspaces:** the queue loads all unallocated credits of a workspace; fine for an SME, would need
  paging past tens of thousands of open credits.
- Reset-token rows are never deleted (harmless; a cleanup job can come later).

## Dependency audit

`pip-audit` over all 49 installed backend packages (pinned versions in `backend/pyproject.toml`, incl.
`cryptography==50.0.2`, `pyjwt==2.15.1`, `fastapi==0.142.2`): **no known vulnerabilities** on 2026-10-10.
Re-run before each deploy.

## Deploy checklist that follows from this review

- Render: set `JWT_SECRET` (`python -c "import secrets; print(secrets.token_urlsafe(48))"`), `PAYSTACK_SECRET_KEY`,
  `RESEND_API_KEY`, `GOOGLE_CLIENT_ID`, `FRONTEND_URL`. Leave `ENVIRONMENT` unset (production).
- Local runs outside docker compose: add `ENVIRONMENT=development` to `backend/.env`.
- Set `TRUSTED_PROXY_HOPS` after checking which `X-Forwarded-For` entry is the real client address (D-66).
- Paystack dashboard webhook URL: `https://<api>/api/v1/webhooks/paystack`.
- Google Cloud Console: OAuth client with the frontend origin(s) as authorised JavaScript origins.
