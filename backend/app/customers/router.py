"""/api/v1/customers routes. Thin: validate, call the service, map errors to HTTP."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.core.deps import CurrentUser, SessionDep
from app.customers import service
from app.customers.schemas import CustomerCreate, CustomerDetail, CustomerList, CustomerRead, CustomerUpdate

router = APIRouter(prefix="/customers", tags=["Customers"])

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")


@router.get("")
def list_customers(
    user: CurrentUser,
    session: SessionDep,
    q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CustomerList:
    items, total = service.list_customers(session, user, q=q, limit=limit, offset=offset)
    return CustomerList(items=items, total=total)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_customer(data: CustomerCreate, user: CurrentUser, session: SessionDep) -> CustomerRead:
    return service.create_customer(session, user, data)


@router.get("/{customer_id}")
def get_customer(customer_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> CustomerDetail:
    try:
        return service.get_customer(session, user, customer_id)
    except service.CustomerNotFound:
        raise NOT_FOUND from None


@router.patch("/{customer_id}")
def update_customer(customer_id: uuid.UUID, data: CustomerUpdate, user: CurrentUser, session: SessionDep) -> CustomerRead:
    try:
        return service.update_customer(session, user, customer_id, data)
    except service.CustomerNotFound:
        raise NOT_FOUND from None
