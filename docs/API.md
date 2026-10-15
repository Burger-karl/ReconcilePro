# API

FastAPI, JSON, feature routes under `/api/v1` (D-36); `GET /api/health` stays unversioned. Any request body over 6 MB is refused with 413 (D-44). `/docs` and `/openapi.json` exist only when `ENVIRONMENT=development` (D-45). Interactive docs at `/docs` once the server runs; the frontend types in
`frontend/types/api.ts` are generated from `/openapi.json`.

Conventions:
- **Auth:** `Authorization: Bearer <JWT>` on every route except those marked *public*. The token carries `user_id`;
  the `current_user` dependency loads the user and their `workspace_id`. Every query is filtered by that workspace (invariant 8).
- **Money:** every amount field ends in `_kobo` and is an integer. The API never sends formatted naira.
- **Not yours = 404:** asking for another workspace's record returns 404, not 403, so ids don't leak.
- **Errors:** `{"detail": "<human-readable message>"}` with 400 (bad input), 401, 404, 409 (conflict, e.g. over-allocation).
- **Lists:** `?limit=50&offset=0`; response `{ "items": [...], "total": n }`.
- Each router lives in its feature folder: `backend/app/<feature>/router.py` (see DECISIONS D-06).

---

## auth — `app/auth/router.py`
| Method | Path | Body / query | Returns | Notes |
|--------|------|--------------|---------|-------|
| POST | `/api/v1/auth/register` *public* | `email, password, workspace_name` | `{access_token, user}` | creates workspace + owner user in one DB transaction |
| POST | `/api/v1/auth/login` *public* | `email, password` | `{access_token, user}` | 401 same message for wrong email or password; 429 after 10 failures for that email, or 30 from that IP address, in 15 minutes (D-42, D-66) |
| POST | `/api/v1/auth/google/register` *public* | `credential, workspace_name` | 201 `{access_token, user}` | `credential` = Google ID token from the sign-in button. Creates workspace + owner with no password. 409 if that Google account or email is already registered (D-37) |
| POST | `/api/v1/auth/google/login` *public* | `credential` | `{access_token, user}` | finds the user by Google `sub`; links a password account with the same email only when Google owns the address (D-38). 401 if no account |
| POST | `/api/v1/auth/forgot-password` *public* | `email` | 202 `{detail}` | same answer whether or not the email exists; emails a 30-minute single-use link `{FRONTEND_URL}/reset-password#token=…`; at most 3 per account per hour (D-39, D-40, D-42) |
| POST | `/api/v1/auth/reset-password` *public* | `token, new_password` | 204 | 400 for unknown, used or expired links (one message). Logs out every existing session (D-41) |
| GET | `/api/v1/auth/me` | — | `user` + `workspace` | `workspace` includes `bank_name`, `bank_account_number`, `bank_account_name` (null until saved) |
| PUT | `/api/v1/workspace/bank-details` | `bank_name, bank_account_number, bank_account_name` | `workspace` | owner only (403 for a member). All three required; account number exactly 10 digits (NUBAN), else 422. Audited as `workspace.bank_details_updated` with `before`/`after` (D-61) |

