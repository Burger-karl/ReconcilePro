# ReconcilePro — Product Requirements Document

Status: MVP built, not yet deployed · Last updated: 2026-10-21 · Owner: Charles Kalu

> **How to read this.** Sections 1–6 are the product: the problem, who it's for, what it does and what it
> deliberately doesn't. Sections 7–9 are the parts an instructor is most likely to probe: the rules that keep the
> money right, how the matching works, and how it is kept safe. Section 10 is an honest status. Section 11 lists
> questions to expect, with short answers. Every "D-xx" points to the full reasoning in `docs/DECISIONS.md`.

---

## 1. The problem

A Nigerian small business sends invoices, and its customers pay in two ways:

- **bank transfer**: the money shows up as a line on the bank statement, with a narration the customer typed
  (often a nickname, a typo, or nothing useful), and
- **card or online payment through Paystack**, which later lands in the bank as one lump **settlement** covering
  many customers.

Someone, usually the owner or a part-time accountant, then has to answer, for every naira that came in:
*which invoice did this pay?* Today that is done by hand in Excel: scrolling the statement, guessing who
"ADA FOODS TRF" is, and ticking invoices off. It is slow and error-prone:

- a payment is matched to the **wrong invoice**, or matched **twice**;
- the same statement is imported twice and money is **counted twice**;
- a Paystack settlement is mistaken for a customer payment, so revenue is **double counted**;
- nobody can later say **who** marked an invoice as paid, or why.

## 2. Who it's for

| Person | What they need |
| --- | --- |
| **Owner** of a small business (e.g. a food distributor) | Know who has paid and who owes, without doing the matching themselves |
| **Accountant / bookkeeper** | Clear the payments the system wasn't sure about, quickly, and be able to undo a mistake |
| **The business's customer** | Open an invoice link, see what's owed and pay by card or bank transfer |

> ⚠ The interview and real bank exports for this section are still to be added to `docs/RESEARCH.md`
> (see section 10).

## 3. Goal and success measures

**Goal:** most payments match themselves; the rest go to one short queue where a person decides, and the money
can never be double counted.

| Measure | How it's seen in the app |
| --- | --- |
| Share of incoming money matched automatically | "Auto-match rate" tile on the dashboard (D-48) |
| Payments waiting for a person | "Needs review" count and the Match screen |
| Money still owed, and how late | "Outstanding" tile and the ageing chart (current, 1–30, 31–60, 60+ days) |
| No double counting | Guaranteed by the database rules in section 7, and proved by tests |

## 4. Scope: what the MVP does

1. **Accounts and workspaces.** Register with email and password, or with Google. Each sign-up gets its own
   workspace; nobody can ever see another workspace's data. Forgot-password by email.
2. **Customers.** Name, email, phone, and **aliases** (other names they pay under, e.g. "ADA FOODS" for
   "Adaeze Foods Ltd"). Aliases make name matching work.
3. **Invoices.** Create (subtotal → the server adds 7.5% VAT), send, email the payment link, void with a
   reason. Each invoice gets a number and a separate **payment reference** the customer is asked to quote.
4. **Bank statement import.** Upload a CSV export. Only credits are kept; Paystack settlement lines are
   recognised and set aside; importing the same file again adds nothing.
5. **Automatic matching.** After each import, every new credit is matched to an invoice when that's certain;
   otherwise up to 3 likely invoices are suggested, each with plain-English reasons.
6. **Match screen (exception queue).** Accept a suggestion, pick a different invoice, allocate part of a
   payment, or say "not this one". Every action can be undone (reversed).
7. **Paystack online payment.** The customer's invoice page has a "Pay" button; when Paystack confirms the
   payment, it is recorded and allocated to that invoice automatically.
8. **Public invoice page.** A link per invoice, no login needed: amount owed, status, bank details for transfer,
   and the Pay button. Works on a phone.
9. **Dashboard.** Outstanding, collected this month, auto-match rate, needs-review count, weekly collections,
   ageing.
10. **Audit log.** Every manual action in plain sentences: who did what, when, and the before/after.
11. **Installable app (PWA).** Can be installed on a phone or desktop; shows an offline page with no network
    (D-68).

## 5. Out of scope (deliberately)

