"""Workspace and User tables (docs/ERD.md).

A workspace is one SME. Every other table carries workspace_id, and every query filters by
the current user's workspace (invariant 8).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, Column, DateTime
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class Workspace(SQLModel, table=True):
    __tablename__ = "workspaces"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=200)
    # timestamptz: store the moment in UTC, show it in local time in the UI.
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class User(SQLModel, table=True):
    # "user" is a reserved word in PostgreSQL, hence "users" (docs/DECISIONS.md D-09).
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('owner', 'member')", name="ck_users_role"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", index=True)
    # Stored lower-case (the service normalises it), so the unique index is effectively case-insensitive.
    email: str = Field(max_length=320, unique=True)
    password_hash: str
    role: str = Field(default="owner", max_length=20)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
