"""/api/public/invoices/{token}: the customer's view of an invoice. No login.

The only key is the unguessable public token, created when the invoice is sent.
"""

from fastapi import APIRouter, HTTPException, status

from app.core.deps import SessionDep
from app.invoices import service
from app.invoices.schemas import PublicInvoice
from app.paystack import service as paystack
from app.paystack.client import PaystackUnavailable
from app.paystack.schemas import PaymentLink

router = APIRouter(prefix="/api/public/invoices", tags=["Public"])


@router.get("/{token}")
def get_public_invoice(token: str, session: SessionDep) -> PublicInvoice:
    try:
        return service.get_public_invoice(session, token)
    except service.InvoiceNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found") from None


@router.post("/{token}/pay")
def pay_invoice(token: str, session: SessionDep) -> PaymentLink:
    """Start a Paystack checkout for the outstanding amount. Nothing is recorded until the webhook arrives."""
    try:
        return paystack.start_payment(session, token)
    except service.InvoiceNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found") from None
    except paystack.PaymentNotPossible as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    except PaystackUnavailable:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Online payment is unavailable right now. Please try again."
        ) from None
