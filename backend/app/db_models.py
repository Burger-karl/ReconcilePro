"""Imports every feature's models so they register on SQLModel.metadata.

Alembic (autogenerate), the test fixtures (create_all) and scripts/erd.py all import this module,
so a table that is not imported here is invisible to them. Add one line per feature as it gets a models.py:

    from app.audit import models as audit_models  # noqa: F401
from app.auth import models as auth_models  # noqa: F401
from app.customers import models as customers_models  # noqa: F401
from app.invoices import models as invoices_models  # noqa: F401
"""

from sqlmodel import SQLModel

from app.audit import models as audit_models  # noqa: F401
from app.auth import models as auth_models  # noqa: F401
from app.customers import models as customers_models  # noqa: F401
from app.invoices import models as invoices_models  # noqa: F401

metadata = SQLModel.metadata
