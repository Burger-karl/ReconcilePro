"""Sign in with Google (DECISIONS D-37, D-38).

The browser gets a signed ID token from Google and posts it to us. These tests make their own RSA key
pair and sign tokens with it, then point app.auth.google at the matching public key instead of
Google's. So the real checks run (signature, audience, issuer, expiry, email_verified); only the
download of Google's public keys is replaced.
"""

import time
from collections.abc import Iterator

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.audit.models import AuditEvent
from app.auth import google
from app.auth.models import User, Workspace
from app.core.config import settings

CLIENT_ID = "test-client-id.apps.googleusercontent.com"
GOOGLE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
ATTACKER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)

REGISTER_URL = "/api/v1/auth/google/register"
LOGIN_URL = "/api/v1/auth/google/login"


@pytest.fixture(autouse=True)
def fake_google(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Configure a client id and make google.py trust GOOGLE_KEY's public half."""
    monkeypatch.setattr(settings, "google_client_id", CLIENT_ID)
    monkeypatch.setattr(google, "_google_public_key", lambda credential: GOOGLE_KEY.public_key())
    yield


def credential(key=GOOGLE_KEY, **overrides) -> str:
    """A Google-style ID token. Override any claim; pass a claim as None to leave it out."""
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "110169484474386276334",
        "email": "ada@gmail.com",
        "email_verified": True,
        "iat": now,
        "exp": now + 3600,
    }
    claims.update(overrides)
    claims = {name: value for name, value in claims.items() if value is not None}
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})


def google_register(client: TestClient, token: str, workspace_name: str = "Adaeze Foods"):
    return client.post(REGISTER_URL, json={"credential": token, "workspace_name": workspace_name})


def google_login(client: TestClient, token: str):
    return client.post(LOGIN_URL, json={"credential": token})


def register_with_password(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-1", "workspace_name": "Adaeze Foods"},
    )
    assert response.status_code == 201, response.text


# --- register ---------------------------------------------------------------------------------


def test_valid_google_credential_registers_workspace_and_owner(client: TestClient, session: Session) -> None:
    response = google_register(client, credential())

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["access_token"]
    assert body["user"]["email"] == "ada@gmail.com"
    assert body["user"]["role"] == "owner"

    user = session.exec(select(User).where(User.email == "ada@gmail.com")).one()
    assert user.google_sub == "110169484474386276334"
    assert user.password_hash is None
    assert session.get(Workspace, user.workspace_id).name == "Adaeze Foods"

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200


def test_google_register_twice_is_409_and_creates_no_extra_workspace(client: TestClient, session: Session) -> None:
    assert google_register(client, credential()).status_code == 201

    again = google_register(client, credential(), workspace_name="Second Try")

    assert again.status_code == 409
    assert session.exec(select(func.count()).select_from(Workspace)).one() == 1


def test_google_register_with_email_of_password_user_is_409(client: TestClient) -> None:
    register_with_password(client, "ada@gmail.com")

    response = google_register(client, credential())

    assert response.status_code == 409


def test_google_register_rejects_blank_workspace_name(client: TestClient) -> None:
    assert google_register(client, credential(), workspace_name="   ").status_code == 422


# --- login ------------------------------------------------------------------------------------


def test_google_login_returns_token_for_existing_google_user(client: TestClient) -> None:
    user_id = google_register(client, credential()).json()["user"]["id"]

    response = google_login(client, credential())

    assert response.status_code == 200, response.text
    assert response.json()["user"]["id"] == user_id


def test_google_login_finds_user_by_sub_even_if_their_google_email_changed(client: TestClient) -> None:
    user_id = google_register(client, credential()).json()["user"]["id"]

    response = google_login(client, credential(email="ada.new@gmail.com"))

    assert response.status_code == 200
    assert response.json()["user"]["id"] == user_id


def test_google_login_with_no_account_is_401(client: TestClient, session: Session) -> None:
    response = google_login(client, credential())

    assert response.status_code == 401
    assert session.exec(select(func.count()).select_from(User)).one() == 0


def test_google_login_links_password_user_with_same_gmail_address(client: TestClient, session: Session) -> None:
    register_with_password(client, "ada@gmail.com")

    response = google_login(client, credential())

    assert response.status_code == 200, response.text
    user = session.exec(select(User).where(User.email == "ada@gmail.com")).one()
    assert user.google_sub == "110169484474386276334"
    event = session.exec(select(AuditEvent).where(AuditEvent.action == "user.google_linked")).one()
    assert event.entity_id == user.id
    assert event.workspace_id == user.workspace_id


