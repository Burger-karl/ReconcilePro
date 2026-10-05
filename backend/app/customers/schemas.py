"""Request and response bodies for /api/customers."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.invoices.schemas import InvoiceRead


def _clean_name(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Name cannot be blank")
    return value


def _clean_aliases(values: list[str]) -> list[str]:
    # Trim each alias and drop empty ones; the form sends "" for an empty row.
    return [alias.strip() for alias in values if alias.strip()]


class CustomerCreate(BaseModel):
    name: str = Field(max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    aliases: list[str] = Field(default_factory=list, max_length=20)

    _name = field_validator("name")(_clean_name)
    _aliases = field_validator("aliases")(_clean_aliases)


class CustomerUpdate(BaseModel):
    """Every field optional: only the fields sent are changed."""

    name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    aliases: list[str] | None = Field(default=None, max_length=20)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str | None) -> str | None:
        return None if value is None else _clean_name(value)

    @field_validator("aliases")
    @classmethod
    def clean_aliases(cls, values: list[str] | None) -> list[str] | None:
        return None if values is None else _clean_aliases(values)


class CustomerRead(BaseModel):
    id: uuid.UUID
    name: str
    email: str | None
    phone: str | None
    aliases: list[str]
    # Sum of what is still owed on this customer's sent / part-paid / overdue invoices.
    outstanding_kobo: int
    created_at: datetime


class CustomerDetail(CustomerRead):
    invoices: list[InvoiceRead]


class CustomerList(BaseModel):
    items: list[CustomerRead]
    total: int
