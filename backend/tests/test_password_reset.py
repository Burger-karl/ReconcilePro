"""Forgot password and reset password (DECISIONS D-39, D-40, D-41).

The email is never really sent: app.email.service.send_email is replaced by a function that keeps
the message, so a test can pull the reset link out of it like a user clicking it.
"""

import re
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.audit.models import AuditEvent
from app.auth.models import PasswordResetToken, User
from app.core.time import utc_now
from app.email import service as email_service

EMAIL = "ada@adaezefoods.ng"
OLD_PASSWORD = "correct-horse-1"
NEW_PASSWORD = "battery-staple-2"
FORGOT_URL = "/api/v1/auth/forgot-password"
RESET_URL = "/api/v1/auth/reset-password"


@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    sent: list[dict] = []
    monkeypatch.setattr(email_service, "send_email", lambda **message: sent.append(message))
    return sent


@pytest.fixture
def account(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/auth/register", json={"email": EMAIL, "password": OLD_PASSWORD, "workspace_name": "Adaeze Foods"}
    )
    assert response.status_code == 201, response.text
    return response.json()


def token_from(message: dict) -> str:
    # The token is in the URL fragment (#token=...), which browsers never send to a server (D-40).
    match = re.search(r"/reset-password#token=([A-Za-z0-9_\-]+)", message["text"])
    assert match, message["text"]
    return match.group(1)


def request_link(client: TestClient, outbox: list[dict], email: str = EMAIL) -> str:
    response = client.post(FORGOT_URL, json={"email": email})
    assert response.status_code == 202, response.text
    return token_from(outbox[-1])


def login(client: TestClient, password: str, email: str = EMAIL) -> int:
    return client.post("/api/v1/auth/login", json={"email": email, "password": password}).status_code


# --- forgot password --------------------------------------------------------------------------


def test_forgot_password_same_response_for_known_and_unknown_email(
    client: TestClient, account: dict, outbox: list[dict]
) -> None:
    known = client.post(FORGOT_URL, json={"email": EMAIL})
    unknown = client.post(FORGOT_URL, json={"email": "nobody@example.com"})

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert [message["to"] for message in outbox] == [EMAIL]


def test_forgot_password_matches_email_case_insensitively(
    client: TestClient, account: dict, outbox: list[dict]
) -> None:
    client.post(FORGOT_URL, json={"email": "  ADA@AdaezeFoods.NG "})

    assert [message["to"] for message in outbox] == [EMAIL]


def test_forgot_password_stores_only_a_hash_of_the_token(
    client: TestClient, session: Session, account: dict, outbox: list[dict]
) -> None:
    raw = request_link(client, outbox)

    row = session.exec(select(PasswordResetToken)).one()
    assert row.token_hash != raw
    assert raw not in row.token_hash
    assert len(row.token_hash) == 64  # sha256 hex
    assert row.workspace_id == session.get(User, account["user"]["id"]).workspace_id


def test_forgot_password_writes_audit_event(
    client: TestClient, session: Session, account: dict, outbox: list[dict]
) -> None:
    request_link(client, outbox)

    event = session.exec(select(AuditEvent).where(AuditEvent.action == "user.password_reset_requested")).one()
    assert str(event.entity_id) == account["user"]["id"]


def test_at_most_three_reset_emails_per_hour(
    client: TestClient, session: Session, account: dict, outbox: list[dict]
) -> None:
    # Stops this public endpoint being used to flood someone's inbox (D-42).
    responses = [client.post(FORGOT_URL, json={"email": EMAIL}) for _ in range(5)]

    assert {response.status_code for response in responses} == {202}
    assert len({response.text for response in responses}) == 1  # the 4th and 5th look exactly the same
    assert len(outbox) == 3


def test_reset_email_limit_counts_only_the_last_hour(
    client: TestClient, session: Session, account: dict, outbox: list[dict]
) -> None:
    for _ in range(3):
        request_link(client, outbox)
    for row in session.exec(select(PasswordResetToken)).all():
        row.created_at = utc_now() - timedelta(hours=1, minutes=1)
        session.add(row)
    session.flush()

    request_link(client, outbox)

    assert len(outbox) == 4


# --- reset password ---------------------------------------------------------------------------


def test_reset_with_valid_token_changes_password(client: TestClient, account: dict, outbox: list[dict]) -> None:
    raw = request_link(client, outbox)

    response = client.post(RESET_URL, json={"token": raw, "new_password": NEW_PASSWORD})

    assert response.status_code == 204, response.text
    assert login(client, OLD_PASSWORD) == 401
    assert login(client, NEW_PASSWORD) == 200


