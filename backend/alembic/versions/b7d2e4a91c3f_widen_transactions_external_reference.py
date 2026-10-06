"""widen transactions.external_reference to TEXT

A Paystack reference longer than 100 characters made the webhook insert fail (500, retried forever).
In PostgreSQL, VARCHAR(n) -> TEXT is a catalogue-only change: no table rewrite, and the unique
constraint on (source, external_reference) is kept.

Revision ID: b7d2e4a91c3f
Revises: 925494443a4b
Create Date: 2026-10-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'b7d2e4a91c3f'
down_revision: Union[str, Sequence[str], None] = '925494443a4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'transactions', 'external_reference',
        existing_type=sa.VARCHAR(length=100), type_=sa.Text(), existing_nullable=True,
    )


def downgrade() -> None:
    # Fails if any stored reference is longer than 100 characters; that is the point of the upgrade.
    op.alter_column(
        'transactions', 'external_reference',
        existing_type=sa.Text(), type_=sa.VARCHAR(length=100), existing_nullable=True,
    )