def test_linking_removes_the_unverified_password_and_logs_out_old_sessions(
    client: TestClient, session: Session
) -> None:
    # Found by the security review ("pre-account hijacking"): we never check that whoever registered
    # ada@gmail.com with a password owns that inbox. An attacker could register it first, wait for Ada to
    # sign in with Google (which would link), and keep logging in with their password to see her data.
    # Google has now proved who owns the address, so the old password and its sessions are thrown away.
    # The real Ada can set a password again through forgot password (the email goes to her inbox).
    attacker = client.post(
        "/api/v1/auth/register",
        json={"email": "ada@gmail.com", "password": "attacker-pass-1", "workspace_name": "Trap Ltd"},
    ).json()
    attacker_headers = {"Authorization": f"Bearer {attacker['access_token']}"}

    assert google_login(client, credential()).status_code == 200

    user = session.exec(select(User).where(User.email == "ada@gmail.com")).one()
    assert user.password_hash is None
    login = client.post("/api/v1/auth/login", json={"email": "ada@gmail.com", "password": "attacker-pass-1"})
    assert login.status_code == 401
    assert client.get("/api/v1/auth/me", headers=attacker_headers).status_code == 401


def test_google_login_links_workspace_account_when_google_is_authoritative(client: TestClient, session: Session) -> None:
    # "hd" (hosted domain) means a Google Workspace account: the company's Google admin owns the address.
    register_with_password(client, "ada@adaezefoods.ng")

    response = google_login(client, credential(email="ada@adaezefoods.ng", hd="adaezefoods.ng"))

    assert response.status_code == 200
    assert session.exec(select(User)).one().google_sub == "110169484474386276334"


def test_google_login_does_not_link_when_google_is_not_authoritative_for_the_email(
    client: TestClient, session: Session
) -> None:
    # A personal Google account can carry any verified address, e.g. ada@adaezefoods.ng, without
    # Google owning that domain. Google's docs say not to treat that as proof for account linking.
    register_with_password(client, "ada@adaezefoods.ng")

    response = google_login(client, credential(email="ada@adaezefoods.ng"))

    assert response.status_code == 401
    assert session.exec(select(User)).one().google_sub is None


def test_google_login_does_not_relink_an_account_already_linked_to_another_google_user(
    client: TestClient, session: Session
) -> None:
    google_register(client, credential())

    response = google_login(client, credential(sub="999999999999999999999"))

    assert response.status_code == 401
    assert session.exec(select(User)).one().google_sub == "110169484474386276334"


# --- token checks: each one stops a different attack ------------------------------------------


@pytest.mark.parametrize(
    "bad_token",
    [
        pytest.param(lambda: credential(email_verified=False), id="unverified-email"),
        pytest.param(lambda: credential(email_verified=None), id="email-verified-missing"),
        pytest.param(lambda: credential(email_verified="true"), id="email-verified-as-string"),
        pytest.param(lambda: credential(aud="another-app.apps.googleusercontent.com"), id="wrong-audience"),
        pytest.param(lambda: credential(iss="https://evil.example.com"), id="wrong-issuer"),
        pytest.param(lambda: credential(iss="accounts.google.co"), id="issuer-substring"),
        pytest.param(lambda: credential(exp=int(time.time()) - 60), id="expired"),
        pytest.param(lambda: credential(exp=None), id="no-expiry"),
        pytest.param(lambda: credential(sub=None), id="no-sub"),
        pytest.param(lambda: credential(email=None), id="no-email"),
        pytest.param(lambda: credential(key=ATTACKER_KEY), id="signed-by-unknown-key"),
        pytest.param(lambda: "not-a-jwt", id="garbage"),
    ],
)
def test_bad_google_credentials_are_rejected(client: TestClient, session: Session, bad_token) -> None:
    token = bad_token()

    assert google_register(client, token).status_code == 401
    assert google_login(client, token).status_code == 401
    assert session.exec(select(func.count()).select_from(User)).one() == 0


def test_hs256_token_signed_with_googles_public_key_is_rejected(client: TestClient) -> None:
    # Classic algorithm-confusion attack: sign with HS256 using the PUBLIC key as the HMAC secret.
    # Only RS256 is accepted, so this never verifies.
    now = int(time.time())
    forged = jwt.encode(
        {"iss": "accounts.google.com", "aud": CLIENT_ID, "sub": "1", "email": "x@gmail.com",
         "email_verified": True, "iat": now, "exp": now + 3600},
        "attacker-chosen-hmac-secret-that-is-long-enough",
        algorithm="HS256",
    )

    assert google_login(client, forged).status_code == 401


def test_google_routes_503_when_client_id_not_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "google_client_id", "")

    assert google_register(client, credential()).status_code == 503
    assert google_login(client, credential()).status_code == 503


def test_google_keys_unreachable_is_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def unreachable(credential: str):
        raise google.GoogleUnavailable

    monkeypatch.setattr(google, "_google_public_key", unreachable)

    assert google_login(client, credential()).status_code == 503


# --- password login for Google-only users -----------------------------------------------------


def test_password_login_for_google_only_user_is_401_with_the_usual_message(client: TestClient) -> None:
    google_register(client, credential())

    response = client.post("/api/v1/auth/login", json={"email": "ada@gmail.com", "password": "anything-at-all"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"
