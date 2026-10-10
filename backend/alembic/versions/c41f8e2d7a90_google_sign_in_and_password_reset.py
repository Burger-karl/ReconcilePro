"""google sign-in and password reset

- users.password_hash becomes nullable: someone who only signs in with Google has no password.
  A CHECK makes sure every user still has at least one way in (password or Google).
- users.google_sub: Google's permanent id for the person, unique (D-38).
- users.token_version: copied into login tokens; a password reset adds 1 to log out old tokens (D-41).
  server_default '0' fills it for existing rows without rewriting their tokens' meaning.
- password_reset_tokens: one row per forgot-password link, storing only a sha256 of the token (D-39).

Revision ID: c41f8e2d7a90
Revises: b7d2e4a91c3f
Create Date: 2026-10-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel  # noqa: F401
from alembic import op


revision: str = 'c41f8e2d7a90'
down_revision: Union[str, Sequence[str], None] = 'b7d2e4a91c3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('users', 'password_hash', existing_type=sqlmodel.sql.sqltypes.AutoString(), nullable=True)
    op.add_column('users', sa.Column('google_sub', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True))
    op.create_unique_constraint('users_google_sub_key', 'users', ['google_sub'])
    op.add_column('users', sa.Column('token_version', sa.Integer(), server_default='0', nullable=False))
    op.create_check_constraint(
        'ck_users_can_sign_in', 'users', 'password_hash IS NOT NULL OR google_sub IS NOT NULL'
    )

    op.create_table('password_reset_tokens',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('workspace_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_password_reset_tokens_user_id'), 'password_reset_tokens', ['user_id'], unique=False)
    op.create_index(
        op.f('ix_password_reset_tokens_workspace_id'), 'password_reset_tokens', ['workspace_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_password_reset_tokens_workspace_id'), table_name='password_reset_tokens')
    op.drop_index(op.f('ix_password_reset_tokens_user_id'), table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')
    op.drop_constraint('ck_users_can_sign_in', 'users', type_='check')
    op.drop_column('users', 'token_version')
    op.drop_constraint('users_google_sub_key', 'users', type_='unique')
    op.drop_column('users', 'google_sub')
    # Fails while Google-only users exist (they have no password); that is deliberate, not data loss.
    op.alter_column('users', 'password_hash', existing_type=sqlmodel.sql.sqltypes.AutoString(), nullable=False)
