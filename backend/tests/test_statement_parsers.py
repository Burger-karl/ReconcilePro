"""Statement parsing without a database: money text -> kobo, format detection, each bank parser, fingerprints."""

import uuid
from datetime import date
from pathlib import Path

import pytest

from app.statements.parsers import bank_a, bank_b
from app.statements.parsers.base import NormalizedLine, StatementError, parse_naira_to_kobo
from app.statements.parsers.detect import detect_and_parse
from app.statements.service import fingerprint, fingerprints_for, is_settlement

FIXTURES = Path(__file__).parent / "fixtures" / "statements"


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# --- money text -> kobo (invariant 1: never via float) -----------------------------------------------


@pytest.mark.parametrize(
    ("text", "kobo"),
    [
        ("90,000.00", 9_000_000),
        ("96750.00", 9_675_000),
        ("10,750.50", 1_075_050),
        ("120450.75", 12_045_075),
        ("0.29", 29),  # as a float, 0.29 * 100 = 28.999999999999996
        ("1.1", 110),
        ("₦1,250.75", 125_075),
        (" 5000 ", 500_000),
    ],
)
def test_parse_naira_to_kobo(text: str, kobo: int) -> None:
    assert parse_naira_to_kobo(text) == kobo


def test_blank_amount_is_none() -> None:
    assert parse_naira_to_kobo("") is None
    assert parse_naira_to_kobo("   ") is None


@pytest.mark.parametrize("text", ["abc", "1.234", "-500.00", "1,00,0.0.0", "12e3"])
def test_bad_amount_raises(text: str) -> None:
    with pytest.raises(StatementError):
        parse_naira_to_kobo(text)


# --- detection ---------------------------------------------------------------------------------------


def test_detects_bank_a_after_preamble_lines() -> None:
    parser, lines = detect_and_parse(read("bank_a.csv"))

    assert parser is bank_a
    assert len(lines) == 6


def test_detects_bank_b() -> None:
    parser, lines = detect_and_parse(read("bank_b.csv"))

    assert parser is bank_b
    assert len(lines) == 5


def test_unknown_format_is_rejected_with_a_clear_message() -> None:
    with pytest.raises(StatementError, match="Unrecognised statement format"):
        detect_and_parse("Date,Amount,Who\n2026-10-01,100,ME\n")


def test_header_matching_ignores_case_and_spaces() -> None:
    text = "  trans. date , VALUE DATE,reference,debits,credits,balance,remarks\n01-Oct-2026,01-Oct-2026,R1,,100.00,100.00,X\n"

    parser, lines = detect_and_parse(text)

    assert parser is bank_a
    assert lines[0].amount_kobo == 10_000


def test_bad_row_reports_its_line_number() -> None:
    text = read("bank_b.csv").replace("25000.00", "25,OOO.00", 1)

    with pytest.raises(StatementError, match="Line 4"):
        detect_and_parse(text)


# --- bank A ------------------------------------------------------------------------------------------


def test_bank_a_lines() -> None:
    _, lines = detect_and_parse(read("bank_a.csv"))

    kola = lines[0]
    assert kola == NormalizedLine(
        line_number=7,
        value_date=date(2026, 10, 1),
        direction="credit",
        amount_kobo=9_675_000,
        narration="TRF FROM: KOLA AND SONS REF: RCN-VYQESR",
        bank_reference="FT26274A001",
        balance_kobo=109_675_000,
        payer_name="KOLA AND SONS",
    )
    pos = lines[1]
    assert (pos.direction, pos.amount_kobo, pos.payer_name) == ("debit", 1_500_000, None)


# --- bank B ------------------------------------------------------------------------------------------


def test_bank_b_lines_have_no_balance_and_extract_payer() -> None:
    _, lines = detect_and_parse(read("bank_b.csv"))

    first = lines[0]
    assert (first.value_date, first.amount_kobo, first.payer_name) == (date(2026, 10, 1), 9_675_000, "KOLA AND SONS")
    assert all(line.balance_kobo is None for line in lines)
    assert lines[-1].direction == "debit"


# --- settlements (invariant 6) -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("narration", "expected"),
    [
        ("PAYSTACK SETTLEMENT PSTK-STL-88213", True),
        ("PAYSTACK/SETTLEMENT/PSTK-STL-88214", True),
        ("paystack payout 123", True),
        ("TRF FROM: KOLA AND SONS REF: RCN-VYQESR", False),
    ],
)
def test_is_settlement(narration: str, expected: bool) -> None:
    assert is_settlement(narration) is expected


# --- fingerprints (invariant 2, docs/DECISIONS.md D-03) ------------------------------------------------

WORKSPACE = uuid.UUID("11111111-1111-1111-1111-111111111111")


def line(**overrides) -> NormalizedLine:
    values = dict(
        line_number=2, value_date=date(2026, 10, 2), direction="credit", amount_kobo=2_500_000,
        narration="NIP/IFEOMA CATERING/INV 12 OCT", bank_reference=None, balance_kobo=None, payer_name="IFEOMA CATERING",
    )
    return NormalizedLine(**{**values, **overrides})


def test_fingerprint_is_stable_and_ignores_case_and_spacing_in_narration() -> None:
    a = fingerprint(WORKSPACE, "bank_statement", line(), occurrence=1)
    b = fingerprint(WORKSPACE, "bank_statement", line(narration="  nip/ifeoma   catering/inv 12 oct "), occurrence=1)

    assert a == b
    assert len(a) == 64  # sha256 hex


def test_fingerprint_changes_with_amount_date_workspace_and_balance() -> None:
    base = fingerprint(WORKSPACE, "bank_statement", line(), occurrence=1)

    assert base != fingerprint(WORKSPACE, "bank_statement", line(amount_kobo=2_500_001), occurrence=1)
    assert base != fingerprint(WORKSPACE, "bank_statement", line(value_date=date(2026, 10, 3)), occurrence=1)
    assert base != fingerprint(uuid.uuid4(), "bank_statement", line(), occurrence=1)
    assert base != fingerprint(WORKSPACE, "bank_statement", line(balance_kobo=100), occurrence=1)


def test_identical_lines_without_balance_get_different_fingerprints() -> None:
    # Two real ₦25,000 payments from the same customer on the same day must both be kept.
    first, second = fingerprints_for(WORKSPACE, "bank_statement", [line(line_number=3), line(line_number=4)])

    assert first != second


def test_identical_lines_get_the_same_fingerprints_when_the_file_is_read_again() -> None:
    once = fingerprints_for(WORKSPACE, "bank_statement", [line(line_number=3), line(line_number=4)])
    again = fingerprints_for(WORKSPACE, "bank_statement", [line(line_number=3), line(line_number=4)])

    assert once == again


def test_line_number_is_not_part_of_the_fingerprint() -> None:
    # The same payment sits on line 9 of one statement and line 7 of an overlapping one.
    assert fingerprint(WORKSPACE, "bank_statement", line(line_number=9), occurrence=1) == fingerprint(
        WORKSPACE, "bank_statement", line(line_number=7), occurrence=1
    )


def test_unquoted_thousands_separator_is_rejected_not_misread() -> None:
    # "25,000.00" without quotes splits into "25" and "000.00". Reading it as ₦25 would be silent data loss.
    text = "DATE POSTED,VALUE DATE,DESCRIPTION,DEBIT,CREDIT\n2026/10/02,2026/10/02,NIP/IFEOMA/X,,25,000.00\n"

    with pytest.raises(StatementError, match="Line 2: has more columns"):
        detect_and_parse(text)
