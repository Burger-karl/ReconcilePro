"""/api/v1/allocations routes. Undoing an allocation is a reversal, never a delete (invariant 7)."""

import uuid

from fastapi import APIRouter

from app.allocations import service
from app.allocations.http import to_http
from app.allocations.schemas import AllocationRead, ReverseRequest
from app.core.deps import CurrentUser, SessionDep

router = APIRouter(prefix="/allocations", tags=["Allocations"])


@router.post("/{allocation_id}/reverse")
def reverse(allocation_id: uuid.UUID, data: ReverseRequest, user: CurrentUser, session: SessionDep) -> AllocationRead:
    try:
        allocation = service.reverse(
            session, workspace_id=user.workspace_id, allocation_id=allocation_id, actor_user_id=user.id, reason=data.reason
        )
    except service.AllocationError as error:
        raise to_http(error) from None
    session.commit()
    return service.to_read(session, allocation)
