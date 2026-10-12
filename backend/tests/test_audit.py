"""GET /api/v1/audit: the workspace's audit trail, newest first (invariant 7, DECISIONS D-49)."""

import pytest
from fastapi.testclient import TestClient

AUDIT = "/api/v1/audit"


def new_customer(client: TestClient, headers: dict, name: str) -> dict:
    response = client.post("/api/v1/customers", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def events(client: TestClient, headers: dict, query: str = "") -> dict:
    response = client.get(f"{AUDIT}{query}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_lists_events_newest_first_with_who_did_it(client: TestClient, auth_headers: dict) -> None:
    first = new_customer(client, auth_headers, "Kola & Sons")
    client.patch(f"/api/v1/customers/{first['id']}", json={"phone": "08030000000"}, headers=auth_headers)

    body = events(client, auth_headers)

    actions = [item["action"] for item in body["items"]]
    assert actions[:2] == ["customer.updated", "customer.created"]
    assert body["total"] == len(body["items"])
    newest = body["items"][0]
    assert newest["entity_type"] == "customer"
    assert newest["entity_id"] == first["id"]
    assert newest["actor_email"] == "ada@adaezefoods.ng"
    assert set(newest) == {"id", "action", "entity_type", "entity_id", "actor_user_id", "actor_email", "data", "created_at"}


def test_filters_by_entity(client: TestClient, auth_headers: dict) -> None:
    kola = new_customer(client, auth_headers, "Kola & Sons")
    new_customer(client, auth_headers, "Bisi Stores")

    body = events(client, auth_headers, f"?entity_type=customer&entity_id={kola['id']}")

    assert body["total"] == 1
    assert body["items"][0]["entity_id"] == kola["id"]


def test_pages_with_limit_and_offset(client: TestClient, auth_headers: dict) -> None:
    for number in range(5):
        new_customer(client, auth_headers, f"Customer {number}")

    first_page = events(client, auth_headers, "?entity_type=customer&limit=2")
    second_page = events(client, auth_headers, "?entity_type=customer&limit=2&offset=2")

    assert first_page["total"] == second_page["total"] == 5
    assert len(first_page["items"]) == len(second_page["items"]) == 2
    assert {item["id"] for item in first_page["items"]}.isdisjoint(item["id"] for item in second_page["items"])


@pytest.mark.parametrize("query", ["?limit=0", "?limit=201", "?offset=-1", "?entity_id=not-a-uuid"])
def test_rejects_bad_paging_and_ids(client: TestClient, auth_headers: dict, query: str) -> None:
    assert client.get(f"{AUDIT}{query}", headers=auth_headers).status_code == 422


def test_only_shows_the_callers_workspace(client: TestClient, auth_headers: dict, other_auth_headers: dict) -> None:
    theirs = new_customer(client, other_auth_headers, "Their Customer")

    mine = events(client, auth_headers)
    by_their_id = events(client, auth_headers, f"?entity_id={theirs['id']}")

    assert theirs["id"] not in {item["entity_id"] for item in mine["items"]}
    assert by_their_id == {"items": [], "total": 0}


def test_audit_needs_login(client: TestClient) -> None:
    assert client.get(AUDIT).status_code == 401
