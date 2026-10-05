"""/api/transactions routes (read only)."""

import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status

from app.core.deps import CurrentUser, SessionDep
from app.transactions import service
from app.transactions.schemas import AllocationState, TransactionDetail, TransactionList

router = APIRouter(prefix="/api/transactions", tags=["Transactions"])


@router.get("")
def list_transactions(
    user: CurrentUser,
    session: SessionDep,
    source: Literal["bank_statement", "paystack"] | None = None,
    kind: Literal["credit", "settlement"] | None = None,
    state: AllocationState | None = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TransactionList:
    items, total = service.list_transactions(
        session, user, source=source, kind=kind, state=state, date_from=date_from, date_to=date_to,
        limit=limit, offset=offset,
    )
    return TransactionList(items=items, total=total)


@router.get("/{transaction_id}")
def get_transaction(transaction_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> TransactionDetail:
    try:
        return service.get_transaction(session, user, transaction_id)
    except service.TransactionNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found") from None
