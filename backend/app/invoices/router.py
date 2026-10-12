"""/api/v1/invoices routes. Thin: validate, call the service, map errors to HTTP."""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.core.deps import CurrentUser, SessionDep
from app.invoices import service
from app.invoices.schemas import (
    InvoiceCreate,
    InvoiceDetail,
    InvoiceList,
    InvoiceRead,
    InvoiceStatus,
    InvoiceUpdate,
    VoidRequest,
)

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@contextmanager
def http_errors() -> Iterator[None]:
    """Turn the service's exceptions into HTTP responses, in one place for every route."""
    try:
        yield
    except service.InvoiceNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found") from None
    except service.CustomerNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found") from None
    except service.InvoiceConflict as conflict:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(conflict)) from None


@router.get("")
def list_invoices(
    user: CurrentUser,
    session: SessionDep,
    status: InvoiceStatus | None = None,
    customer_id: uuid.UUID | None = None,
    q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> InvoiceList:
    items, total = service.list_invoices(
        session, user, status=status, customer_id=customer_id, q=q, limit=limit, offset=offset
    )
    return InvoiceList(items=items, total=total)


@router.post("", status_code=201)
def create_invoice(data: InvoiceCreate, user: CurrentUser, session: SessionDep) -> InvoiceRead:
    with http_errors():
        return service.create_invoice(session, user, data)


@router.get("/{invoice_id}")
def get_invoice(invoice_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> InvoiceDetail:
    with http_errors():
        return service.get_invoice(session, user, invoice_id)


@router.patch("/{invoice_id}")
def update_invoice(invoice_id: uuid.UUID, data: InvoiceUpdate, user: CurrentUser, session: SessionDep) -> InvoiceRead:
    with http_errors():
        return service.update_invoice(session, user, invoice_id, data)


@router.post("/{invoice_id}/send")
def send_invoice(invoice_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> InvoiceRead:
    with http_errors():
        return service.send_invoice(session, user, invoice_id)


@router.post("/{invoice_id}/void")
def void_invoice(invoice_id: uuid.UUID, data: VoidRequest, user: CurrentUser, session: SessionDep) -> InvoiceRead:
    with http_errors():
        return service.void_invoice(session, user, invoice_id, data.reason)
