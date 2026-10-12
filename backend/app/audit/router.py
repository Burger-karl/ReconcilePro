"""/api/v1/audit: the workspace's audit trail, newest first (read only; invariant 7)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.audit import service
from app.audit.schemas import AuditEventList, AuditEventRead
from app.core.deps import CurrentUser, SessionDep

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("")
def list_events(
    user: CurrentUser,
    session: SessionDep,
    entity_type: Annotated[str | None, Query(max_length=40)] = None,
    entity_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditEventList:
    rows, total = service.list_events(
        session, user.workspace_id, entity_type=entity_type, entity_id=entity_id, limit=limit, offset=offset
    )
    items = [
        AuditEventRead(**event.model_dump(), actor_email=actor_email)
        for event, actor_email in rows
    ]
    return AuditEventList(items=items, total=total)
