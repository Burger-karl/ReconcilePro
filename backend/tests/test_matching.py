"""Matching rules (CLAUDE.md "Matching"), tested as pure functions: no database, no writes.

1. Exact reference in the narration or bank reference (case- and space-insensitive)
   -> auto-allocate, if the amount is <= what is outstanding.
2. Otherwise score each open invoice:
     amount == outstanding           50
     payer name ~ name/aliases >= 85  up to 30
     paid 0-14 days after sending     up to 20 (less the later it is)
   Score >= 70 with one clear top candidate -> suggested. Anything else -> needs review.
3. Only sent / part_paid / overdue invoices are candidates. Every candidate has plain-English reasons.
"""

import uuid
from datetime import date, timedelta

import pytest

from app.matching.service import CreditIn, InvoiceIn, match, name_points, date_points, normalise_reference

SENT = date(2026, 10, 1)


def credit(**overrides) -> CreditIn:
    values = dict(
        id=uuid.uuid4(), kind="credit", amount_kobo=9_675_000, value_date=SENT,
        narration="NIP/KOLA AND SONS/OCT SUPPLIES", bank_reference=None, payer_name="KOLA AND SONS",
    )
    return CreditIn(**{**values, **overrides})


def invoice(**overrides) -> InvoiceIn:
    values = dict(
        id=uuid.uuid4(), number="INV-0001", reference="RCN-VYQESR", status="sent", customer_name="Kola & Sons",
        aliases=(), outstanding_kobo=9_675_000, sent_date=SENT,
    )
    return InvoiceIn(**{**values, **overrides})


# --- 1. exact reference ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "narration",
    ["NIP/KOLA AND SONS/RCN-VYQESR", "trf rcn-vyqesr oct", "NIP/KOLA/RCN VYQESR", "NIP/KOLA/rcnvyqesr/FBN", "RCN - VYQ ESR"],
)
def test_exact_reference_is_case_and_space_insensitive(narration: str) -> None:
    target = invoice()

    result = match(credit(narration=narration, payer_name=None), [target, invoice(reference="RCN-AAAAAA")])

    assert result.decision == "auto"
    assert result.invoice_id == target.id
    assert result.amount_kobo == 9_675_000


def test_reference_in_the_bank_reference_field_counts() -> None:
    target = invoice()

    result = match(credit(narration="TRANSFER", bank_reference="rcn-vyqesr"), [target])

    assert (result.decision, result.invoice_id) == ("auto", target.id)


def test_reference_part_payment_is_auto_allocated() -> None:
    result = match(credit(narration="RCN-VYQESR", amount_kobo=5_000_000), [invoice()])

    assert (result.decision, result.amount_kobo) == ("auto", 5_000_000)


def test_reference_but_more_than_outstanding_needs_review() -> None:
    target = invoice(outstanding_kobo=9_675_000)

    result = match(credit(narration="RCN-VYQESR", amount_kobo=9_675_001), [target])

    assert result.decision == "review"
    top = result.candidates[0]
    assert top.invoice_id == target.id
    assert top.reference_match is True
    assert any("more than" in reason for reason in top.reasons)


def test_two_references_in_one_narration_needs_review() -> None:
    first, second = invoice(), invoice(reference="RCN-K4Q2MX", number="INV-0002")

    result = match(credit(narration="RCN-VYQESR RCN-K4Q2MX"), [first, second])

    assert result.decision == "review"


def test_reference_of_a_draft_or_void_invoice_is_ignored() -> None:
    for status in ("draft", "void", "paid"):
        result = match(credit(narration="RCN-VYQESR"), [invoice(status=status)])
        assert result.decision == "review"
        assert result.candidates == []


def test_normalise_reference() -> None:
    assert normalise_reference(" rcn - vyq esr ") == "RCNVYQESR"


# --- 2. scoring -----------------------------------------------------------------------------------------


def test_perfect_score_without_reference_is_suggested() -> None:
    target = invoice()

    result = match(credit(), [target])

    assert result.decision == "suggested"
    assert result.invoice_id == target.id
    top = result.candidates[0]
    assert top.score == 100
    assert (top.breakdown.amount, top.breakdown.name, top.breakdown.date) == (50, 30, 20)
    assert top.reference_match is False


