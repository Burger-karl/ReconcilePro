"""Feature 1 — auth + workspace.

Register creates a workspace and its owner in one DB transaction; login returns a JWT;
/api/v1/auth/me needs a valid token. Every later feature scopes queries by the workspace
that comes from this token (invariant 8), so these tests guard the front door.
"""

import time
from datetime import timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.auth.models import User, Workspace
from app.core.config import settings
from app.core.security import create_access_token

REGISTER = {"email": "ada@adaezefoods.ng", "password": "correct-horse-1", "workspace_name": "Adaeze Foods"}


def register(client: TestClient, **overrides) -> dict:
    response = client.post("/api/v1/auth/register", json={**REGISTER, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- register -------------------------------------------------------------------------------


def test_register_creates_workspace_and_owner(client: TestClient, session: Session) -> None:
    body = register(client)

    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "ada@adaezefoods.ng"
    assert body["user"]["role"] == "owner"

    user = session.exec(select(User).where(User.email == "ada@adaezefoods.ng")).one()
    workspace = session.get(Workspace, user.workspace_id)
    assert workspace is not None
    assert workspace.name == "Adaeze Foods"
    assert str(user.workspace_id) == body["user"]["workspace_id"]


def test_register_stores_a_hash_not_the_password(client: TestClient, session: Session) -> None:
    register(client)

    user = session.exec(select(User)).one()
    assert user.password_hash != REGISTER["password"]
    assert user.password_hash.startswith("$argon2")


def test_register_normalises_email(client: TestClient) -> None:
    body = register(client, email="  Ada@AdaezeFoods.NG ")

    assert body["user"]["email"] == "ada@adaezefoods.ng"


def test_duplicate_email_is_rejected_and_creates_no_extra_workspace(
    client: TestClient, session: Session
) -> None:
    register(client)

    response = client.post("/api/v1/auth/register", json={**REGISTER, "email": "ADA@adaezefoods.ng"})

    assert response.status_code == 409
    assert response.json()["detail"] == "An account with this email already exists"
    # The second workspace must not be left behind: workspace + user are one transaction.
    assert session.exec(select(func.count()).select_from(Workspace)).one() == 1


def test_register_rejects_short_password(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json={**REGISTER, "password": "short"})

    assert response.status_code == 422


def test_register_rejects_invalid_email(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json={**REGISTER, "email": "not-an-email"})

    assert response.status_code == 422


def test_register_rejects_blank_workspace_name(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json={**REGISTER, "workspace_name": "   "})

    assert response.status_code == 422


# --- login ----------------------------------------------------------------------------------


def test_login_with_correct_password_returns_token(client: TestClient) -> None:
    register(client)

    response = client.post("/api/v1/auth/login", json={"email": "ADA@adaezefoods.ng", "password": REGISTER["password"]})

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_wrong_password_and_unknown_email_give_the_same_error(client: TestClient) -> None:
    # Same status and message for both, so the login form can't be used to find out who has an account.
    register(client)

    wrong_password = client.post("/api/v1/auth/login", json={"email": REGISTER["email"], "password": "wrong-password"})
    unknown_email = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong-password"})

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json() == {"detail": "Incorrect email or password"}


# --- me / token checks ----------------------------------------------------------------------


def test_me_returns_user_and_their_workspace(client: TestClient) -> None:
    token = register(client)["access_token"]

    response = client.get("/api/v1/auth/me", headers=auth_header(token))

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == REGISTER["email"]
    assert body["workspace"]["name"] == "Adaeze Foods"
    assert body["workspace"]["id"] == body["user"]["workspace_id"]


def test_two_registrations_get_separate_workspaces(client: TestClient) -> None:
    first = register(client)
    second = register(client, email="kola@kolasons.ng", workspace_name="Kola & Sons")

    assert first["user"]["workspace_id"] != second["user"]["workspace_id"]
    me = client.get("/api/v1/auth/me", headers=auth_header(second["access_token"])).json()
    assert me["workspace"]["name"] == "Kola & Sons"


def test_me_without_token_is_401(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_with_garbage_token_is_401(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me", headers=auth_header("not-a-jwt")).status_code == 401


def test_me_with_token_signed_by_another_secret_is_401(client: TestClient) -> None:
    user_id = register(client)["user"]["id"]
    forged = jwt.encode({"sub": user_id}, "some-other-secret-that-is-at-least-32-bytes", algorithm="HS256")

    assert client.get("/api/v1/auth/me", headers=auth_header(forged)).status_code == 401


def test_me_with_expired_token_is_401(client: TestClient) -> None:
    user_id = register(client)["user"]["id"]
    expired = create_access_token(user_id, token_version=0, expires_in=timedelta(seconds=-1))

    assert client.get("/api/v1/auth/me", headers=auth_header(expired)).status_code == 401


def test_me_with_token_for_deleted_user_is_401(client: TestClient, session: Session) -> None:
    body = register(client)
    session.delete(session.get(User, body["user"]["id"]))
    session.flush()

    assert client.get("/api/v1/auth/me", headers=auth_header(body["access_token"])).status_code == 401


def test_token_does_not_carry_workspace_id(client: TestClient) -> None:
    # The workspace is always loaded from the database via the user, never trusted from the token,
    # so moving a user between workspaces can't be undone by an old token.
    token = register(client)["access_token"]

    claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])

    # "ver" is the user's token_version: a password reset bumps it, which logs out old tokens (D-41).
    assert set(claims) == {"sub", "exp", "ver"}


@pytest.mark.parametrize("ver", [None, 1, "0", True])
def test_token_with_missing_or_wrong_version_is_401(client: TestClient, ver) -> None:
    user_id = register(client)["user"]["id"]
    claims = {"sub": user_id, "exp": int(time.time()) + 600}
    if ver is not None:
        claims["ver"] = ver
    token = jwt.encode(claims, settings.jwt_secret, algorithm="HS256")

    assert client.get("/api/v1/auth/me", headers=auth_header(token)).status_code == 401


# --- token lifetime and logout (D-67) -----------------------------------------------------------


def test_login_token_lasts_two_hours(client: TestClient) -> None:
    token = register(client)["access_token"]
    claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])

    # A stolen token is useful for at most this long (it was 24 hours).
    assert claims["exp"] - time.time() == pytest.approx(2 * 60 * 60, abs=60)


