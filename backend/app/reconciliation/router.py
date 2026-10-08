"""/api/v1/reconciliation routes: the exception queue and what the accountant does with it."""

from fastapi import APIRouter, HTTPException, Response, status

from app.allocations import service as allocations
from app.allocations.http import to_http
from app.allocations.schemas import AllocationRead
from app.core.deps import CurrentUser, SessionDep
from app.reconciliation import service
from app.reconciliation.schemas import AllocateRequest, AutoMatchResult, Queue, RejectRequest

router = APIRouter(prefix="/reconciliation", tags=["Reconciliation"])


@router.get("/queue")
def get_queue(user: CurrentUser, session: SessionDep) -> Queue:
    items = service.queue(session, user)
    return Queue(items=items, total=len(items))


@router.post("/allocate", status_code=status.HTTP_201_CREATED)
def allocate(data: AllocateRequest, user: CurrentUser, session: SessionDep) -> AllocationRead:
    try:
        allocation = service.allocate_by_hand(session, user, data)
    except allocations.AllocationError as error:
        raise to_http(error) from None
    return allocations.to_read(session, allocation)


@router.post("/reject", status_code=status.HTTP_204_NO_CONTENT)
def reject(data: RejectRequest, user: CurrentUser, session: SessionDep) -> Response:
    try:
        service.reject(session, user, data.transaction_id, data.invoice_id)
    except service.NotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank line or invoice not found") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/auto-match")
def auto_match(user: CurrentUser, session: SessionDep) -> AutoMatchResult:
    """Re-run exact-reference matching on every unallocated credit (e.g. after sending new invoices)."""
    return AutoMatchResult(auto_allocated=service.run_auto_match(session, user))
