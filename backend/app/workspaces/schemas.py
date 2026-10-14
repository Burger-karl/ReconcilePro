"""Request bodies for workspace settings. The Workspace table itself lives in app/auth/models.py,
because a workspace is created together with its owner at registration."""

from pydantic import BaseModel, ConfigDict, Field


class BankDetails(BaseModel):
    """The account customers pay into by bank transfer (D-61). All three fields are required together."""

    # Strip spaces BEFORE the length and pattern checks, so "  " counts as empty and " 0123456789 " is fine.
    model_config = ConfigDict(str_strip_whitespace=True)

    bank_name: str = Field(min_length=2, max_length=100)
    # NUBAN: every Nigerian bank account number is exactly 10 digits. A typo here would send customers'
    # money to the wrong account, so anything else is refused (422).
    bank_account_number: str = Field(pattern=r"^\d{10}$")
    bank_account_name: str = Field(min_length=2, max_length=200)
