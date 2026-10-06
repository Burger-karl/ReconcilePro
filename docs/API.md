# API

FastAPI, JSON, all routes under `/api`. Interactive docs at `/docs` once the server runs; the frontend types in
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
| POST | `/api/auth/register` *public* | `email, password, workspace_name` | `{access_token, user}` | creates workspace + owner user in one DB transaction |
| POST | `/api/auth/login` *public* | `email, password` | `{access_token, user}` | |
| GET | `/api/auth/me` | — | `user` + `workspace` | |

## customers — `app/customers/router.py`
| Method | Path | Body / query | Returns |
|--------|------|--------------|---------|
| GET | `/api/customers` | `?q=` search name/alias | list of customers with `outstanding_kobo` |
| POST | `/api/customers` | `name, email?, phone?, aliases[]` | customer |
| GET | `/api/customers/{id}` | — | customer + their invoices |
| PATCH | `/api/customers/{id}` | any of the above | customer (writes audit event) |

## invoices — `app/invoices/router.py`
| Method | Path | Body / query | Returns | Notes |
|--------|------|--------------|---------|-------|
| GET | `/api/invoices` | `?status=paid\|part_paid\|overdue\|sent\|draft\|void&customer_id=&q=` | list with derived `status`, `paid_kobo`, `outstanding_kobo` | status filter works on the derived value |
| POST | `/api/invoices` | `customer_id, description, subtotal_kobo, issue_date, due_date` | invoice (draft) | server computes `vat_kobo`, `total_kobo`, `number`, `reference` (D-02) |
| GET | `/api/invoices/{id}` | — | invoice | allocation history is added in feature 3 |
| PATCH | `/api/invoices/{id}` | fields above | invoice | only while `draft` (else 409); VAT and total recomputed |
| POST | `/api/invoices/{id}/send` | — | invoice | `draft → sent`, sets `sent_at`, `public_token`; 409 if not draft. Email via Resend in feature 7 |
| POST | `/api/invoices/{id}/void` | `reason` (required) | invoice | 409 if already void or if it has non-reversed allocations |

## public — `app/invoices/public_router.py`
| Method | Path | Body | Returns | Notes |
|--------|------|------|---------|-------|
| GET | `/api/public/invoices/{token}` *public* | — | business name, invoice summary, derived status, outstanding | no customer list, no ids of other records |
| POST | `/api/public/invoices/{token}/pay` *public* | — | `{authorization_url}` | initialises a Paystack transaction for the outstanding amount, `metadata.invoice_id` set, callback to `/i/{token}`. 404 unknown token; 409 if paid/void or the customer has no email (D-34); 502 if Paystack is unavailable. Writes nothing; the webhook records the money |

## statements — `app/statements/router.py`
| Method | Path | Body | Returns | Notes |
|--------|------|------|---------|-------|
| POST | `/api/statements/import` | multipart `file` (CSV, ≤ 5 MB) | `{bank, rows_read, added, skipped_duplicates, settlements, debits_ignored, auto_allocated, needs_review}` | detect parser → normalise → fingerprint → `INSERT … ON CONFLICT DO NOTHING` (invariant 2). 400 with the line number if any row is bad (nothing imported), 413 if too large. New credits are auto-matched in the same transaction (D-27) |

## transactions — `app/transactions/router.py`
| Method | Path | Query | Returns |
|--------|------|-------|---------|
| GET | `/api/transactions` | `?source=&kind=&state=unallocated\|part\|allocated&from=&to=` | list with `allocated_kobo`, `unallocated_kobo`, newest value date first |
| GET | `/api/transactions/{id}` | — | transaction + allocation history (reversed ones included) |

## reconciliation — `app/reconciliation/router.py`
| Method | Path | Body | Returns | Notes |
|--------|------|------|---------|-------|
| GET | `/api/reconciliation/queue` | — | `{items, total}`; each item: `transaction` (with `unallocated_kobo`), `suggested_invoice_id`, `candidates[]` (`invoice_id, invoice_number, customer_name, status, outstanding_kobo, score, breakdown{amount,name,date}, reference_match, reasons[]`, best first, max 3) | credits with money left; settlements never appear (invariant 6); rejected pairs left out |
| POST | `/api/reconciliation/allocate` | `transaction_id, invoice_id, amount_kobo, method: suggested\|manual` | 201 allocation | calls `allocations.service.allocate()`; 409 if either side would be over-allocated, 404 if not in this workspace |
| POST | `/api/reconciliation/reject` | `transaction_id, invoice_id` | 204 | audit event `match.rejected`; that pair is not proposed again (D-28) |
| POST | `/api/reconciliation/auto-match` | — | `{auto_allocated}` | re-runs exact-reference matching over all unallocated credits (D-27) |

## allocations — `app/allocations/router.py`
| Method | Path | Body | Returns | Notes |
|--------|------|------|---------|-------|
| POST | `/api/allocations/{id}/reverse` | `reason` (required) | allocation | sets `reversed_at`, writes audit event; never deletes (invariant 7); 409 if already reversed |

## dashboard — `app/dashboard/router.py`
| Method | Path | Returns |
|--------|------|---------|
| GET | `/api/dashboard/summary` | `outstanding_kobo, collected_this_month_kobo, auto_match_rate, needs_review_count` |
| GET | `/api/dashboard/collections` | `?weeks=8` → `[{week_start, collected_kobo}]` |
| GET | `/api/dashboard/ageing` | `[{bucket: current\|1_30\|31_60\|60_plus, outstanding_kobo, count}]` |

## audit — `app/audit/router.py`
| Method | Path | Query | Returns |
|--------|------|-------|---------|
| GET | `/api/audit` | `?entity_type=&entity_id=&limit=&offset=` | list of audit events, newest first |

## webhooks — `app/paystack/router.py`
| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/webhooks/paystack` *public* | 1. read raw body; 2. verify `x-paystack-signature` = HMAC-SHA512(raw body, secret) **before** parsing JSON, else 401; 3. on `charge.success`, confirm with Paystack verify-transaction; 4. in **one DB transaction** insert the transaction (`source=paystack`, `external_reference=reference`) and call `allocate()`; a duplicate hits `UNIQUE(source, external_reference)` and is a no-op (invariant 3); 5. return 200 quickly with `{status: allocated\|unallocated\|duplicate\|ignored}`. 400 if the signed body isn't JSON; 502 if Paystack can't be reached, so it retries (D-30 to D-33) |
