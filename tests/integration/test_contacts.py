"""Integration tests for /api/contacts routes."""

from datetime import date, timedelta

import pytest

from tests.conftest import auth_header

CONTACT = {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@example.com",
    "phone": "+380501112233",
    "birthday": "1990-05-20",
    "additional_info": "friend",
}


@pytest.fixture
async def contact(client, user_headers):
    resp = await client.post("/api/contacts/", json=CONTACT, headers=user_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_requires_auth(client):
    assert (await client.get("/api/contacts/")).status_code == 401
    bad = {"Authorization": "Bearer nope"}
    assert (await client.get("/api/contacts/", headers=bad)).status_code == 401


async def test_create_and_get(client, user_headers, contact):
    assert contact["first_name"] == "John" and contact["id"]
    resp = await client.get(f"/api/contacts/{contact['id']}", headers=user_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == CONTACT["email"]


async def test_create_duplicate(client, user_headers, contact):
    resp = await client.post(
        "/api/contacts/", json={**CONTACT, "phone": "+380509999999"}, headers=user_headers
    )
    assert resp.status_code == 409


async def test_create_validation(client, user_headers):
    resp = await client.post(
        "/api/contacts/", json={**CONTACT, "email": "bad"}, headers=user_headers
    )
    assert resp.status_code == 422


async def test_list_and_search(client, user_headers, contact):
    await client.post(
        "/api/contacts/",
        json={**CONTACT, "first_name": "Anna", "last_name": "Smith",
              "email": "anna@test.com", "phone": "+380502223344"},
        headers=user_headers,
    )
    all_ = (await client.get("/api/contacts/", headers=user_headers)).json()
    assert len(all_) == 2
    by_name = (await client.get("/api/contacts/?first_name=ann", headers=user_headers)).json()
    assert [c["first_name"] for c in by_name] == ["Anna"]
    by_last = (await client.get("/api/contacts/?last_name=DOE", headers=user_headers)).json()
    assert [c["first_name"] for c in by_last] == ["John"]
    by_email = (await client.get("/api/contacts/?email=test.com", headers=user_headers)).json()
    assert len(by_email) == 1
    page = (await client.get("/api/contacts/?skip=1&limit=1", headers=user_headers)).json()
    assert len(page) == 1


async def test_update(client, user_headers, contact):
    resp = await client.patch(
        f"/api/contacts/{contact['id']}",
        json={"first_name": "Johnny"},
        headers=user_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["first_name"] == "Johnny"
    assert resp.json()["last_name"] == "Doe"


async def test_update_not_found_and_duplicate(client, user_headers, contact):
    resp = await client.patch("/api/contacts/999", json={"first_name": "X"}, headers=user_headers)
    assert resp.status_code == 404
    other = (
        await client.post(
            "/api/contacts/",
            json={**CONTACT, "email": "other@example.com", "phone": "+380507777777"},
            headers=user_headers,
        )
    ).json()
    resp = await client.put(
        f"/api/contacts/{other['id']}", json={"email": CONTACT["email"]}, headers=user_headers
    )
    assert resp.status_code == 409


async def test_delete(client, user_headers, contact):
    resp = await client.delete(f"/api/contacts/{contact['id']}", headers=user_headers)
    assert resp.status_code == 200
    resp = await client.get(f"/api/contacts/{contact['id']}", headers=user_headers)
    assert resp.status_code == 404
    resp = await client.delete(f"/api/contacts/{contact['id']}", headers=user_headers)
    assert resp.status_code == 404


async def test_contacts_are_isolated_between_users(client, contact, make_user):
    other = await make_user(username="mallory")
    headers = auth_header(other)
    assert (await client.get(f"/api/contacts/{contact['id']}", headers=headers)).status_code == 404
    assert (await client.get("/api/contacts/", headers=headers)).json() == []
    # same email/phone is allowed in another user's address book
    resp = await client.post("/api/contacts/", json=CONTACT, headers=headers)
    assert resp.status_code == 201


async def test_birthdays(client, user_headers):
    today = date.today()
    soon = today + timedelta(days=3)
    later = today + timedelta(days=30)
    for i, bday in enumerate([soon, later]):
        await client.post(
            "/api/contacts/",
            json={**CONTACT, "email": f"b{i}@example.com", "phone": f"+38050000000{i}",
                  "birthday": bday.replace(year=1990 if not (bday.month == 2 and bday.day == 29) else 1992).isoformat()},
            headers=user_headers,
        )
    week = (await client.get("/api/contacts/birthdays", headers=user_headers)).json()
    assert [c["email"] for c in week] == ["b0@example.com"]
    month = (await client.get("/api/contacts/birthdays?days=31", headers=user_headers)).json()
    assert len(month) == 2
    assert (await client.get("/api/contacts/birthdays?days=0", headers=user_headers)).status_code == 422
