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

## Day 5 — 2026-10-09
- **Built:** No code. Moved the pyproject change and API versioning onto their own branch (`chore/pyproject-and-api-v1`, three commits off main) before committing. Planned the auth work with /plan-feature: Google sign-in, forgot password, reset password — files, function signatures, tests to write first, invariants touched, viva points, open questions.
- **Broke:** My first commit attempt put the `requirements.txt` deletion into the versioning commit; undid the local commits and redid them in the right groups (nothing was pushed).
- **Learned:** The simplest Google sign-in is the ID token from Google's button: the backend only checks Google's signature, so there's no redirect flow, client secret or OAuth state to store.
- **Next:** Build it test-first, then a security review of the whole backend before the UI.

## Day 6 — 2026-10-10
- **Built:** On `feat/auth-google-and-reset` (branched off the v1 branch):
  - `POST /api/v1/auth/google/register` and `/google/login`. `app/auth/google.py` checks Google's ID token with PyJWT: RS256 only, `aud`, `iss`, `exp`, `email_verified`. Users are found by Google's `sub`, and a password account is linked only when Google owns the email (Gmail or Workspace).
  - `POST /auth/forgot-password` (always the same 202, email sent in the background, 30-minute single-use link, only a sha256 of the token stored, link token in the URL `#fragment`) and `POST /auth/reset-password` (row locked, all old sessions ended through `users.token_version`).
  - `app/email/service.py` sends through Resend. Migration `c41f8e2d7a90`: nullable `password_hash`, `google_sub`, `token_version`, `password_reset_tokens` table, and a CHECK that every user can still sign in.
  - Whole-backend security review, written up in `docs/SECURITY-REVIEW.md`, and fixed: production refuses the dev JWT secret (`ENVIRONMENT` now defaults to production), Google linking removes the old password (pre-account hijacking), 6 MB request limit, 10 failed logins → 429 for 15 minutes, max 3 reset emails/hour, API docs off in production, no email bodies in production logs, statement import batches inserts and caps at 20,000 lines, long references give a 400.
  - Moved `httpx` to runtime dependencies.
  - Docs: API.md, ERD.md, DECISIONS D-37 to D-47. 344 tests pass. `pip-audit`: no known vulnerabilities.
- **Broke:** Docker Desktop won't start, so I ran the tests against a throwaway Postgres (`pgserver`) instead. Because the database wasn't up while I wrote them, I never saw the new auth tests fail first. To make up for it I broke five security checks on purpose, one at a time, and the tests caught each one. The review found two real crashes in statement import: a reference over 100 characters (`value too long for type character varying(100)`), and about 5,000+ lines (`number of parameters must be between 0 and 65535`).
- **Learned:** Google's guide says to key on `sub`, not email, and to trust the email for linking only when Google is authoritative for it. Pre-account hijacking is why linking must remove an unverified password. A JWT can't be deleted, so a version number in the user row logs out every old token. FastAPI turns any error raised while it reads a body into a 400, so the size-limit error has to be an HTTPException to come back as 413.
- **Next:** Set `ENVIRONMENT=development` in my local `backend/.env`. Get Docker working and run the suite there. Create the Google OAuth client id. Commit this branch, merge the v1 branch and then this one. Then the UI: pick a layout and build the login, register, forgot-password and reset pages.

## Day 7 — 2026-10-12
- **Built:** Merged `chore/pyproject-and-api-v1` and `feat/auth-google-and-reset` into main (no conflicts). Before starting the frontend I found two backend features from API.md were still missing, so on `feat/dashboard-audit`:
  - `GET /api/v1/dashboard/summary`: outstanding, open invoice count, collected this month, auto-match rate (whole %, or null when nothing was matched), needs review.
  - `GET /api/v1/dashboard/collections?weeks=8`: Monday weeks, oldest first, empty weeks as 0.
  - `GET /api/v1/dashboard/ageing`: current / 1–30 / 31–60 / 60+ days past due.
  - `GET /api/v1/audit`: paged, filterable by entity, with the actor's email.
  - Added `invoices.open_invoices()` and `reconciliation.needs_review_count()` so the dashboard reuses the same rules as the invoices page and the queue. Decisions D-48 and D-49. Tests written first and seen failing (26 failed, then passed); 370 tests pass.
  - Chose layout C (matching board + inspector) for the signed-in app.
