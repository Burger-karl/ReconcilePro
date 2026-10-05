"""Bank A (synthetic format, see tests/fixtures/statements/README.md).

Preamble lines before the header, DD-Mon-YYYY dates, "1,234.56" amounts, separate Debits/Credits columns,
a running Balance and a Reference column. Narrations look like "TRF FROM: KOLA AND SONS REF: RCN-VYQESR".
"""

import re

from app.statements.parsers.base import NormalizedLine, credit_or_debit, parse_date, parse_optional_amount

NAME = "bank_a"
HEADER = ("trans. date", "value date", "reference", "debits", "credits", "balance", "remarks")

# The payer is between "FROM:" and "REF:".
_PAYER = re.compile(r"TRF FROM:\s*(.+?)\s+REF:", re.IGNORECASE)


def parse_row(row: dict[str, str], line_number: int) -> NormalizedLine | None:
    money = credit_or_debit(row["debits"], row["credits"], line_number)
    if money is None:
        return None
    direction, amount_kobo = money
    narration = row["remarks"].strip()
    payer = _PAYER.search(narration)
    return NormalizedLine(
        line_number=line_number,
        value_date=parse_date(row["value date"], "%d-%b-%Y", line_number),
        direction=direction,
        amount_kobo=amount_kobo,
        narration=narration,
        bank_reference=row["reference"].strip() or None,
        balance_kobo=parse_optional_amount(row["balance"], line_number),
        payer_name=payer.group(1).strip() if payer else None,
    )
