"""Shared pytest fixtures.

Tests run against a real Postgres test database (reconcile_test), never SQLite, because the hard part
relies on Postgres features: SELECT ... FOR UPDATE, ON CONFLICT DO NOTHING, unique constraints.

Isolation: every test runs inside a transaction that is rolled back at the end, so tests never see
each other's rows and the database is left empty. Concurrency tests (two sessions racing each other)
cannot use this, because rolled-back data is invisible to the other session; they get their own
committing fixture when the allocation feature is built.
"""

import os
from collections.abc import Iterator

# Before any app import: settings default to production, which refuses the development JWT secret (D-43).
os.environ.setdefault("ENVIRONMENT", "development")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

import app.db_models  # noqa: F401  (registers every table on SQLModel.metadata)
from app.core.config import settings
from app.core.db import get_session
from app.core.limits import login_attempts
from app.main import app


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """Create all tables once per test run, from the current models."""
    engine = create_engine(settings.test_database_url)
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session whose work is rolled back after the test.

    join_transaction_mode="create_savepoint" means code under test may call session.commit():
    it only releases a savepoint, and the outer transaction is still rolled back here.
    """
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    """HTTP client for the API that uses the rolled-back test session."""
    app.dependency_overrides[get_session] = lambda: session
    # Failed logins are counted in memory per email; start every test from zero.
    login_attempts.reset()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register_headers(client: TestClient, email: str, workspace_name: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-1", "workspace_name": workspace_name},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    """Logged-in owner of workspace "Adaeze Foods"."""
    return register_headers(client, "ada@adaezefoods.ng", "Adaeze Foods")


@pytest.fixture
def other_auth_headers(client: TestClient) -> dict[str, str]:
    """Owner of a DIFFERENT workspace, for invariant 8 (workspace isolation) tests."""
    return register_headers(client, "kola@kolasons.ng", "Kola & Sons")