- Direct **bank feeds** / open banking: statements come in as CSV uploads.
- **FIRS** tax filing, **WhatsApp** reminders: listed as "Later".
- Invoice **line items**: one description and one amount per invoice (D-04).
- Debits / expenses: only money coming **in** is reconciled (D-20).
- Push notifications, offline use of data (D-68).
- Multiple users with different roles per workspace beyond owner/member.

## 6. Main user flows

**A. Owner bills a customer.** Customers → add "Adaeze Foods" with alias "ADA FOODS" → Invoices → new invoice
₦100,000 + VAT → Send. The customer gets an email with the link.

**B. Customer pays online.** Opens the link → Pay → Paystack card checkout → back on the invoice page, which
shows "Paid" within seconds. Behind the scenes Paystack calls our webhook; we check the signature, confirm with
Paystack, record and allocate the payment in one go.

**C. Customer pays by transfer.** At month end the accountant exports the bank statement as CSV → Statements →
upload. The import reports: lines read, new, duplicates skipped, settlements set aside, auto-matched, needs review.

**D. Accountant clears the queue.** Match screen → each unmatched credit shows its best guesses with reasons
("Amount equals outstanding", "Payer name 92% like ADA FOODS", "Paid 3 days after sending") → Accept, choose
another, or reject. A wrong match is fixed by reversing it, with a reason; nothing is ever deleted.

## 7. The rules that keep the money right

These are the "hard part" of the project and are enforced in code **and** in the database.

| # | Rule | Why |
| --- | --- | --- |
| 1 | All money is whole **kobo** (integers). Never decimals or floats. ₦ formatting only on screen. | `0.1 + 0.2 ≠ 0.3` in floating point; kobo makes every sum exact (D-01) |
| 2 | Re-importing a statement adds nothing: each line has a **fingerprint**, unique per workspace, inserted with `ON CONFLICT DO NOTHING`. | The database itself refuses duplicates, even if two uploads race (D-03, D-21) |
| 3 | A Paystack payment is recorded **once**, however many times the webhook arrives: unique `(source, reference)`, and the payment and its allocation are saved in one transaction. | Paystack retries webhooks; without this a customer could be credited twice (D-30, D-31) |
| 4 | **Only one function, `allocate()`, may link money to an invoice.** It locks both rows, re-adds what is already allocated, and refuses if either the bank line or the invoice would go over. | Two people clicking at once can't over-allocate; proved by threaded race tests (D-17) |
| 5 | Paid / part-paid / overdue is **calculated** from allocations, never stored. | A stored "paid" flag can drift out of step with the money; a calculation can't (D-05) |
| 6 | Paystack **settlement** lines on the statement are never matched to invoices. | That money was already counted when Paystack told us about each payment (D-22) |
| 7 | Allocations are **reversed, never deleted**, and every manual action writes an audit row. | Full history: you can always see what happened and who did it (D-16) |
| 8 | **Every query is filtered by the user's workspace.** Another workspace's record answers 404. | One business can never see another's data, not even that a record exists (D-07) |

## 8. How matching works

1. **Exact reference.** If the invoice's payment reference appears in the narration (ignoring case, spaces and
   punctuation) and the amount is not more than what's owed, it is allocated automatically (D-26).
2. **Otherwise, a score out of 100** for each open invoice (sent, part-paid or overdue only):
   - **50**: the amount equals what's outstanding;
   - **up to 30**: the payer's name is at least 85% similar to the customer's name or an alias;
   - **up to 20**: paid 0–14 days after the invoice was sent, fading with time.
3. A score of **70 or more with one clear winner** is *suggested* (a person still accepts it). Everything else
   waits in the queue with its top 3 candidates.
4. Each candidate comes with human-readable **reasons**, so the accountant can see why, not just a number.

Matching never writes anything itself; only `allocate()` does (rule 4).

## 9. Security and privacy (summary)

- Passwords hashed with **argon2**; the same error for a wrong email or a wrong password.
- **Google sign-in** checks Google's signature, the app id, the issuer, expiry and a verified email (D-37, D-38).
- **Login limits:** 10 failures per email, 30 per IP address, per 15 minutes (D-42, D-66).
- **Login tokens last 2 hours**; sign-out cancels every token for that user (D-67).
- **Content-Security-Policy** limits where the page can load scripts from and send data to (D-67).
- **Paystack webhook** signature checked on the raw body before anything else; the payment is then confirmed
  with Paystack's own API (D-30).
