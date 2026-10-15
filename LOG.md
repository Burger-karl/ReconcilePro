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

### Day 7 (continued): F5 Customers
- **Built:** Committed and merged F4. On `feat/frontend-customers`:
  - **Backend, test-first:** a customer's email must now be a valid address, and a blank one means "no email". Paystack needs a real address (D-34), so a bad one would only have failed at payment time. 5 new tests failed first; 378 now pass.
  - **Customers screen:** a search box, a table (name, names on bank statements, email, outstanding), and an inspector with contact details, aliases, what they owe and their invoices (each linking to `/invoices/[id]`).
  - An Add/Edit dialog with aliases one per line, and `/customers/[id]` for phones.
- **Checked:** Types, lint and build pass. Through the running API: a bad email → 422, a blank one is stored as null, blank aliases are dropped and the rest trimmed, PATCH sets the email and replaces the aliases. In Chrome (seeded data):
  - The list shows every customer with the right outstanding (e.g. Bisi ₦168,750.00).
  - Add with "femi-at-bakery" shows "Enter a valid email address, or leave it blank". With a real email it saves, keeping both aliases including "F. ADEYEMI, BAKERY" (the comma survives because aliases go one per line).
  - In a narrow window a row opens `/customers/[id]`: contact, outstanding ₦32,250.00, bank names, and 2 invoices linking to their pages.
  - Edit added "KOLA&SONS LTD" and the panel updated. No console errors.
  - Not checked: the wide-screen inspector, because the browser window was only 980px. It uses the same code pattern as Invoices, which was tested.
  - Decision D-55.
- **Broke:** `npx next start` couldn't find the project's Next.js and started downloading `next@16.4.0`. I stopped it straight away and now start it with `npm start` (the local 16.3.8). The Chrome extension was disconnected at first; I reconnected it.
- **Learned:** Validate data where it is stored, not where it is used. An email typo would otherwise surface weeks later as a failed Paystack checkout. Pick the input shape from the data: bank names can contain commas, so one per line is safer than comma-separated.
- **Next:** Commit F5. Then F6 Statements: CSV upload with the import summary, and the transactions list.

### Day 7 (continued): F6 Statements
- **Built:** Committed and merged F5. On `feat/frontend-statements`:
  - Upload card: choose a CSV, Import, then a plain-English summary (read / new / skipped as duplicates / matched automatically / Paystack payouts / money-out ignored / need you) with a "Match N payments" button. API errors are shown with "nothing from this file was imported".
  - Ledger of every bank and Paystack line with tabs (All, Unmatched, Part matched, Matched, Paystack payouts), status badges (Needs review amber, Matched green, Settlement slate) and paging.
  - Inspector with the narration in mono, amount / matched / still to match, and "where the money went" (every allocation, reversed ones too, linking to the invoice). `/transactions/[id]` for phones.
  - Decision D-56.
- **Checked (Chrome, seeded data, full 1366px width this time):**
  - Uploaded a 4-line CSV built in the page: 3 new, 1 matched to INV-0007 by its reference, 1 payout, 1 money-out ignored, 1 needs review.
  - Uploaded the same file again: 0 new, 3 skipped. Invariant 2 is visible in the UI, and the ledger still had 9 lines.
  - A file in an unknown format was refused with the supported headers listed, and nothing was added.
  - The inspector showed INV-0007 "Matched automatically" ₦32,250.00. The tabs filter correctly. On a phone a row opens `/transactions/[id]` with no sideways scroll.
- **Broke:** My first build was cut off by a 550-second time limit and left no output, so I reran it without one. The upload error ran two sentences together because the API's message has no full stop, so I add one. A Paystack payout's panel said "Still to match ₦9,000.00", which contradicts invariant 6, so payouts now show only their amount and an explanation.
- **Learned:** Testing the upload with a file built in the page (DataTransfer) exercises the real input, change handler and FormData path without needing file access. The duplicate-safe import only builds trust if the UI says so ("already imported before, skipped").
- **Next:** Commit F6. Then F7 Audit log, F8 public invoice page and Paystack return, F9 landing.

### Day 7 (continued): F7 Audit log
- **Built:** Committed and merged F6. On `feat/frontend-audit`:
  - `/audit` lists every event newest first as a sentence, with who, when and amount; 50 a page with Newer/Older.
  - Filter tabs: All, Invoices, Payments, Bank lines, Customers, Imports, Sign-in & security.
  - Selecting an event shows who, the exact time, the raw action, every recorded detail (₦ for `_kobo`, "from → to" for edits) and links to the invoice, customer or bank line. Inspector on wide screens, details under the row on phones.
  - `lib/audit-text.ts` gained `eventDetails()` and `eventLinks()`. Decision D-57.
