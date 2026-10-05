"""Imports every feature's models so they register on SQLModel.metadata.

Alembic (autogenerate), the test fixtures (create_all) and scripts/erd.py all import this module,
so a table that is not imported here is invisible to them. Add one line per feature as it gets a models.py:

    from app.auth import models as auth_models  # noqa: F401
"""

from sqlmodel import SQLModel

from app.auth import models as auth_models  # noqa: F401

metadata = SQLModel.metadata