- Password-reset links: single use, 30 minutes, only a hash stored (D-39).
- Uploads over 6 MB refused; API docs hidden in production; production refuses to start with the development
  secret (D-43 to D-45).
- Full review and accepted risks: `docs/SECURITY-REVIEW.md`.

## 10. Status (honest)

**Built and tested**
- Every endpoint in `docs/API.md` and every screen listed in section 4.
- About **420 backend tests** (pytest), including race tests for `allocate()`, duplicate webhooks and
  re-imports. Frontend typecheck, lint and production build pass.
- 68 recorded design decisions (`docs/DECISIONS.md`); daily log (`LOG.md`).

**Not done yet**
| Item | Why it matters | Next step |
| --- | --- | --- |
| **Research evidence** (`docs/RESEARCH.md` is still an empty template): real bank exports, an interview, competitors, Paystack spike, sign-off | It's the Day 1–2 gate, and the reason behind the design | Collect 2–3 redacted statements and one interview; fill the tables |
| **Real bank formats** | The CSV parsers (`bank_a`, `bank_b`) were built on synthetic files until real exports arrive (D-24) | Add a parser per real bank export |
| **Deployment** (Render for API + database, Vercel for web) | Needed for a live demo and for installing the PWA from a phone | Set production secrets, point the Paystack webhook at `/api/v1/webhooks/paystack` |
| **Google sign-in client ID** | The button stays hidden until it is set | Follow `docs/GOOGLE-SIGN-IN.md` |
| **Email sending** | The local Resend key is rejected (401) | Get a valid key for production |
| `docker compose up` not re-checked; 375px phone layout of the app screens not checked | Demo risk | Check before the demo |

## 11. Questions to expect

**Why integers and not decimals for money?** Floats can't represent 0.1 exactly, so sums drift. Kobo
integers are exact, and the database column is `BIGINT` (D-01).

**What stops two people allocating the same payment at once?** `allocate()` takes row locks
(`SELECT … FOR UPDATE`) on the bank line and the invoice, then re-adds existing allocations *after* locking,
and refuses if either would go over. The race tests fail without the locks (D-17).

**What if Paystack sends the same webhook twice?** The second insert hits the unique `(source, reference)`
constraint and is a no-op; because the payment and allocation are in one transaction, there's never a payment
without its allocation or vice versa.

**What if I upload last month's statement again?** Every line's fingerprint already exists, so
`ON CONFLICT DO NOTHING` skips it; the import reports them as "duplicates skipped".

**Why is invoice status calculated instead of stored?** So it can never disagree with the money. Reverse an
allocation and the invoice is automatically "part paid" or "overdue" again.

**Why not delete a wrong match?** Accounting needs history. A reversal keeps the record, the reason and who did
it.

**How do you know a webhook really came from Paystack?** HMAC-SHA512 of the raw body with our secret must equal
the signature header, and then we ask Paystack's verify-transaction API anyway (D-30).

**Why did you put the token in localStorage?** Simpler for a separate API domain. The risks are reduced
with 2-hour tokens, real logout and a CSP. The next step would be an httpOnly cookie behind an `/api` proxy (D-67).

**What would you build next?** Real bank parsers from the research, deployment, then bank feeds and WhatsApp
reminders.

---

## Appendix: where things are

| What | Where |
| --- | --- |
| Backend features (models, schemas, service, router per folder) | `backend/app/<feature>/` |
| The one writer of allocations | `backend/app/allocations/service.py` → `allocate()` |
| Matching (pure scoring) and the exception queue | `backend/app/matching/` · `backend/app/reconciliation/` |
| Statement parsers | `backend/app/statements/parsers/` |
| Paystack webhook | `backend/app/paystack/router.py` |
| Tests | `backend/tests/test_*.py` |
| Screens | `frontend/app/(app)/…` · public invoice page `frontend/app/i/[token]/page.tsx` |
| Database tables | `docs/ERD.md` · Endpoints `docs/API.md` · Decisions `docs/DECISIONS.md` |
