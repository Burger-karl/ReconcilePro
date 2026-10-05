"""Matching: given one bank credit and the workspace's invoices, decide what it probably pays.

PURE functions: plain data in, plain data out. No database, no writes (CLAUDE.md conventions).
The reconciliation feature loads the data, calls match(), and asks allocations.allocate() to
actually move money. That split means every rule here can be unit-tested in milliseconds.

Rules (CLAUDE.md "Matching", details in docs/DECISIONS.md D-25..D-27):
1. Exact reference: an open invoice's payment reference appears in the narration or bank reference,
   ignoring case, spaces and punctuation -> "auto", if the credit is not more than what is outstanding.
2. Otherwise score each open invoice out of 100:
     amount equals outstanding        50
     payer name ~ customer name/alias up to 30 (only if at least 85% similar)
     paid 0-14 days after sending     up to 20 (fewer points the later it is)
   Top score >= 70 AND at least 10 points clear of the next -> "suggested".
3. Anything else -> "review" (the accountant decides). Only sent / part_paid / overdue invoices are candidates.
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import date

from rapidfuzz import fuzz

OPEN_STATUSES = ("sent", "part_paid", "overdue")

AMOUNT_POINTS = 50
NAME_POINTS = 30
DATE_POINTS = 20
NAME_THRESHOLD = 85  # % similarity below which a name earns nothing
DATE_WINDOW_DAYS = 14
SUGGEST_AT = 70
CLEAR_MARGIN = 10  # the top candidate must beat the runner-up by this much
MAX_CANDIDATES = 3


@dataclass(frozen=True)
class CreditIn:
    id: uuid.UUID
    kind: str  # "credit" or "settlement"
    amount_kobo: int  # what is still unallocated on this bank line
    value_date: date
    narration: str
    bank_reference: str | None
    payer_name: str | None


@dataclass(frozen=True)
class InvoiceIn:
    id: uuid.UUID
    number: str
    reference: str
    status: str  # DERIVED status
    customer_name: str
    aliases: tuple[str, ...]
    outstanding_kobo: int
    sent_date: date | None  # in Lagos


@dataclass(frozen=True)
class Breakdown:
    amount: int
    name: int
    date: int


@dataclass(frozen=True)
class Candidate:
    invoice_id: uuid.UUID
    number: str
    customer_name: str
    status: str
    outstanding_kobo: int
    score: int
    breakdown: Breakdown
    reference_match: bool
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MatchResult:
    decision: str  # "auto" | "suggested" | "review"
    invoice_id: uuid.UUID | None  # the invoice to allocate to (auto) or propose (suggested)
    amount_kobo: int | None  # how much to allocate automatically (auto only)
    candidates: list[Candidate]  # best first, at most MAX_CANDIDATES


# --- the pieces --------------------------------------------------------------------------------------------


def normalise_reference(text: str) -> str:
    """Upper case with everything but letters and digits removed: "rcn - vyq esr" -> "RCNVYQESR".
    Customers type references with spaces, lower case, or without the dash."""
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def normalise_name(name: str) -> str:
    """"Kola & Sons Ltd." -> "KOLA AND SONS". Removes what differs between how a business writes its
    name and how a bank prints it: case, "&" vs "AND", punctuation, company suffixes."""
    name = name.upper().replace("&", " AND ")
    name = re.sub(r"[^A-Z0-9 ]", " ", name)
    words = [word for word in name.split() if word not in ("LTD", "LIMITED", "PLC", "NIG", "NIGERIA")]
    return " ".join(words)


def name_points(payer_name: str | None, names: tuple[str, ...]) -> tuple[int, int, str | None]:
    """(points, best similarity %, which name matched). Points only from 85% similarity, scaled up to 30.

    token_set_ratio ignores word order and extra words, so "KOLA AND SONS TRADING" still matches "Kola & Sons".
    """
    if not payer_name:
        return 0, 0, None
    payer = normalise_name(payer_name)
    best_similarity, best_name = 0, None
    for name in names:
        similarity = round(fuzz.token_set_ratio(payer, normalise_name(name)))
        if similarity > best_similarity:
            best_similarity, best_name = similarity, name
    if best_similarity < NAME_THRESHOLD:
        return 0, best_similarity, best_name
    return round(NAME_POINTS * best_similarity / 100), best_similarity, best_name


def date_points(sent_date: date | None, value_date: date) -> int:
    """20 points if paid the day it was sent, falling in a straight line to 0 at 14 days.
    Paid before it was sent (or never sent) earns nothing."""
    if sent_date is None:
        return 0
    days = (value_date - sent_date).days
    if days < 0 or days >= DATE_WINDOW_DAYS:
        return 0
    return round(DATE_POINTS * (DATE_WINDOW_DAYS - days) / DATE_WINDOW_DAYS)


def _score(credit: CreditIn, invoice: InvoiceIn, reference_match: bool) -> Candidate:
    reasons: list[str] = []
    if reference_match:
        reasons.append(f"Reference {invoice.reference} found in the payment details")
        if credit.amount_kobo > invoice.outstanding_kobo:
            reasons.append("Amount is more than the amount outstanding, so it was not allocated automatically")

    amount = AMOUNT_POINTS if credit.amount_kobo == invoice.outstanding_kobo else 0
    if amount:
        reasons.append("Amount equals the amount outstanding")

    name, similarity, matched = name_points(credit.payer_name, (invoice.customer_name, *invoice.aliases))
    if name:
        if matched == invoice.customer_name:
            reasons.append(f"Payer '{credit.payer_name}' matches customer '{invoice.customer_name}' ({similarity}%)")
        else:
            reasons.append(
                f"Payer '{credit.payer_name}' matches alias '{matched}' of customer '{invoice.customer_name}' ({similarity}%)"
            )

    when = date_points(invoice.sent_date, credit.value_date)
    if when:
        days = (credit.value_date - invoice.sent_date).days
        reasons.append("Paid the day the invoice was sent" if days == 0 else
                       f"Paid {days} day{'s' if days != 1 else ''} after the invoice was sent")

    return Candidate(
        invoice_id=invoice.id,
        number=invoice.number,
        customer_name=invoice.customer_name,
        status=invoice.status,
        outstanding_kobo=invoice.outstanding_kobo,
        score=amount + name + when,
        breakdown=Breakdown(amount=amount, name=name, date=when),
        reference_match=reference_match,
        reasons=reasons,
    )


# --- the decision --------------------------------------------------------------------------------------------


def match(credit: CreditIn, invoices: list[InvoiceIn]) -> MatchResult:
    # Invariant 6: settlements are never matched.
    if credit.kind != "credit":
        return MatchResult(decision="review", invoice_id=None, amount_kobo=None, candidates=[])

    open_invoices = [invoice for invoice in invoices if invoice.status in OPEN_STATUSES]
    payment_text = normalise_reference(f"{credit.narration} {credit.bank_reference or ''}")
    referenced = {invoice.id for invoice in open_invoices if normalise_reference(invoice.reference) in payment_text}

    candidates = [_score(credit, invoice, invoice.id in referenced) for invoice in open_invoices]
    # Keep reference matches even with 0 points; drop invoices with nothing in common with the credit.
    candidates = [c for c in candidates if c.reference_match or c.score > 0]
    # Best first: a quoted reference beats any score; then the higher score; then the older invoice number.
    candidates.sort(key=lambda c: (not c.reference_match, -c.score, c.number))
    candidates = candidates[:MAX_CANDIDATES]

    # Rule 1: exactly one open invoice quoted, and the money fits.
    if len(referenced) == 1:
        top = candidates[0]
        if credit.amount_kobo <= top.outstanding_kobo:
            return MatchResult(decision="auto", invoice_id=top.invoice_id, amount_kobo=credit.amount_kobo, candidates=candidates)
        return MatchResult(decision="review", invoice_id=None, amount_kobo=None, candidates=candidates)
    if len(referenced) > 1:
        return MatchResult(decision="review", invoice_id=None, amount_kobo=None, candidates=candidates)

    # Rule 2: a strong, clear-cut score.
    if candidates and candidates[0].score >= SUGGEST_AT:
        runner_up = candidates[1].score if len(candidates) > 1 else 0
        if candidates[0].score - runner_up >= CLEAR_MARGIN:
            return MatchResult(
                decision="suggested", invoice_id=candidates[0].invoice_id, amount_kobo=None, candidates=candidates
            )

    return MatchResult(decision="review", invoice_id=None, amount_kobo=None, candidates=candidates)
