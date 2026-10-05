"""Print a Mermaid erDiagram built from the real SQLModel tables.

Usage (from backend/):  python scripts/erd.py
Compare the output with docs/ERD.md after changing any models.py; they should list the same
tables, columns and foreign keys (docs/DECISIONS.md D-10).
"""

import sys
from pathlib import Path

# Make `import app` work when run as `python scripts/erd.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db_models import metadata  # noqa: E402


def column_line(column) -> str:
    """One Mermaid attribute line, e.g. `bigint amount_kobo FK`."""
    type_name = str(column.type).lower().replace(" ", "_")
    keys = []
    if column.primary_key:
        keys.append("PK")
    if column.foreign_keys:
        keys.append("FK")
    if column.unique:
        keys.append("UK")
    return f"        {type_name} {column.name} {','.join(keys)}".rstrip()


def main() -> None:
    lines = ["```mermaid", "erDiagram"]

    # Relationships: one line per foreign key, "parent ||--o{ child".
    for table in sorted(metadata.tables.values(), key=lambda t: t.name):
        for fk in sorted(table.foreign_keys, key=lambda f: f.parent.name):
            parent = fk.column.table.name
            optional = "|o" if fk.parent.nullable else "||"
            lines.append(f'    {parent} {optional}--o{{ {table.name} : "{fk.parent.name}"')

    # Entities with their columns.
    for table in sorted(metadata.tables.values(), key=lambda t: t.name):
        lines.append(f"    {table.name} {{")
        lines.extend(column_line(column) for column in table.columns)
        lines.append("    }")

    lines.append("```")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
