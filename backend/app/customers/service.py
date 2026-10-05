"""Customer logic. Every query filters by the caller's workspace (invariant 8);
every change writes an audit event in the same commit (invariant 7)."""

import uuid

from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.audit.service import record
from app.auth.models import User
from app.customers.models import Customer
from app.customers.schemas import CustomerCreate, CustomerDetail, CustomerRead, CustomerUpdate
from app.invoices import service as invoices


class CustomerNotFound(Exception):
    pass


def _to_read(customer: Customer, outstanding_kobo: int) -> CustomerRead:
    return CustomerRead(
        id=customer.id,
        name=customer.name,
        email=customer.email,
        phone=customer.phone,
        aliases=customer.aliases,
        outstanding_kobo=outstanding_kobo,
        created_at=customer.created_at,
    )


def _get(session: Session, user: User, customer_id: uuid.UUID) -> Customer:
    customer = session.exec(
        select(Customer).where(Customer.id == customer_id, Customer.workspace_id == user.workspace_id)
    ).first()
    if customer is None:
        raise CustomerNotFound
    return customer


def list_customers(
    session: Session, user: User, *, q: str | None = None, limit: int = 50, offset: int = 0
) -> tuple[list[CustomerRead], int]:
    query = select(Customer).where(Customer.workspace_id == user.workspace_id)
    if q and q.strip():
        term = q.strip()
        # Match the name or any alias. array_to_string joins the aliases so one ILIKE covers them all;
        # autoescape stops a "%" typed by the user acting as a wildcard.
        query = query.where(
            or_(
                Customer.name.icontains(term, autoescape=True),
                func.array_to_string(Customer.aliases, " ").icontains(term, autoescape=True),
            )
        )
    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    customers = session.exec(query.order_by(func.lower(Customer.name)).limit(limit).offset(offset)).all()
    owed = invoices.outstanding_by_customer(session, user.workspace_id)
    return [_to_read(customer, owed.get(customer.id, 0)) for customer in customers], total


def get_customer(session: Session, user: User, customer_id: uuid.UUID) -> CustomerDetail:
    customer = _get(session, user, customer_id)
    customer_invoices, _ = invoices.list_invoices(session, user, customer_id=customer.id, limit=1000)
    owed = invoices.outstanding_by_customer(session, user.workspace_id).get(customer.id, 0)
    return CustomerDetail(**_to_read(customer, owed).model_dump(), invoices=customer_invoices)


def create_customer(session: Session, user: User, data: CustomerCreate) -> CustomerRead:
    customer = Customer(workspace_id=user.workspace_id, **data.model_dump())
    session.add(customer)
    record(
        session,
        workspace_id=user.workspace_id,
        actor_user_id=user.id,
        action="customer.created",
        entity_type="customer",
        entity_id=customer.id,
        data={"name": customer.name},
    )
    session.commit()
    return _to_read(customer, 0)


def update_customer(session: Session, user: User, customer_id: uuid.UUID, data: CustomerUpdate) -> CustomerRead:
    customer = _get(session, user, customer_id)
    changes = {}
    # exclude_unset: only fields the client actually sent. Sending "email": null clears the email.
    for field, new_value in data.model_dump(exclude_unset=True).items():
        if field in ("name", "aliases") and new_value is None:
            continue  # name and aliases can't be null
        old_value = getattr(customer, field)
        if old_value != new_value:
            changes[field] = {"from": old_value, "to": new_value}
            setattr(customer, field, new_value)
    if changes:
        record(
            session,
            workspace_id=user.workspace_id,
            actor_user_id=user.id,
            action="customer.updated",
            entity_type="customer",
            entity_id=customer.id,
            data={"changes": changes},
        )
    session.add(customer)
    session.commit()
    owed = invoices.outstanding_by_customer(session, user.workspace_id).get(customer.id, 0)
    return _to_read(customer, owed)
