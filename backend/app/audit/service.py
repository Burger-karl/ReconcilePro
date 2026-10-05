"""record(): the one way to write an audit event.

It only adds the row to the session; it does NOT commit. The caller commits once, so the
change and its audit row are saved together or not at all.
"""

import uuid
from typing import Any

from sqlmodel import Session

from app.audit.models import AuditEvent


def record(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    data: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        data=data or {},
    )
    session.add(event)
    return event
