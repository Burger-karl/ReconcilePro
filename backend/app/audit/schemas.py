"""Response bodies for /api/v1/audit."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditEventRead(BaseModel):
    id: uuid.UUID
    action: str  # e.g. "invoice.sent"
    entity_type: str
    entity_id: uuid.UUID
    actor_user_id: uuid.UUID | None  # None = the system (auto-match, Paystack)
    actor_email: str | None
    data: dict[str, Any]
    created_at: datetime


class AuditEventList(BaseModel):
    items: list[AuditEventRead]
    total: int
