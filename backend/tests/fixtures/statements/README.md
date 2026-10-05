# Synthetic statement fixtures

These CSVs are **made up** for tests. They are not exports from any real bank and contain no real
customer data. `bank_a` and `bank_b` are invented formats modelled on common shapes:

- `bank_a.csv`: preamble lines before the header, `DD-Mon-YYYY` dates, amounts with thousands separators,
  separate Debits/Credits columns, a running Balance, a Reference column.
- `bank_a_overlap.csv`: a later statement whose first two lines repeat the end of `bank_a.csv`.
- `bank_b.csv`: `YYYY/MM/DD` dates, plain amounts, **no balance column**, and two genuinely identical
  payments on the same day (to test the occurrence index in the fingerprint, docs/DECISIONS.md D-03).

When real redacted exports are collected (docs/research/), each new bank format becomes one parser file in
`app/statements/parsers/` plus a fixture here.
