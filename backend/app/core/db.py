"""Database engine and the per-request session.

One engine per process (it holds the connection pool). Each request gets its own Session
via the get_session dependency, and the session is closed when the request ends.
"""

from collections.abc import Iterator

from sqlmodel import Session, create_engine

from app.core.config import settings

# pool_pre_ping checks a pooled connection is still alive before using it
# (Render's Postgres closes idle connections).
engine = create_engine(settings.database_url, pool_pre_ping=True)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: `session: Session = Depends(get_session)`.

    Tests override this dependency to use a session inside a rolled-back transaction.
    """
    with Session(engine) as session:
        yield session