def test_reset_token_is_single_use(client: TestClient, account: dict, outbox: list[dict]) -> None:
    raw = request_link(client, outbox)
    assert client.post(RESET_URL, json={"token": raw, "new_password": NEW_PASSWORD}).status_code == 204

    again = client.post(RESET_URL, json={"token": raw, "new_password": "attacker-password-3"})

    assert again.status_code == 400
    assert login(client, NEW_PASSWORD) == 200


def test_expired_reset_token_is_rejected(
    client: TestClient, session: Session, account: dict, outbox: list[dict]
) -> None:
    raw = request_link(client, outbox)
    row = session.exec(select(PasswordResetToken)).one()
    row.expires_at = utc_now() - timedelta(seconds=1)
    session.add(row)
    session.flush()

    response = client.post(RESET_URL, json={"token": raw, "new_password": NEW_PASSWORD})

    assert response.status_code == 400
    assert response.json()["detail"] == "This reset link is invalid or has expired"
    assert login(client, OLD_PASSWORD) == 200


def test_requesting_a_new_link_invalidates_the_old_one(client: TestClient, account: dict, outbox: list[dict]) -> None:
    first = request_link(client, outbox)
    second = request_link(client, outbox)

    assert client.post(RESET_URL, json={"token": first, "new_password": NEW_PASSWORD}).status_code == 400
    assert client.post(RESET_URL, json={"token": second, "new_password": NEW_PASSWORD}).status_code == 204


@pytest.mark.parametrize("token", ["", "not-a-real-token", "x" * 200])
def test_unknown_or_garbage_token_is_400(client: TestClient, account: dict, token: str) -> None:
    response = client.post(RESET_URL, json={"token": token, "new_password": NEW_PASSWORD})

    assert response.status_code == 400
    assert login(client, OLD_PASSWORD) == 200


def test_oversized_token_is_422(client: TestClient) -> None:
    response = client.post(RESET_URL, json={"token": "x" * 10_000, "new_password": NEW_PASSWORD})

    assert response.status_code == 422


@pytest.mark.parametrize("password", ["short", "x" * 129])
def test_reset_enforces_the_same_password_rules_as_register(
    client: TestClient, account: dict, outbox: list[dict], password: str
) -> None:
    raw = request_link(client, outbox)

    response = client.post(RESET_URL, json={"token": raw, "new_password": password})

    assert response.status_code == 422
    # A rejected attempt does not burn the link.
    assert client.post(RESET_URL, json={"token": raw, "new_password": NEW_PASSWORD}).status_code == 204


def test_reset_logs_out_existing_sessions(client: TestClient, account: dict, outbox: list[dict]) -> None:
    old_headers = {"Authorization": f"Bearer {account['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=old_headers).status_code == 200

    raw = request_link(client, outbox)
    client.post(RESET_URL, json={"token": raw, "new_password": NEW_PASSWORD})

    assert client.get("/api/v1/auth/me", headers=old_headers).status_code == 401
    new_token = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": NEW_PASSWORD}).json()
    new_headers = {"Authorization": f"Bearer {new_token['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=new_headers).status_code == 200


def test_reset_writes_audit_event(client: TestClient, session: Session, account: dict, outbox: list[dict]) -> None:
    raw = request_link(client, outbox)
    client.post(RESET_URL, json={"token": raw, "new_password": NEW_PASSWORD})

    event = session.exec(select(AuditEvent).where(AuditEvent.action == "user.password_reset")).one()
    user = session.get(User, account["user"]["id"])
    assert event.entity_id == user.id
    assert event.workspace_id == user.workspace_id
    assert event.actor_user_id == user.id
    assert NEW_PASSWORD not in str(event.data)


def test_reset_token_from_one_user_cannot_reset_another(
    client: TestClient, account: dict, outbox: list[dict]
) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "kola@kolasons.ng", "password": "kola-password-1", "workspace_name": "Kola & Sons"},
    )
    adas_token = request_link(client, outbox)

    client.post(RESET_URL, json={"token": adas_token, "new_password": NEW_PASSWORD})

    assert login(client, "kola-password-1", email="kola@kolasons.ng") == 200
    assert login(client, NEW_PASSWORD, email="kola@kolasons.ng") == 401


def test_google_only_user_can_set_a_password_by_reset(
    client: TestClient, session: Session, account: dict, outbox: list[dict]
) -> None:
    user = session.get(User, account["user"]["id"])
    user.password_hash = None
    user.google_sub = "110169484474386276334"
    session.add(user)
    session.flush()

    raw = request_link(client, outbox)
    assert client.post(RESET_URL, json={"token": raw, "new_password": NEW_PASSWORD}).status_code == 204

    assert login(client, NEW_PASSWORD) == 200
