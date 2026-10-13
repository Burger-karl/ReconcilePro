"""/api/v1/invoices routes. Thin: validate, call the service, map errors to HTTP."""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from app.core.deps import CurrentUser, SessionDep
from app.email import service as email_service
from app.invoices import service
from app.invoices.schemas import (
    EmailResult,
    InvoiceCreate,
    InvoiceDetail,
    InvoiceList,
    InvoiceRead,
    InvoiceStatus,
    InvoiceUpdate,
    SentInvoice,
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


def queue_email(background: BackgroundTasks, email: service.InvoiceEmail) -> None:
    """Send after the response, like password reset emails: a slow mail server never delays the screen."""
    background.add_task(email_service.send_email, to=email.to, subject=email.subject, text=email.text)


@router.post("/{invoice_id}/send")
def send_invoice(
    invoice_id: uuid.UUID, user: CurrentUser, session: SessionDep, background: BackgroundTasks
) -> SentInvoice:
    with http_errors():
        sent, email = service.send_invoice(session, user, invoice_id)
    if email is not None:
        queue_email(background, email)
    return sent


@router.post("/{invoice_id}/email", status_code=status.HTTP_202_ACCEPTED)
def email_invoice(
    invoice_id: uuid.UUID, user: CurrentUser, session: SessionDep, background: BackgroundTasks
) -> EmailResult:
    """Email the payment link to the customer again (open invoices only; 409 otherwise)."""
    with http_errors():
        email = service.email_invoice(session, user, invoice_id)
    queue_email(background, email)
    return EmailResult(emailed_to=email.to)


@router.post("/{invoice_id}/void")
def void_invoice(invoice_id: uuid.UUID, data: VoidRequest, user: CurrentUser, session: SessionDep) -> InvoiceRead:
    with http_errors():
        return service.void_invoice(session, user, invoice_id, data.reason)