- **Checked (Chrome, seeded data plus a customer edit, a reversal, a draft edit and a void made through the API):**
  - The list shows "Invoice INV-0008 voided", "Payment match reversed ₦100,000.00", "System" for automatic matches.
  - Details: "Subtotal ₦15,000.00 → ₦20,000.00"; "Phone none → 08031234567" and the bank names before → after; the reversal reason with links to the invoice and the bank line.
  - The Payments tab shows only payment events; Sign-in & security shows its empty state; "Open invoice" opened INV-0002.
  - On a phone the details open under the row with no sideways scroll. Lint and build pass.
- **Broke:** Nothing new. Screenshots still time out now and then on this machine, so I read the page with JavaScript.
- **Learned:** A draft edit records only the field that was sent (subtotal); VAT and total aren't listed because they are recomputed, not edited. An audit page is most useful when every row reads as a sentence and every detail as "before → after".
- **Next:** Commit F7. Then F8: the public invoice page (`/i/[token]`, 375px phones) and the page Paystack returns to.

### Day 7 (continued): F8 Public invoice page and Paystack return
- **Built:** Committed and merged F7. On `feat/frontend-public-invoice`:
  - `/i/[token]` (no login, 375px first): business, number + status badge, amount due (36px), due date, bill-to, subtotal/VAT/total, paid so far.
  - A full-width 48px "Pay ₦X with Paystack" button that redirects only to an `https://*.paystack.com` checkout.
  - Bank-transfer instructions with the reference to quote and a 44px copy button.
  - States: paid (thank you), part paid (charges what's left), void (cancelled, no button), unknown link (plain "Invoice not found").
  - Paystack return (`?reference=…`): shows "confirming" and re-asks the API every 3s for up to a minute. It only says "payment received" when the API says paid; the URL proves nothing.
  - The page is always light, through `forcedTheme` on `/i/` paths. Decision D-58.
- **Checked (Chrome, signed out, saved app theme dark):**
  - The page stayed light. INV-0004 showed everything in the spec's order.
  - Pay with no Paystack key → "Online payment is unavailable right now. Please try again."
  - A customer with no email → "Online payment isn't set up for this invoice. Please pay by bank transfer."
  - Paid, part-paid, void and unknown links each showed the right state.
  - Return flow: opening INV-0009 with `?reference=` showed "confirming" with status still Sent. After a payment was recorded through the API (standing in for the webhook), the page switched by itself to Paid, ₦0.00, "Thank you — payment received."
  - At 375px: Pay button 274×48, copy button 44×44, amount 36px, no sideways scroll.
- **Broke:**
  - The React lint rule banned `Date.now()` during render, so a one-minute timer now flips a "window over" flag.
  - The first return test never updated. Chrome reported the tab as hidden and SWR pauses polling for hidden pages, so I turned on `refreshWhenHidden` for that one-minute window (a customer may switch to their banking app).
  - `notFound()` isn't documented for client components, so the page shows its own "Invoice not found".
- **Learned:** A redirect back from a payment provider is not proof of payment; only the verified webhook is. SWR's polling respects page visibility by default, which is right for dashboards but wrong for a short "waiting for payment" window. The spec asked for a payment date and bank details that the API doesn't have yet; I recorded them as gaps rather than inventing them.
- **Next:** Commit F8. Then F9, the landing page.

## Day 8 — 2026-10-13
- **Built:** Committed and merged F8. F9 landing page on `feat/frontend-landing`:
  - `/` is now the `(marketing)` landing page; the old redirect-only `app/page.tsx` is deleted.
  - Hero: "Know which invoices are paid, without the spreadsheet." beside a real-looking matched-payment card built from the app's own components (score bar, reasons, StatusBadge).
  - "How it works" in three steps, "Numbers you can stand behind" (kobo integers, never paid twice, nothing disappears), and a final "Create free workspace".
  - A server component, prerendered as static HTML. Only `AuthNav` runs in the browser: "Sign in / Create free workspace" for visitors, "Open app" for someone signed in. Each claim's comment names the backend invariant that makes it true. Decision D-59.
- **Checked:**
  - The served HTML contains the title, description and all sections before any JavaScript runs.
  - Header: signed out → "Sign in | Create free workspace"; signed in → "Open app".
  - 375px: no sideways scroll, h1 36px, the preview card fits (328px).
  - Screenshots in light and dark both read well.
  - The call-to-action buttons were only 36px (this shadcn style's `lg`), so I made them 44px and confirmed the class in the served page and the built CSS.
- **Broke:**
  - Chrome reported the tab as hidden, so screenshots timed out until you brought the window to the front.
  - Later Chrome stopped responding altogether and my tab group dropped out twice, so I verified the last change from the served HTML instead of retrying the browser.
  - My seed script once read the wrong task file and tried your own Postgres on port 5432. It was refused and nothing was written; I now read the Postgres task's own output file.
  - Clearing stale `.next/types` was needed again after deleting a page.
- **Learned:** A landing page with no state should be a server component: faster, and indexable. Writing each marketing claim next to the rule that guarantees it keeps the copy honest and gives a ready viva answer.
- **Next:** Commit F9. All nine frontend slices are then done. Left: emailing invoices (Resend, "feature 7"), the API gaps noted in D-58 (payment date, business bank details), and deployment (Render + Vercel, with the D-43 checklist).

### Day 8 (continued): invoice email
- **Built:** Committed and merged F9. On `feat/invoice-email`, test-first (10 new tests failed, then passed; 388 backend tests pass):
  - Sending an invoice emails the payment link when the customer has an email. The response gains `emailed_to`, and `invoice.sent` records it.
  - `POST /invoices/{id}/email` sends it again, only while money is owed; a customer with no email gets a 409. Audited as `invoice.emailed`.
  - The email has the business, number, amount owed (`format_naira`, integer kobo), due date, the `/i/{token}` link and the transfer reference.
  - Frontend: the send toast says where it was emailed; an "Email to customer" button on open invoices; the audit text describes the new events. API.md and D-60 updated.
- **Checked:** Through the running API: send → `emailed_to: bisi@bisistores.ng`; email again → 202; no email → 409 with the message. The logged email reads correctly. Frontend typecheck and lint pass. Click-through in Chrome on seeded data: "Email to customer" toast names the address; a customer with no email gets the 409 message as an error toast; sending a draft says "sent and emailed to ..."; the Audit log shows both events. Production build passes with `next build --webpack`.
- **Broke:** A Python heredoc turned the email's `\n` escapes into real line breaks, which broke the f-strings; fixed by editing the file directly. The Windows console prints "₦" as `₦` in the log (display only).
  - `npm run build` (Turbopack) failed three times with `0xc0000142`: Windows could not start Turbopack's Node worker processes (low memory, 1.3 GB free). The webpack build of the same code passed, so it is the machine, not the code.
  - `seed.py` now sends invoices, so it called Resend for made-up demo addresses. Resend refused my local key (401), so nothing went out. Fixed: the seed blanks the Resend key for its own run, so emails are only logged.
- **Learned:** My local `RESEND_API_KEY` is rejected by Resend (401). Delivery failures are only logged (D-60), so the app still says "emailed". I need a valid key before the demo.
- **Next:** Commit and merge `feat/invoice-email`. Then the D-58 gaps (payment date, bank details) and deployment.

### Day 8 (continued): bank details and payment date on the public invoice
- **Built:** Merged `feat/invoice-email`. On `feat/public-invoice-details`, test-first (18 new tests failed, then passed; 406 backend tests pass):
  - Three nullable bank columns on `workspaces` (Alembic migration `b70d16d3c0f6`). The account number is text, because a 10-digit NUBAN can start with 0.
  - `PUT /workspace/bank-details` in a new `app/workspaces/` feature: owner only (403 for a member), all three fields required, exactly 10 digits. Audited with the old and new account, because changing bank details is a classic invoice fraud.
  - The public invoice API adds the bank fields and `last_paid_on` (value date of the latest non-reversed payment, from the allocations service).
  - Frontend: a Settings screen (rail icon), the public page shows the account with a copy button and "payment received on …", and the audit log describes the change and has a Settings tab. The seed saves a demo account.
- **Checked:** In Chrome on seeded data: the Settings form loads the saved account; "12345" shows "Nigerian account numbers are exactly 10 digits"; saving shows the toast; an open invoice page shows "GTBank · Adaeze Foods Ltd" and the new number; a paid invoice says "payment received on 9 October 2026"; the audit log shows both changes. Migration upgrade, downgrade and `alembic check` pass. Typecheck, lint and the webpack build pass. Not checked: the 375px layout (the browser window couldn't be resized from my tools).
- **Learned:** Pydantic's `str_strip_whitespace` strips before the length and pattern checks, so "  " fails `min_length` and " 0123456789 " passes.
- **Next:** Commit and merge. Maybe put the bank account in the invoice email too (it still only has the link and the reference). Then deployment.

### Day 8 (continued): colour and motion (awaiting my sign-off)
- **Built:** The UI felt too plain, so I picked a teal + navy brand and "lively but calm" motion (D-62). Teal buttons, focus rings and charts; navy rail with a teal active item; a soft teal wash on page headers, the auth pages, the public invoice and the landing hero; a teal band to close the landing page. CSS-only motion in `globals.css`: screens and cards fade up in order, table rows fade in one after another, ageing bars grow, success ticks pop, linked cards lift on hover, overdue dots pulse, and the Overview figures count up (`lib/use-count-up.ts`).
- **Checked:** Typecheck, lint and the webpack build pass. In Chrome (via JavaScript): button, rail, header wash, chart and band colours are the new teal in both themes; no sideways scroll on the landing page; the Overview figures end exactly on the API's numbers (₦437,500.00, ₦80,625.00, 67%, 2).
- **Broke:** In a background tab the figures sat at ₦0.00: browsers don't run `requestAnimationFrame` in hidden tabs. Fixed: no count there, the final figure shows straight away. White on teal-600 is only ~3.7:1, so buttons use teal-700 instead.
- **Learned:** `sibling-index()` would make staggering rows one line of CSS, but Safari and Firefox don't support it yet, so I used `nth-child` delays.
- **Next:** Get my sign-off on the look, then commit the bank-details work and this separately, merge, and deploy.

### Day 8 (continued): modern landing page (awaiting my sign-off)
- **Built:** A more modern landing page (D-63): sticky glass header, drifting teal glows over a dot grid, a pill badge, gradient headline, floating match and Paystack cards, a self-scrolling feature strip, numbered step cards, a bento trust grid with the kobo maths, and a dark call-to-action card with a teal glow. Sections fade up as they scroll into view, using CSS `animation-timeline: view()`, no JavaScript.
- **Broke:** The first version froze the Chrome tab. Moving `blur-3xl` blobs, gradient text with an animated background, and glass blur on several cards are redrawn every frame, too much for this laptop. Fixed: radial-gradient glows that only translate, a static gradient, and glass blur on the header only. The tab then responded straight away and the page had no blur filters left.
- **Learned:** Animating `transform` and `opacity` is cheap, because the browser just moves an existing layer. Animating a blurred element or a background position means repainting every frame. Also: a hidden Chrome window reports `clientWidth` 0, so I checked overflow by confirming every wide element sits inside an `overflow-hidden` parent.
- **Next:** My sign-off, then commit the bank details, colour/motion and landing work, merge, and deploy.

### Day 8 (continued): auth pages redesign (awaiting my sign-off)
- **Built:** Split-screen sign-in pages (D-64). A navy brand panel on wide screens with drifting teal glows, a headline, three true points and a floating "matched automatically" card; the form on the right. `AuthCard` is rounder with a teal-to-cyan top line, and the Google button, fields and submit fade up one after another (`.stagger`). All four auth pages change, because they share the layout and card.
- **Checked:** Typecheck, lint and the webpack build pass. The prerendered `/login` HTML has the brand panel, and the built CSS has the stagger rules. Not checked in the browser: Claude Code stopped the web server because memory was low.
- **Learned:** The login form isn't in the prerendered HTML: `useSearchParams()` sits behind a Suspense boundary, so the browser renders that part.
- **Next:** Look at it in the browser, then commit everything, merge, and deploy.

### Day 8 (continued): "Create workspace" went to the dashboard
- **Broke:** Clicking "Create free workspace" or "Sign in" took me to the dashboard. Not a routing bug: I was still signed in (the demo token from earlier browser checks), and login/register silently redirected signed-in users. The landing page still offered both buttons, so it looked broken.
- **Fixed:** The landing buttons (`components/marketing/start-buttons.tsx`) say "Open your dashboard" when signed in. Login and register show "You're already signed in as … in …", with "Go to your dashboard" and "Sign out and use another account" (`components/auth/already-signed-in.tsx`), so a second business can still be registered. A `signingIn` flag stops that card flashing up between submitting the form and arriving at the dashboard.
- **Checked in Chrome:** Signed in: `/register` shows the card, and all three landing buttons point to `/dashboard`. After "Sign out and use another account": the register form comes back, the token is gone, and the landing buttons go to `/register` and `/login` again. Typecheck, lint and the webpack build pass.

### Day 9 — 2026-10-14
- **Built:** My logo is in (D-65): cut into a mark, a full logo and the favicon/app icons with Pillow in a scratch venv, shown via `components/brand/logo.tsx` on the landing page, the auth pages and the app rail. The landing page got a 3D app preview that straightens as you scroll, a before/after, "follow one payment" with moving dots, a feature bento with a worked VAT/kobo example, tabs for owner/accountant/customer and an FAQ accordion (both added with the shadcn CLI). Cards lift and tilt on hover. I decided against DaisyUI: it clashes with shadcn's colour variables.
- **Checked:** Typecheck, lint and the webpack build pass. The served landing page has every new section, `/icon.png` loads, and the demo login works.
- **Broke:** Postgres wouldn't start after an unclean shutdown: a stale `postmaster.pid` named a dead process. I removed it and Postgres recovered with the data intact. Fixing the root title needed `sed` on line 26, not 25: my first edit hit the wrong line and changed nothing.
- **Learned:** The wordmark has to be text, not the PNG: navy letters vanish in dark mode. An exact reference match has no score, so the landing page says "Exact match", not "100".
- **Next:** My look at it in the browser, then commit everything, merge, and deploy.

### Day 9 (continued): committed and merged
- **Built:** Committed `feat/public-invoice-details` in two commits: the bank details and payment date (backend, Settings, public page), then the ReconcilePro brand, motion, landing, auth pages and logo. Merged into `main` with a merge commit, like the earlier features.
- **Broke:** Claude Code stopped the web and API servers twice because the laptop ran low on memory. Nothing wrong with the apps; next time I run them in my own terminals.
- **Learned:** Some files (`globals.css`, `DECISIONS.md`) hold several features' changes, so a perfectly clean one-feature-per-commit split would need hunk-by-hunk staging. I kept shared files in the second commit instead.
- **Next:** Deploy: Render (API + DB) and Vercel (web). Production needs a strong `JWT_SECRET` (32+ bytes), the Paystack and Resend keys, `GOOGLE_CLIENT_ID`, `FRONTEND_URL`, and the Paystack webhook pointed at `/api/v1/webhooks/paystack`. Still to check: the 375px phone layout.

### Day 10 — 2026-10-15: login limit per IP address
- **Built:** On `feat/login-ip-limit`, test-first (7 new tests failed, then passed; 413 backend tests pass). `/auth/login` already blocked one email after 10 wrong passwords (D-42); now it also blocks an IP address after 30 failed logins in 15 minutes, whatever the emails (D-66). A successful login doesn't clear the address's count. `client_ip()` reads `X-Forwarded-For` from the right, controlled by a new `TRUSTED_PROXY_HOPS` setting (0 locally = header ignored).
- **Broke:** Postgres didn't come back after the PC restarted: a stale `postmaster.pid`. Removed it; it recovered on a new port (49419).
- **Learned:** Password spraying (one password, many emails) never trips a per-email limit. And `X-Forwarded-For` is partly written by the client: only the entries our own proxies append, counted from the right, can be trusted. Uvicorn's `--forwarded-allow-ips="*"` takes the leftmost entry, the spoofable one.
- **Next:** On Render, check which header entry is my real address and set `TRUSTED_PROXY_HOPS`. Commit and merge this branch.

### Day 10 (continued): hardening the login token
- **Built:** Merged the per-IP login limit. On `feat/token-hardening` (D-67): tokens last 2 hours instead of 24; `POST /auth/logout` bumps `token_version` so every copy of the token dies, and is audited; the app's sign-out calls it; a Content-Security-Policy on every page limits where scripts can send data. 6 new tests; 419 backend tests pass. Typecheck, lint and the webpack build pass.
- **Checked:** On the live API: `/me` 200, logout 204, the same token on `/me` 401, a fresh login 200. The CSP header is served on `/login`. Not checked: CSP errors in a real browser, because the Chrome extension wasn't connected.
- **Broke:** I wrote the tests while Postgres was down, so I never saw them fail. I stashed my code and ran them against the old one: 5 of 6 failed, as they should (the 6th, logging in again, passed before too). Also: the test suite drops and recreates every table in `reconcile_test`, which is the same database my dev server uses, so it wiped the demo data. Re-seeded.
- **Learned:** Logout with JWTs needs server state; one version number per user is the cheapest, but it logs out every device. CSP without nonces must allow inline scripts, so it limits where data goes more than what runs.
- **Next:** Check the pages and Google sign-in for CSP errors in a browser. Give dev its own database. Consider the httpOnly cookie with an `/api` proxy.
- **Fixed (same day):** Chrome logged "CSP blocks the use of eval". Not my sign-out code: zod 4 probes `new Function("")` once to decide whether to compile validators, and the CSP blocks it (caught, but still reported). `z.config({ jitless: true })` in `lib/zod-config.ts` skips the probe; no `unsafe-eval` needed. The Google button is hidden because `NEXT_PUBLIC_GOOGLE_CLIENT_ID` isn't set locally; it needs a client ID from Google Cloud Console in both env files.
