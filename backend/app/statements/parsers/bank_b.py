"""Bank B (synthetic format, see tests/fixtures/statements/README.md).

YYYY/MM/DD dates, plain "96750.00" amounts, separate DEBIT/CREDIT columns, NO balance column and no
reference column. Narrations look like "NIP/KOLA AND SONS/RCN-VYQESR" (NIP = NIBSS instant payment).
"""

import re

from app.statements.parsers.base import NormalizedLine, credit_or_debit, parse_date

NAME = "bank_b"
HEADER = ("date posted", "value date", "description", "debit", "credit")

# The payer is the second "/"-separated part of an NIP transfer.
_PAYER = re.compile(r"^NIP/([^/]+)/", re.IGNORECASE)


def parse_row(row: dict[str, str], line_number: int) -> NormalizedLine | None:
    money = credit_or_debit(row["debit"], row["credit"], line_number)
    if money is None:
        return None
    direction, amount_kobo = money
    narration = row["description"].strip()
    payer = _PAYER.search(narration)
    return NormalizedLine(
        line_number=line_number,
        value_date=parse_date(row["value date"], "%Y/%m/%d", line_number),
        direction=direction,
        amount_kobo=amount_kobo,
        narration=narration,
        bank_reference=None,
        balance_kobo=None,  # this bank doesn't give one; the fingerprint uses an occurrence index instead
        payer_name=payer.group(1).strip() if payer else None,
    )