Google routes: 401 "Google sign-in failed" for any bad credential; 503 if `GOOGLE_CLIENT_ID` is not set or Google's keys can't be fetched.
Login tokens carry `sub`, `exp` and `ver` (the user's `token_version`); a token whose `ver` no longer matches is 401.
Linking Google to a password account removes the password and ends its sessions (D-46).

## customers — `app/customers/router.py`
| Method | Path | Body / query | Returns |
|--------|------|--------------|---------|
| GET | `/api/v1/customers` | `?q=` search name/alias | list of customers with `outstanding_kobo` |
| POST | `/api/v1/customers` | `name, email?, phone?, aliases[]` | customer (`email` must be a valid address, blank = none: Paystack needs it, D-34) |
| GET | `/api/v1/customers/{id}` | — | customer + their invoices |
| PATCH | `/api/v1/customers/{id}` | any of the above | customer (writes audit event) |

## invoices — `app/invoices/router.py`
| Method | Path | Body / query | Returns | Notes |
|--------|------|--------------|---------|-------|
| GET | `/api/v1/invoices` | `?status=paid\|part_paid\|overdue\|sent\|draft\|void&customer_id=&q=` | list with derived `status`, `paid_kobo`, `outstanding_kobo` | status filter works on the derived value |
| POST | `/api/v1/invoices` | `customer_id, description, subtotal_kobo, issue_date, due_date` | invoice (draft) | server computes `vat_kobo`, `total_kobo`, `number`, `reference` (D-02) |
| GET | `/api/v1/invoices/{id}` | — | invoice + `payments[]` | every allocation to it (reversed ones too, with `reversal_reason`) and the bank line each came from: `id` (allocation), `transaction_id`, `source`, `value_date`, `narration`, `amount_kobo`, `method`, `created_at`, `reversed_at` |
| PATCH | `/api/v1/invoices/{id}` | fields above | invoice | only while `draft` (else 409); VAT and total recomputed |
| POST | `/api/v1/invoices/{id}/send` | — | invoice + `emailed_to` | `draft → sent`, sets `sent_at`, `public_token`; 409 if not draft. If the customer has an email, the payment link is emailed in a background task (D-60); `emailed_to` is that address or `null` |
| POST | `/api/v1/invoices/{id}/email` | — | 202 `{emailed_to}` | emails the payment link again to the customer's current email; 409 unless sent / part_paid / overdue, or if the customer has no email. Audit `invoice.emailed` |
| POST | `/api/v1/invoices/{id}/void` | `reason` (required) | invoice | 409 if already void or if it has non-reversed allocations |

## public — `app/invoices/public_router.py`
| Method | Path | Body | Returns | Notes |
|--------|------|------|---------|-------|
| GET | `/api/v1/public/invoices/{token}` *public* | — | business name, invoice summary, derived status, outstanding, `last_paid_on`, bank details | no customer list, no ids of other records. `last_paid_on` = value date of the latest non-reversed payment; bank fields null until the owner saves them (D-61) |
| POST | `/api/v1/public/invoices/{token}/pay` *public* | — | `{authorization_url}` | initialises a Paystack transaction for the outstanding amount, `metadata.invoice_id` set, callback to `/i/{token}`. 404 unknown token; 409 if paid/void or the customer has no email (D-34); 502 if Paystack is unavailable. Writes nothing; the webhook records the money |

## statements — `app/statements/router.py`
| Method | Path | Body | Returns | Notes |
|--------|------|------|---------|-------|
| POST | `/api/v1/statements/import` | multipart `file` (CSV, ≤ 5 MB) | `{bank, rows_read, added, skipped_duplicates, settlements, debits_ignored, auto_allocated, needs_review}` | detect parser → normalise → fingerprint → `INSERT … ON CONFLICT DO NOTHING` (invariant 2). 400 with the line number if any row is bad (nothing imported), 413 if too large. New credits are auto-matched in the same transaction (D-27) |

## transactions — `app/transactions/router.py`
| Method | Path | Query | Returns |
|--------|------|-------|---------|
| GET | `/api/v1/transactions` | `?source=&kind=&state=unallocated\|part\|allocated&from=&to=` | list with `allocated_kobo`, `unallocated_kobo`, newest value date first |
| GET | `/api/v1/transactions/{id}` | — | transaction + allocation history (reversed ones included) |

## reconciliation — `app/reconciliation/router.py`
| Method | Path | Body | Returns | Notes |
|--------|------|------|---------|-------|
| GET | `/api/v1/reconciliation/queue` | — | `{items, total}`; each item: `transaction` (with `unallocated_kobo`), `suggested_invoice_id`, `candidates[]` (`invoice_id, invoice_number, customer_name, status, outstanding_kobo, score, breakdown{amount,name,date}, reference_match, reasons[]`, best first, max 3) | credits with money left; settlements never appear (invariant 6); rejected pairs left out |
| POST | `/api/v1/reconciliation/allocate` | `transaction_id, invoice_id, amount_kobo, method: suggested\|manual` | 201 allocation | calls `allocations.service.allocate()`; 409 if either side would be over-allocated, 404 if not in this workspace |
| POST | `/api/v1/reconciliation/reject` | `transaction_id, invoice_id` | 204 | audit event `match.rejected`; that pair is not proposed again (D-28) |
| POST | `/api/v1/reconciliation/auto-match` | — | `{auto_allocated}` | re-runs exact-reference matching over all unallocated credits (D-27) |

## allocations — `app/allocations/router.py`
| Method | Path | Body | Returns | Notes |
|--------|------|------|---------|-------|
| POST | `/api/v1/allocations/{id}/reverse` | `reason` (required) | allocation | sets `reversed_at`, writes audit event; never deletes (invariant 7); 409 if already reversed |

## dashboard — `app/dashboard/router.py`
| Method | Path | Returns |
|--------|------|---------|
| GET | `/api/v1/dashboard/summary` | `outstanding_kobo, open_invoice_count, collected_this_month_kobo, auto_match_rate` (whole % or `null`), `needs_review_count` — definitions in D-48 |
| GET | `/api/v1/dashboard/collections` | `?weeks=8` (1–52) → `[{week_start, collected_kobo}]`, Monday weeks, oldest first, empty weeks as 0 |
| GET | `/api/v1/dashboard/ageing` | `[{bucket: current\|1_30\|31_60\|60_plus, outstanding_kobo, count}]`, always all four, by days past due |

## audit — `app/audit/router.py`
| Method | Path | Query | Returns |
|--------|------|-------|---------|
| GET | `/api/v1/audit` | `?entity_type=&entity_id=&limit=` (1–200, default 50) `&offset=` | `{items: [{id, action, entity_type, entity_id, actor_user_id, actor_email, data, created_at}], total}`, newest first; `actor_*` null when the system acted (D-49) |

## webhooks — `app/paystack/router.py`
| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/v1/webhooks/paystack` *public* | 1. read raw body; 2. verify `x-paystack-signature` = HMAC-SHA512(raw body, secret) **before** parsing JSON, else 401; 3. on `charge.success`, confirm with Paystack verify-transaction; 4. in **one DB transaction** insert the transaction (`source=paystack`, `external_reference=reference`) and call `allocate()`; a duplicate hits `UNIQUE(source, external_reference)` and is a no-op (invariant 3); 5. return 200 quickly with `{status: allocated\|unallocated\|duplicate\|ignored}`. 400 if the signed body isn't JSON; 502 if Paystack can't be reached, so it retries (D-30 to D-33) |