- **Broke:** The throwaway test Postgres from last session had crashed mid-checkpoint and wouldn't restart within its 10-second limit, so I started a fresh one.
- **Learned:** Collections are counted by the date the money arrived, not the date it was matched, so last month's total doesn't change when an old payment is matched today. Every dashboard number is derived (invariant 5), so it can never disagree with the invoice list or the queue.
- **Built (frontend, F1 foundation on `feat/frontend-foundation`):** Planned the frontend in 9 slices: F1 foundation, F2 Overview, F3 Match board, F4 Invoices, F5 Customers, F6 Statements, F7 Audit, F8 public invoice and Paystack return, F9 landing. Committed and merged the dashboard/audit slice first. Then:
  - Generated `types/api.ts` from the backend schema (exported straight from `app.openapi()`, so no running server was needed).
  - `lib/auth.tsx`: who is signed in, checked with `/auth/me`. Signing out also clears the SWR cache.
  - Pages:
    - `/login`
    - `/register`: Google needs the business name filled in first.
    - `/forgot-password`: the same message for every email.
    - `/reset-password`: reads `#token=` and removes it from the address bar.
  - `GoogleSignInButton`: loads Google's script with `next/script`. It and its "or" line are hidden when `NEXT_PUBLIC_GOOGLE_CLIENT_ID` is empty.
  - Layout C shell:
    - Dark icon rail (shadcn sidebar in icon mode) with an amber needs-review count on Match.
    - Account menu with theme and sign out.
    - Slide-out menu on phones.
    - A `Screen` frame with an inspector slot, and placeholder screens for F2–F7.
  - `safeNextPath()` blocks open redirects through `?next=`. `lib/api.ts` turns "server unreachable" into a clear error.
  - Decisions D-50 (layout C) and D-51 (frontend session). `frontend/CLAUDE.md` updated. Deleted the layout prototype.
- **Checked:** `npm run lint` and `npm run build` pass. In Chrome against the real API:
  - Submitting an empty form shows an error under each field.
  - Registering lands on Overview.
  - The rail, account menu and dark theme work.
  - Sign-out clears the token.
  - A wrong password shows "Incorrect email or password".
  - Forgot → reset → sign in with the new password works; the old password and a reused link are refused.
  - At 375px there's no sideways scroll, and the slide-out menu lists all six screens.
- **Broke (frontend):**
  - This shadcn style ("radix-nova") has no `form` component, so I used its `field` component instead.
  - shadcn's generated `use-mobile.ts` failed the React lint rule (setState inside an effect). I rewrote it with `useSyncExternalStore`.
  - The build failed on stale `.next/dev` types that still pointed at the deleted prototype.
  - The API rejects `.test` email addresses (special-use domain).
  - Browser screenshots timed out under memory pressure, so I checked some screens with JavaScript instead.
- **Learned:** Next 16 renamed `middleware.ts` to `proxy.ts`, and it can't see `localStorage`, so the session check lives in the `(app)` layout. That check is only for the user; the API is the real protection. A token after `#` in a URL never reaches a server. `next/script`'s `onReady` runs on every mount, which redraws Google's button after navigating between pages.
- **Next:** Commit F1. Then F2 Overview: KPI tiles, collections and ageing charts (load the dataviz skill first), and recent activity.

### Day 7 (continued): F2 Overview
- **Built:** Committed and merged F1 into main. On `feat/frontend-overview`:
  - Overview screen with four KPI tiles (Outstanding, Collected this month, Auto-match rate, Needs review → links to Match).
  - Collections by week: a Recharts column chart through shadcn's `chart` wrapper, with a value-first tooltip and a "View as table" fallback.
  - Ageing: a list with a bar per bucket, in validated status colours.
  - Recent activity: the last 8 audit events as plain sentences (`lib/audit-text.ts`, reused later by the Audit page), with "View all".
  - `compactNaira()` for axis ticks only.
  - `backend/seed.py`: a demo workspace created through the real API (invoices due at different dates, a statement over 8 weeks, automatic and manual matches). It refuses to run outside development, and refuses to run twice. CLAUDE.md already listed `python seed.py` but the file didn't exist.
  - Decision D-52.
- **Checked:** Lint and build pass. Seeded a dev database and signed in in Chrome:
  - The figures match the seed by hand (₦437,500.00 outstanding = the five open invoices; 67% = 2 of 3 matches automatic; 2 need review).
  - Light and dark themes both work, the tooltip reads "₦96,750.00 — Week of 31 Aug 2026", and an expired token from the old database sent me back to sign in.
  - At 375px there's no sideways scroll.
- **Broke:**
  - The dataviz validator rejected my first ageing colours (orange vs red ΔE 8.7; red-400 vs red-600 in dark ΔE 14.3), so I re-stepped them.
  - The 2×2 tiles split "₦437,500.00" across two lines on a phone.
  - Recharts' grow-in animation left the columns at zero height on this slow machine.
  - shadcn's tooltip drops the "Week of" label when you give it a custom formatter, so I wrote a small tooltip.
  - A leftover `next start` from the F1 check was still holding port 3000.
  - The seed showed PyJWT warning that my local `backend/.env` JWT_SECRET is only 9 bytes. Fine for development, but production would refuse it (D-43).
- **Learned:** Run the palette validator instead of trusting your eye: two "obviously different" reds weren't. Showing money to the kobo is a layout constraint, not just a formatting rule. A single-series chart needs no legend; the title names it.
- **Next:** Commit F2. Then F3, the Match board: unmatched credits beside candidate invoices, scores with reasons, and accept / allocate part / not this one from the keyboard.