def test_amount_and_name_is_enough_to_suggest() -> None:
    result = match(credit(value_date=SENT + timedelta(days=30)), [invoice()])

    assert result.decision == "suggested"
    assert result.candidates[0].score == 80


def test_amount_and_date_is_exactly_seventy_and_suggested() -> None:
    result = match(credit(payer_name="SOMEBODY ELSE ENTIRELY"), [invoice()])

    assert result.candidates[0].score == 70
    assert result.decision == "suggested"


def test_amount_only_needs_review() -> None:
    result = match(credit(payer_name="SOMEBODY ELSE", value_date=SENT + timedelta(days=30)), [invoice()])

    assert result.candidates[0].score == 50
    assert result.decision == "review"


def test_name_and_date_without_amount_needs_review() -> None:
    result = match(credit(amount_kobo=1_000_000), [invoice()])

    assert result.candidates[0].score == 50
    assert result.decision == "review"


def test_two_equally_good_invoices_need_review() -> None:
    # Same customer, two identical invoices: we can't know which one they meant.
    result = match(credit(), [invoice(), invoice(number="INV-0002", reference="RCN-K4Q2MX")])

    assert result.decision == "review"
    assert result.candidates[0].score == result.candidates[1].score == 100


def test_clear_winner_among_several_is_suggested() -> None:
    winner = invoice()
    weaker = invoice(number="INV-0002", reference="RCN-K4Q2MX", outstanding_kobo=1_000_000)

    result = match(credit(), [weaker, winner])

    assert result.decision == "suggested"
    assert result.invoice_id == winner.id
    assert [c.invoice_id for c in result.candidates] == [winner.id, weaker.id]  # best first


def test_aliases_are_compared_too() -> None:
    target = invoice(customer_name="Kola & Sons Ltd", aliases=("K AND S TRADING",))

    result = match(credit(payer_name="K AND S TRADING"), [target])

    assert result.candidates[0].breakdown.name == 30


def test_at_most_three_candidates() -> None:
    invoices = [invoice(number=f"INV-{i}", reference=f"RCN-{i:06d}") for i in range(6)]

    assert len(match(credit(), invoices).candidates) == 3


def test_candidates_with_zero_score_are_left_out() -> None:
    result = match(credit(payer_name="NOBODY", amount_kobo=1, value_date=SENT + timedelta(days=60)), [invoice()])

    assert result.candidates == []
    assert result.decision == "review"


# --- 3. candidates and reasons --------------------------------------------------------------------------


def test_part_paid_and_overdue_invoices_are_candidates() -> None:
    for status in ("part_paid", "overdue"):
        assert match(credit(), [invoice(status=status)]).candidates


def test_settlement_lines_are_never_matched() -> None:
    result = match(credit(kind="settlement", narration="PAYSTACK SETTLEMENT RCN-VYQESR"), [invoice()])

    assert result.decision == "review"
    assert result.candidates == []


def test_reasons_are_plain_english() -> None:
    top = match(credit(value_date=SENT + timedelta(days=3)), [invoice()]).candidates[0]

    assert top.reasons == [
        "Amount equals the amount outstanding",
        "Payer 'KOLA AND SONS' matches customer 'Kola & Sons' (100%)",
        "Paid 3 days after the invoice was sent",
    ]


# --- the pieces of the score ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("payer", "names", "points"),
    [
        ("KOLA AND SONS", ("Kola & Sons",), 30),
        ("KOLA & SONS LTD", ("Kola and Sons",), 30),
        ("KOLA AND SON", ("Kola & Sons",), 29),  # very close but not exact: scaled
        ("TUNDE ADEBAYO", ("Kola & Sons",), 0),  # below 85% similarity: nothing
        (None, ("Kola & Sons",), 0),
    ],
)
def test_name_points(payer: str | None, names: tuple[str, ...], points: int) -> None:
    assert name_points(payer, names)[0] == points


@pytest.mark.parametrize(("days", "points"), [(0, 20), (7, 10), (13, 1), (14, 0), (15, 0), (-1, 0)])
def test_date_points_decay_over_fourteen_days(days: int, points: int) -> None:
    assert date_points(SENT, SENT + timedelta(days=days)) == points
