"""Workspace settings. For now only the bank account shown on public invoices (D-61)."""

from sqlmodel import Session

from app.audit.service import record
from app.auth.models import User, Workspace
from app.auth.schemas import WorkspaceRead
from app.workspaces.schemas import BankDetails


def _bank_details(workspace: Workspace) -> dict | None:
    """The saved details as a plain dict for the audit row, or None if none are saved yet."""
    if workspace.bank_account_number is None:
        return None
    return {
        "bank_name": workspace.bank_name,
        "bank_account_number": workspace.bank_account_number,
        "bank_account_name": workspace.bank_account_name,
    }


def save_bank_details(session: Session, user: User, details: BankDetails) -> WorkspaceRead:
    # Always the user's own workspace, taken from the user row, never from the request (invariant 8).
    workspace = session.get(Workspace, user.workspace_id)
    before = _bank_details(workspace)
    workspace.bank_name = details.bank_name
    workspace.bank_account_number = details.bank_account_number
    workspace.bank_account_name = details.bank_account_name
    # Changing where customers send money is a classic fraud move, so keep the old and new account.
    record(
        session,
        workspace_id=workspace.id,
        actor_user_id=user.id,
        action="workspace.bank_details_updated",
        entity_type="workspace",
        entity_id=workspace.id,
        data={"before": before, "after": _bank_details(workspace)},
    )
    session.add(workspace)
    session.commit()
    return WorkspaceRead.model_validate(workspace, from_attributes=True)
