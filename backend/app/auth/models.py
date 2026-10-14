"""Workspace and User tables (docs/ERD.md).

A workspace is one SME. Every other table carries workspace_id, and every query filters by
the current user's workspace (invariant 8).
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Column, DateTime
from sqlmodel import Field, SQLModel

from app.core.time import utc_now


class Workspace(SQLModel, table=True):
    __tablename__ = "workspaces"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=200)
    # Where customers send bank transfers, shown on every public invoice (D-61). All three are set together
    # by the owner (PUT /workspace/bank-details); None until then. The account number is a 10-digit NUBAN,
    # kept as text because it can start with 0.
    bank_name: str | None = Field(default=None, max_length=100)
    bank_account_number: str | None = Field(default=None, max_length=10)
    bank_account_name: str | None = Field(default=None, max_length=200)
    # timestamptz: store the moment in UTC, show it in local time in the UI.
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class User(SQLModel, table=True):
    # "user" is a reserved word in PostgreSQL, hence "users" (docs/DECISIONS.md D-09).
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'member')", name="ck_users_role"),
        # Every user keeps at least one way to sign in.
        CheckConstraint("password_hash IS NOT NULL OR google_sub IS NOT NULL", name="ck_users_can_sign_in"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", index=True)
    # Stored lower-case (the service normalises it), so the unique index is effectively case-insensitive.
    email: str = Field(max_length=320, unique=True)
    # None for someone who only ever signed in with Google; they can set one via forgot password.
    password_hash: str | None = None
    # Google's permanent id for the person ("sub" claim). Emails on a Google account can change; sub never
    # does, so this, not the email, is how a Google sign-in finds its user (D-38).
    google_sub: str | None = Field(default=None, max_length=255, unique=True)
    # Copied into every login token as "ver". A password reset adds 1, so all older tokens stop working (D-41).
    token_version: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    role: str = Field(default="owner", max_length=20)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class PasswordResetToken(SQLModel, table=True):
    """One forgot-password link. Single use, short-lived, and only a hash of the token is stored (D-39)."""

    __tablename__ = "password_reset_tokens"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # Every tenant table carries workspace_id (D-07), even though this one is looked up by token_hash.
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", index=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    # sha256 hex of the token in the emailed link. A leaked database therefore can't be used to reset passwords.
    token_hash: str = Field(max_length=64, unique=True)
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    # Set when the link is used or replaced by a newer one; a used link never works again.
    used_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
