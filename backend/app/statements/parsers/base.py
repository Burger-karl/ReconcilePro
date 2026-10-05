"""What every bank parser produces, plus shared helpers.

Each bank exports statements differently (column names, date format, amount format). A parser's only job
is to turn its bank's rows into NormalizedLine objects; everything after that (fingerprints, settlement
detection, inserting) is the same for every bank.

A parser module defines:
    NAME: str                 e.g. "bank_a"
    HEADER: tuple[str, ...]   its header row, lower-case, exactly as exported
    parse_row(row: dict[str, str], line_number: int) -> NormalizedLine | None   (None = skip the row)
"""

import re
from dataclasses import dataclass
from datetime import date, datetime


class StatementError(Exception):
    """The file can't be imported. The message is shown to the user, so it must say what to fix."""


@dataclass(frozen=True)
class NormalizedLine:
    line_number: int  # line in the file, for error messages; NOT part of the fingerprint
    value_date: date
    direction: str  # "credit" (money in) or "debit" (money out)
    amount_kobo: int  # always positive; direction says which way
    narration: str  # exactly as the bank wrote it
    bank_reference: str | None
    balance_kobo: int | None  # running balance after this line, if the bank provides it
    payer_name: str | None  # who sent the money, if it can be read from the narration


_AMOUNT = re.compile(r"^(\d+)(?:\.(\d{1,2}))?$")


def parse_naira_to_kobo(text: str) -> int | None:
    """"90,000.00" -> 9000000. Blank -> None. Anything else -> StatementError.

    Works on the TEXT, never via float: float("0.29") * 100 is 28.999999999999996 (invariant 1).
    Negative amounts are rejected: banks put money out in a separate Debit column.
    """
    cleaned = text.replace(",", "").replace("₦", "").strip()
    if not cleaned:
        return None
    match = _AMOUNT.match(cleaned)
    if match is None:
        raise StatementError(f"'{text.strip()}' is not an amount")
    naira, kobo = match.groups()
    return int(naira) * 100 + int((kobo or "").ljust(2, "0"))


def parse_date(text: str, date_format: str, line_number: int) -> date:
    try:
        return datetime.strptime(text.strip(), date_format).date()
    except ValueError:
        raise StatementError(f"Line {line_number}: '{text.strip()}' is not a date") from None


def credit_or_debit(debit_text: str, credit_text: str, line_number: int) -> tuple[str, int] | None:
    """Most banks have separate Debit and Credit columns with one of them empty.
    Returns ("credit", kobo), ("debit", kobo), or None for a row with neither (e.g. an opening-balance line)."""
    try:
        debit = parse_naira_to_kobo(debit_text)
        credit = parse_naira_to_kobo(credit_text)
    except StatementError as error:
        raise StatementError(f"Line {line_number}: {error}") from None
    if credit and debit:
        raise StatementError(f"Line {line_number}: has both a debit and a credit amount")
    if credit:
        return "credit", credit
    if debit:
        return "debit", debit
    return None


def parse_optional_amount(text: str, line_number: int) -> int | None:
    try:
        return parse_naira_to_kobo(text)
    except StatementError as error:
        raise StatementError(f"Line {line_number}: {error}") from None
