"""audit_events: an append-only record of who did what (invariant 7).

Rows are only ever inserted, never updated or deleted.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.core.time import utc_now


class AuditEvent(SQLModel, table=True):
    __tablename__ = "audit_events"
    # The audit page and dashboard feed read "this workspace, newest first".
    __table_args__ = (Index("ix_audit_events_workspace_created", "workspace_id", "created_at"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id")
    # Null when the system acted (auto-match, Paystack webhook).
    actor_user_id: uuid.UUID | None = Field(default=None, foreign_key="users.id")
    action: str = Field(max_length=60)  # e.g. "invoice.sent"
    entity_type: str = Field(max_length=40)  # e.g. "invoice"
    entity_id: uuid.UUID = Field(index=True)
    # Free-form details (amounts in kobo, before/after values). JSONB so it can be queried later.
    data: dict[str, Any] = Field(default_factory=dict, sa_type=JSONB)
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
