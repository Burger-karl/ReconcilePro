"""record(): the one way to write an audit event.

It only adds the row to the session; it does NOT commit. The caller commits once, so the
change and its audit row are saved together or not at all.
"""

import uuid
from typing import Any

from sqlmodel import Session, func, select

from app.audit.models import AuditEvent
from app.auth.models import User


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


def list_events(
    session: Session,
    workspace_id: uuid.UUID,
    *,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[AuditEvent, str | None]], int]:
    """(event, actor's email) for one workspace, newest first, plus the total before paging (invariant 8).

    The email is None when the system acted (auto-match, Paystack webhook).
    """
    filters = [AuditEvent.workspace_id == workspace_id]
    if entity_type is not None:
        filters.append(AuditEvent.entity_type == entity_type)
    if entity_id is not None:
        filters.append(AuditEvent.entity_id == entity_id)
    total = session.exec(select(func.count()).select_from(AuditEvent).where(*filters)).one()
    rows = session.exec(
        select(AuditEvent, User.email)
        # Outer join: system events have no actor, and must still be listed.
        .join(User, User.id == AuditEvent.actor_user_id, isouter=True)
        .where(*filters)
        # id as a tie-breaker so paging is stable when two events share a timestamp.
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(rows), total
