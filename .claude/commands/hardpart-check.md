---
description: Check the current diff against the hard-part invariants
---
Run `git diff` (and `git diff --staged`) and review it against the 8 invariants in CLAUDE.md.

For each invariant, answer: untouched / upheld (cite file:line) / VIOLATED (explain).
Specifically look for:
- float or Decimal used for money
- any insert into payment_allocations outside services/allocation.py
- an invoice status written directly instead of derived
- a query without a workspace_id filter
- a fingerprint or unique constraint that is missing or changed
- a webhook path that does not verify the signature or is not idempotent

Then run `cd backend && pytest -q tests/test_hard_part.py` and report the result.
End with a verdict: SAFE TO COMMIT or FIX FIRST, with a list.
