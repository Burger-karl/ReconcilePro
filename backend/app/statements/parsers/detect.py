"""Pick the right parser by finding a known header row, then parse every row after it.

Banks often put a few lines (account name, period) above the header, so we look at the first
HEADER_SEARCH_LINES lines for a row that exactly matches one parser's HEADER.
"""

import csv
import io
from types import ModuleType

from app.statements.parsers import bank_a, bank_b
from app.statements.parsers.base import NormalizedLine, StatementError

# Add a new bank by writing its module and listing it here.
PARSERS: list[ModuleType] = [bank_a, bank_b]

HEADER_SEARCH_LINES = 20


def _normalise_header(row: list[str]) -> tuple[str, ...]:
    return tuple(cell.strip().lower() for cell in row if cell.strip())


def detect_and_parse(text: str) -> tuple[ModuleType, list[NormalizedLine]]:
    rows = list(csv.reader(io.StringIO(text)))

    for header_index, row in enumerate(rows[:HEADER_SEARCH_LINES]):
        header = _normalise_header(row)
        parser = next((p for p in PARSERS if p.HEADER == header), None)
        if parser is None:
            continue

        lines: list[NormalizedLine] = []
        for data_index in range(header_index + 1, len(rows)):
            cells = rows[data_index]
            if not any(cell.strip() for cell in cells):
                continue  # blank line
            line_number = data_index + 1  # humans count lines from 1
            # More filled cells than the header means a value was split, e.g. an unquoted "25,000.00"
            # read as "25" and "000.00". Importing that would record ₦25, so refuse the file instead.
            if any(cell.strip() for cell in cells[len(parser.HEADER) :]):
                raise StatementError(
                    f"Line {line_number}: has more columns than the header ({len(parser.HEADER)}). "
                    "Is an amount missing its quotes?"
                )
            # Pad short rows so a missing trailing empty column doesn't break the zip.
            cells = cells + [""] * (len(parser.HEADER) - len(cells))
            row_dict = dict(zip(parser.HEADER, cells, strict=False))
            parsed = parser.parse_row(row_dict, line_number)
            if parsed is not None:
                lines.append(parsed)
        return parser, lines

    known = "; ".join(", ".join(p.HEADER) for p in PARSERS)
    raise StatementError(
        f"Unrecognised statement format. No header row matched a supported bank. Supported headers: {known}"
    )
