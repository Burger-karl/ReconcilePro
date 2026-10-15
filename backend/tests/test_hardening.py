"""Fixes from the backend security review (DECISIONS D-43 to D-45).

- Production refuses to start with the development JWT secret (anyone could forge login tokens).
- In production, an email that can't be sent is never written to the log (it may hold a reset link).
- Request bodies over the size limit are refused before they are read into memory or onto disk.
- The interactive API docs are switched off in production.
"""

import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import DEV_JWT_SECRET, Settings, settings
from app.core.limits import MAX_REQUEST_BYTES
from app.email import service as email_service
from app.main import create_app

STRONG_SECRET = "s" * 48


# --- settings -----------------------------------------------------------------------------------


def test_production_refuses_the_development_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(environment="production", jwt_secret=DEV_JWT_SECRET, _env_file=None)


def test_production_refuses_a_short_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(environment="production", jwt_secret="too-short", _env_file=None)


def test_production_starts_with_a_strong_secret() -> None:
    assert Settings(environment="production", jwt_secret=STRONG_SECRET, _env_file=None).environment == "production"


def test_development_allows_the_development_secret() -> None:
    assert Settings(environment="development", jwt_secret=DEV_JWT_SECRET, _env_file=None).jwt_secret == DEV_JWT_SECRET


def test_unknown_environment_is_refused() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="prod", jwt_secret=STRONG_SECRET, _env_file=None)


def test_environment_defaults_to_production() -> None:
    # Secure by default: forgetting to set ENVIRONMENT on a server can't switch the checks off.
    assert Settings.model_fields["environment"].default == "production"


# --- email ---------------------------------------------------------------------------------------


