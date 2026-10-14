"""/api/v1/workspace: settings for the signed-in user's own workspace. Read it with GET /auth/me."""

from fastapi import APIRouter

from app.auth.schemas import WorkspaceRead
from app.core.deps import OwnerUser, SessionDep
from app.workspaces import service
from app.workspaces.schemas import BankDetails

router = APIRouter(prefix="/workspace", tags=["Workspace"])


@router.put("/bank-details")
def save_bank_details(details: BankDetails, user: OwnerUser, session: SessionDep) -> WorkspaceRead:
    """Owner only (403 for a member): where customers pay by transfer, shown on every public invoice."""
    return service.save_bank_details(session, user, details)
