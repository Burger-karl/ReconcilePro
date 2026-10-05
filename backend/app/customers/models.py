"""customers table (docs/ERD.md)."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel

from app.core.time import utc_now


class Customer(SQLModel, table=True):
    __tablename__ = "customers"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", index=True)
    name: str = Field(max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    # Other names this customer shows up as on bank narrations ("KOLA AND SONS", "K&S LTD").
    # The matcher compares the payer name against name + aliases. A Postgres text[] keeps it one column.
    aliases: list[str] = Field(
        default_factory=list, sa_column=Column(ARRAY(Text), nullable=False, server_default="{}")
    )
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
