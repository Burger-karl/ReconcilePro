"""POST /api/webhooks/paystack — public; Paystack calls it after a customer pays (see service.py)."""

import json
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.deps import SessionDep
from app.paystack import service
from app.paystack.client import PaystackUnavailable
from app.paystack.schemas import WebhookResult

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


@router.post("/paystack")
async def paystack_webhook(
    request: Request,
    session: SessionDep,
    x_paystack_signature: Annotated[str | None, Header()] = None,
) -> WebhookResult:
    # async only so we can read the exact bytes Paystack signed; a parsed body would not hash the same.
    raw_body = await request.body()
    if not service.signature_is_valid(raw_body, x_paystack_signature, settings.paystack_secret_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")
    try:
        payload = json.loads(raw_body)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Body is not JSON") from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Body is not a JSON object")

    # The service uses a normal (blocking) database session and HTTP call. Running it in a worker thread
    # stops it freezing the event loop that serves every other request.
    try:
        outcome = await run_in_threadpool(service.handle_event, session, payload)
    except PaystackUnavailable:
        # Not 200, so Paystack retries later. Retries are safe: a duplicate pays once (invariant 3, D-32).
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not verify with Paystack") from None
    return WebhookResult(status=outcome)
