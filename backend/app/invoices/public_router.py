"""/api/public/invoices/{token}: the customer's view of an invoice. No login.

The only key is the unguessable public token, created when the invoice is sent.
The "Pay with Paystack" endpoint is added here in feature 6.
"""

from fastapi import APIRouter, HTTPException, status

from app.core.deps import SessionDep
from app.invoices import service
from app.invoices.schemas import PublicInvoice

router = APIRouter(prefix="/api/public/invoices", tags=["Public"])


@router.get("/{token}")
def get_public_invoice(token: str, session: SessionDep) -> PublicInvoice:
    try:
        return service.get_public_invoice(session, token)
    except service.InvoiceNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found") from None