def test_logout_stops_the_token_working(client: TestClient) -> None:
    token = register(client)["access_token"]

    assert client.post("/api/v1/auth/logout", headers=auth_header(token)).status_code == 204

    # A JWT can't be deleted, but its version no longer matches the user's, so it is refused (D-41).
    assert client.get("/api/v1/auth/me", headers=auth_header(token)).status_code == 401


def test_logout_signs_out_every_device(client: TestClient) -> None:
    phone = register(client)["access_token"]
    laptop = client.post(
        "/api/v1/auth/login", json={"email": REGISTER["email"], "password": REGISTER["password"]}
    ).json()["access_token"]

    client.post("/api/v1/auth/logout", headers=auth_header(laptop))

    assert client.get("/api/v1/auth/me", headers=auth_header(phone)).status_code == 401


def test_signing_in_again_after_logout_works(client: TestClient) -> None:
    client.post("/api/v1/auth/logout", headers=auth_header(register(client)["access_token"]))

    response = client.post("/api/v1/auth/login", json={"email": REGISTER["email"], "password": REGISTER["password"]})

    assert response.status_code == 200
    assert client.get("/api/v1/auth/me", headers=auth_header(response.json()["access_token"])).status_code == 200


def test_logout_needs_a_valid_token(client: TestClient) -> None:
    assert client.post("/api/v1/auth/logout").status_code == 401


def test_logout_is_audited(client: TestClient, session: Session) -> None:
    from app.audit.models import AuditEvent

    body = register(client)
    client.post("/api/v1/auth/logout", headers=auth_header(body["access_token"]))

    actions = session.exec(select(AuditEvent.action).where(AuditEvent.entity_id == body["user"]["id"])).all()
    assert "user.logged_out" in actions