### Day 7 (continued): F3 Match payments
- **Built:** Committed and merged F2. On `feat/frontend-match`:
  - The Match screen from pages/reconciliation.md. Left pane: payments with money still unmatched (payer, amount, narration in mono, a 2px navy border on the selected one). Right pane: the payment in full, then up to three candidate cards.
  - Each card has the invoice number, status badge, "Suggested" tag, an Amount/Name/Date score bar with points written out, plain-English reasons with the two amounts beside them, and Accept / Allocate part… / Not this one.
  - Keyboard: J/K next/previous, 1–3 choose a card, A accept, M allocate, R not this one, ? shortcuts.
  - Allocate dialog: ₦ amount parsed to kobo, limited to what both sides allow; with no card selected it searches open invoices.
  - Toast with Undo, which does a real reversal through the API. "All caught up" empty state. On phones: one pane at a time with a Back button.
  - The app shell is now one screen tall and each screen scrolls on its own (D-53).
- **Checked (Chrome, seeded data):**
  - A accepted Ngozi's suggestion: toast, row faded out, next payment selected, rail badge 2 → 1.
  - Undo sent `POST /allocations/{id}/reverse` (200) and the payment came back.
  - M on the unknown payer opened the invoice search. ₦60,000 was refused ("up to ₦50,000.00"). ₦20,000.50 to INV-0004 left exactly ₦29,999.50.
  - R hid INV-0006 for that payment.
  - The "?" sheet opens. The phone layout swaps panes with no sideways scroll. Overview still scrolls in the new shell.
- **Broke:** The keyboard handler called `.closest()` on the event target, which throws when the target is the window, so I now check it's an element first. The browser tool sent "/" instead of "?". On this slow machine Chrome sometimes paused CSS animations, so a closed dialog stayed in the page until the next frame was drawn (a browser quirk, not the app). Postgres timed out starting while a build was running.
- **Learned:** The screen should never do money maths it then trusts. It sends the request, lets `allocate()` decide, and re-reads the queue. Showing the credit and outstanding amounts beside reasons that contain no money (D-29) makes the matcher's decision checkable at a glance.
- **Next:** Commit F3. Then F4 Invoices: list with status filter, inspector with payments, create/edit draft, send, void.

### Day 7 (continued): F4 Invoices
- **Built:** Committed and merged F3. On `feat/frontend-invoices`:
  - **Backend first, test-first:** `GET /invoices/{id}` now includes `payments[]` (every allocation, reversed ones too, with the bank line), via `allocations.invoice_payments()`. API.md said this would come "in feature 3" but it never had. 3 new tests failed first, then 373 pass.
  - **Invoices screen:**
    - Status tabs (All, Drafts, Sent, Part paid, Overdue, Paid, Void), a 300ms debounced search, paging, and a dense table with money right-aligned.
    - Inspector: subtotal/VAT/total/paid/outstanding, dates, the payment reference, Copy payment link, and the payments list with Reverse.
    - Actions by status: draft → Send (confirm) / Edit; open → Void (disabled while it has money on it); void → nothing.
  - New/Edit dialog: customer select, ₦ amount parsed to kobo, dates. VAT is left to the server.
  - Reason dialog for Void and Reverse.
  - `/invoices/[id]` for phones.
  - `lib/refresh.ts` re-reads every affected list after a change. Decision D-54.
- **Checked (Chrome, seeded data):**
  - The inspector shows INV-0002 with its ₦100,000 automatic payment.
  - Reverse without a reason is refused. With a reason: Paid ₦0.00, Outstanding ₦268,750.00, the payment is listed as "Reversed: …", and the Match badge went 2 → 3.
  - New invoice ₦45,000.10 → the server's VAT is ₦3,375.01 and the total ₦48,375.11. Send → confirm → Sent. Void with a reason → Void.
  - Edit draft INV-0008 to ₦20,000 → VAT ₦1,500.00.
  - The Overdue tab and the "kola" search return the right rows. On a phone a row opens `/invoices/[id]` with no sideways scroll.
- **Broke:** Clicking an invoice crashed the page ("Cannot read properties of null (reading 'id')"). The React Compiler had memoised the Reverse dialog's callback and checked `reversing!.id` while nothing was selected; I fixed it by reading the id with `?.` outside the callback. A void invoice still offered "Copy payment link", so I hid it. The first `shadcn add` hit a network error. Browser-tool clicks on stale element refs did nothing, so I used JavaScript clicks to test the app's logic.
- **Learned:** A `!` non-null assertion silences TypeScript but not the runtime, and with the React Compiler the code inside a callback can run at render time. Testing every status transition (draft → sent → void, paid → reversed) in the real UI found two bugs that lint and the build couldn't.
- **Next:** Commit F4. Then F5 Customers: list with amount owed, aliases for name matching, add and edit.
