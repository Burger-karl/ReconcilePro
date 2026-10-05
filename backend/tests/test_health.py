from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_tests_run_against_postgres(session: Session) -> None:
    # Guards the conftest: the hard-part tests are meaningless on SQLite.
    version = session.exec(text("SELECT version()")).one()[0]

    assert version.startswith("PostgreSQL")
