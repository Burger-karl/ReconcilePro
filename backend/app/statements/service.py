"""Import a bank statement: decode -> detect bank -> parse -> fingerprint -> insert new lines only.

Invariant 2 (re-importing adds nothing) is enforced by the DATABASE, not by checking first:
every line gets a fingerprint, transactions has UNIQUE(workspace_id, fingerprint), and we insert with
ON CONFLICT DO NOTHING. A line that is already there is silently skipped, even if two imports of the
same file run at the same moment. RETURNING tells us which lines were really added.

The whole file is one transaction: if any row is bad, nothing is imported.
"""

import hashlib
import uuid
from collections import Counter

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session

from app.audit.service import record
from app.auth.models import User
from app.core.time import utc_now
from app.statements.parsers.base import NormalizedLine, StatementError
from app.statements.parsers.detect import detect_and_parse
from app.statements.schemas import ImportResult
from app.transactions.models import Transaction

SOURCE = "bank_statement"
MAX_FILE_BYTES = 5 * 1024 * 1024  # a year of SME statements is well under 1 MB


class FileTooLarge(Exception):
    pass


# --- pure helpers ------------------------------------------------------------------------------------


def is_settlement(narration: str) -> bool:
    """Paystack paying our collected money out to the bank (invariant 6).

    These are stored with kind="settlement" and never matched to invoices: the individual customer
    payments inside them were already recorded one by one by the Paystack webhook. Matching the
    settlement too would count that money twice.
    """
    return "PAYSTACK" in narration.upper()


def normalise_narration(narration: str) -> str:
    """Upper case, single spaces: the same line exported twice may differ in case or spacing."""
    return " ".join(narration.upper().split())


def fingerprint(workspace_id: uuid.UUID, source: str, line: NormalizedLine, occurrence: int) -> str:
    """sha256 of the fields that identify a statement line (docs/DECISIONS.md D-03).

    line_number is deliberately left out: the same payment is on different lines in overlapping statements.
    """
    parts = [
        str(workspace_id),
        source,
        line.value_date.isoformat(),
        str(line.amount_kobo),
        normalise_narration(line.narration),
        line.bank_reference or "",
        "" if line.balance_kobo is None else str(line.balance_kobo),
    ]
    # Without a running balance, two genuine identical payments (same day, amount, narration) would collide.
    # Numbering identical lines 1, 2, ... within the file keeps both, and re-reading the file gives the
    # same numbers, so a re-import still adds nothing.
    if line.balance_kobo is None:
        parts.append(str(occurrence))
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def fingerprints_for(workspace_id: uuid.UUID, source: str, lines: list[NormalizedLine]) -> list[str]:
    seen: Counter[tuple] = Counter()
    result = []
    for line in lines:
        key = (line.value_date, line.amount_kobo, normalise_narration(line.narration), line.bank_reference)
        seen[key] += 1
        result.append(fingerprint(workspace_id, source, line, occurrence=seen[key]))
    return result


def decode(content: bytes) -> str:
    """Most exports are UTF-8 (sometimes with a BOM); Excel on Windows saves cp1252."""
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("cp1252")


# --- import --------------------------------------------------------------------------------------------


def import_statement(session: Session, user: User, filename: str, content: bytes) -> ImportResult:
    if len(content) > MAX_FILE_BYTES:
        raise FileTooLarge
    if not filename.lower().endswith(".csv"):
        raise StatementError("Upload the statement as a CSV file (export it from your bank, or Save As CSV in Excel)")
    text = decode(content)
    if not text.strip():
        raise StatementError("The file is empty")

    parser, lines = detect_and_parse(text)
    # MVP: only money IN is imported. Debits (charges, withdrawals) are counted and reported, not stored.
    credits = [line for line in lines if line.direction == "credit"]

    rows = [
        {
            # Core insert() doesn't run the model's Python defaults, so id and created_at are set here.
            "id": uuid.uuid4(),
            "workspace_id": user.workspace_id,
            "source": SOURCE,
            "kind": "settlement" if is_settlement(line.narration) else "credit",
            "value_date": line.value_date,
            "amount_kobo": line.amount_kobo,
            "narration": line.narration,
            "bank_reference": line.bank_reference,
            "balance_kobo": line.balance_kobo,
            "payer_name": line.payer_name,
            "external_reference": None,
            "fingerprint": line_fingerprint,
            "created_at": utc_now(),
        }
        for line, line_fingerprint in zip(credits, fingerprints_for(user.workspace_id, SOURCE, credits), strict=True)
    ]
    added_ids: set[uuid.UUID] = set()
    if rows:
        statement = (
            insert(Transaction)
            .values(rows)
            .on_conflict_do_nothing(constraint="uq_transactions_workspace_fingerprint")
            .returning(Transaction.id)
        )
        added_ids = set(session.exec(statement).scalars())

    settlements_added = sum(1 for row in rows if row["id"] in added_ids and row["kind"] == "settlement")
    result = ImportResult(
        bank=parser.NAME,
        rows_read=len(lines),
        added=len(added_ids),
        skipped_duplicates=len(credits) - len(added_ids),
        settlements=settlements_added,
        debits_ignored=len(lines) - len(credits),
    )
    record(
        session,
        workspace_id=user.workspace_id,
        actor_user_id=user.id,
        action="statement.imported",
        entity_type="statement",
        entity_id=uuid.uuid4(),  # imports have no table of their own; this id groups the event
        data={"filename": filename, **result.model_dump()},
    )
    session.commit()
    return result
