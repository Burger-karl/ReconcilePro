"""Pure functions behind invoices: VAT (docs/DECISIONS.md D-02), derived status (D-05), payment reference.

No database here: these are the rules an examiner will ask about, tested on their own.
"""

from datetime import date

import pytest

from app.invoices.service import REFERENCE_ALPHABET, compute_vat, derive_status, new_reference

# --- VAT: 7.5% of subtotal, rounded half UP to the nearest kobo -------------------------------


@pytest.mark.parametrize(
    ("subtotal_kobo", "expected_vat_kobo"),
    [
        (9_000_000, 675_000),  # ₦90,000.00 -> ₦6,750.00 exactly
        (1_000, 75),  # exact
        (10, 1),  # 0.75 kobo rounds up
        (6, 0),  # 0.45 kobo rounds down
        (20, 2),  # 1.5 kobo: half rounds up
        (60, 5),  # 4.5 kobo: half rounds UP (banker's rounding would give 4)
        (1, 0),  # 0.075 kobo
        (99_999_999_999, 7_500_000_000),  # ~₦1bn: 7,499,999,999.925 -> 7,500,000,000
    ],
)
def test_vat_is_seven_and_a_half_percent_rounded_half_up(subtotal_kobo: int, expected_vat_kobo: int) -> None:
    assert compute_vat(subtotal_kobo) == expected_vat_kobo


def test_vat_returns_an_int_never_a_float() -> None:
    assert type(compute_vat(9_000_000)) is int


# --- Derived status: only draft/sent/void are stored --------------------------------------------

TODAY = date(2026, 10, 5)
DUE_TOMORROW = date(2026, 10, 6)
DUE_YESTERDAY = date(2026, 10, 4)
TOTAL = 9_675_000


@pytest.mark.parametrize(
    ("stored", "paid_kobo", "due", "expected"),
    [
        ("draft", 0, DUE_YESTERDAY, "draft"),  # a draft is never overdue: it was never sent
        ("void", 0, DUE_YESTERDAY, "void"),
        ("void", TOTAL, DUE_TOMORROW, "void"),  # void wins even if money was allocated before voiding
        ("sent", 0, DUE_TOMORROW, "sent"),
        ("sent", 0, TODAY, "sent"),  # due today is not yet overdue
        ("sent", 0, DUE_YESTERDAY, "overdue"),
        ("sent", 1, DUE_TOMORROW, "part_paid"),
        ("sent", TOTAL - 1, DUE_TOMORROW, "part_paid"),  # one kobo short is still part paid
        ("sent", 1, DUE_YESTERDAY, "overdue"),  # late AND part paid -> overdue wins (D-05)
        ("sent", TOTAL, DUE_YESTERDAY, "paid"),  # fully paid is never overdue
        ("sent", TOTAL, DUE_TOMORROW, "paid"),
    ],
)
def test_derive_status(stored: str, paid_kobo: int, due: date, expected: str) -> None:
    assert derive_status(stored, total_kobo=TOTAL, paid_kobo=paid_kobo, due_date=due, today=TODAY) == expected


# --- Payment reference --------------------------------------------------------------------------


def test_reference_format() -> None:
    reference = new_reference()

    assert reference.startswith("RCN-")
    code = reference.removeprefix("RCN-")
    assert len(code) == 6
    assert all(char in REFERENCE_ALPHABET for char in code)


def test_reference_alphabet_has_no_lookalike_characters() -> None:
    # Customers type the reference into their banking app; 0/O and 1/I/L get mistyped.
    for char in "0O1IL":
        assert char not in REFERENCE_ALPHABET