def test_unsent_email_body_is_logged_in_development(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(settings, "resend_api_key", "")
    monkeypatch.setattr(settings, "environment", "development")

    with caplog.at_level(logging.WARNING):
        email_service.send_email(to="ada@x.ng", subject="Reset", text="secret-link-123")

    assert "secret-link-123" in caplog.text


def test_unsent_email_body_is_never_logged_in_production(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(settings, "resend_api_key", "")
    monkeypatch.setattr(settings, "environment", "production")

    with caplog.at_level(logging.DEBUG):
        email_service.send_email(to="ada@x.ng", subject="Reset", text="secret-link-123")

    assert "secret-link-123" not in caplog.text
    assert "RESEND_API_KEY" in caplog.text


# --- request size --------------------------------------------------------------------------------


def test_request_with_large_content_length_is_413(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        content=b"x" * (MAX_REQUEST_BYTES + 1),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413


def test_chunked_request_over_the_limit_is_413(client: TestClient) -> None:
    # No Content-Length header: the size is only known by counting bytes as they arrive.
    def chunks():
        for _ in range(MAX_REQUEST_BYTES // 65_536 + 2):
            yield b"x" * 65_536

    response = client.post("/api/v1/webhooks/paystack", content=chunks(), headers={"x-paystack-signature": "x"})

    assert response.status_code == 413


def test_normal_requests_still_work(client: TestClient) -> None:
    assert client.get("/api/health").status_code == 200


# --- docs ------------------------------------------------------------------------------------------


def test_api_docs_are_off_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    with TestClient(create_app()) as production_client:
        assert production_client.get("/docs").status_code == 404
        assert production_client.get("/openapi.json").status_code == 404


def test_api_docs_are_on_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "environment", "development")
    with TestClient(create_app()) as development_client:
        assert development_client.get("/openapi.json").status_code == 200


# --- failed logins (D-42) --------------------------------------------------------------------------


def _login(client: TestClient, password: str) -> int:
    return client.post("/api/v1/auth/login", json={"email": "ada@adaezefoods.ng", "password": password}).status_code


def test_ten_wrong_passwords_block_that_email(client: TestClient, auth_headers: dict) -> None:
    for _ in range(10):
        assert _login(client, "wrong-guess-1") == 401

    # Blocked now, even with the right password, so guessing on gives an attacker nothing.
    assert _login(client, "correct-horse-1") == 429


def test_block_is_per_email(client: TestClient, auth_headers: dict, other_auth_headers: dict) -> None:
    for _ in range(10):
        _login(client, "wrong-guess-1")

    other = client.post("/api/v1/auth/login", json={"email": "kola@kolasons.ng", "password": "correct-horse-1"})
    assert other.status_code == 200


def test_successful_login_resets_the_count(client: TestClient, auth_headers: dict) -> None:
    for _ in range(9):
        _login(client, "wrong-guess-1")
    assert _login(client, "correct-horse-1") == 200

    for _ in range(9):
        _login(client, "wrong-guess-1")
    assert _login(client, "correct-horse-1") == 200


def test_block_ends_after_the_window(client: TestClient, auth_headers: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.limits import login_attempts

    clock = [1000.0]
    monkeypatch.setattr(login_attempts, "clock", lambda: clock[0])
    for _ in range(10):
        _login(client, "wrong-guess-1")
    assert _login(client, "correct-horse-1") == 429

    clock[0] += 15 * 60 + 1

    assert _login(client, "correct-horse-1") == 200


# --- failed logins per IP address (D-66) --------------------------------------------------------------


def test_thirty_failures_from_one_address_block_every_login_from_it(client: TestClient, auth_headers: dict) -> None:
    # Password spraying: one common password tried against many accounts. Each email stays under its own
    # limit of 10, so only a per-address count can stop it.
    for n in range(30):
        response = client.post("/api/v1/auth/login", json={"email": f"guess{n}@example.com", "password": "Password1"})
        assert response.status_code == 401

    # Blocked now, even for a real account with the right password.
    assert _login(client, "correct-horse-1") == 429


def test_a_successful_login_does_not_reset_the_address_count(client: TestClient, auth_headers: dict) -> None:
    # Otherwise an attacker with one real account could log into it every 29 guesses and spray forever.
    for n in range(29):
        client.post("/api/v1/auth/login", json={"email": f"guess{n}@example.com", "password": "Password1"})
    assert _login(client, "correct-horse-1") == 200

    _login(client, "wrong-guess-1")

    assert _login(client, "correct-horse-1") == 429


def test_address_block_ends_after_the_window(
    client: TestClient, auth_headers: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.limits import login_attempts, login_ip_attempts

    clock = [1000.0]
    monkeypatch.setattr(login_ip_attempts, "clock", lambda: clock[0])
    monkeypatch.setattr(login_attempts, "clock", lambda: clock[0])
    for n in range(30):
        client.post("/api/v1/auth/login", json={"email": f"guess{n}@example.com", "password": "Password1"})
    assert _login(client, "correct-horse-1") == 429

    clock[0] += 15 * 60 + 1

    assert _login(client, "correct-horse-1") == 200


# --- which address a request came from (D-66) ----------------------------------------------------------


def _request(peer: str, forwarded_for: str | None = None):
    from starlette.requests import Request

    headers = [(b"x-forwarded-for", forwarded_for.encode())] if forwarded_for else []
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


def test_without_a_proxy_the_peer_address_is_used_and_the_header_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.limits import client_ip

    monkeypatch.setattr(settings, "trusted_proxy_hops", 0)
    # Anyone can send X-Forwarded-For; with no proxy in front, believing it would let an attacker
    # pick a fresh address for every guess.
    assert client_ip(_request("203.0.113.9", "1.1.1.1")) == "203.0.113.9"


def test_behind_one_proxy_the_address_it_added_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.limits import client_ip

    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    # "1.1.1.1" was typed by the client (spoofed); the proxy appended the real address at the end.
    assert client_ip(_request("10.0.0.2", "1.1.1.1, 203.0.113.9")) == "203.0.113.9"


def test_behind_two_proxies_the_second_last_entry_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.limits import client_ip

    monkeypatch.setattr(settings, "trusted_proxy_hops", 2)
    assert client_ip(_request("10.0.0.2", "1.1.1.1, 203.0.113.9, 10.0.0.7")) == "203.0.113.9"


def test_a_missing_header_falls_back_to_the_peer_address(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.limits import client_ip

    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    assert client_ip(_request("10.0.0.2")) == "10.0.0.2"
