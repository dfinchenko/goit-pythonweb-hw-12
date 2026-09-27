"""Integration tests for /api/auth routes."""

from sqlalchemy import select

from src.database.models import User, UserRole
from src.services.auth import (
    create_access_token,
    create_email_token,
    create_refresh_token,
    create_reset_token,
)
from tests.conftest import PASSWORD

NEW_USER = {"username": "bob", "email": "bob@example.com", "password": "secret123"}


async def login(client, username, password=PASSWORD):
    return await client.post(
        "/api/auth/login", data={"username": username, "password": password}
    )


async def test_register(client, mail_mock, db_session):
    resp = await client.post("/api/auth/register", json=NEW_USER)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["username"] == "bob"
    assert data["role"] == "user"
    assert data["confirmed"] is False
    assert "password" not in data and "hashed_password" not in data
    mail_mock["confirm"].assert_awaited_once()


async def test_register_ignores_role_escalation(client):
    resp = await client.post("/api/auth/register", json={**NEW_USER, "role": "admin"})
    assert resp.json()["role"] == "user"


async def test_register_conflicts(client, user):
    resp = await client.post(
        "/api/auth/register", json={**NEW_USER, "email": user.email}
    )
    assert resp.status_code == 409
    resp = await client.post(
        "/api/auth/register", json={**NEW_USER, "username": user.username}
    )
    assert resp.status_code == 409


async def test_register_validation(client):
    resp = await client.post(
        "/api/auth/register", json={**NEW_USER, "password": "123"}
    )
    assert resp.status_code == 422


async def test_login_success_returns_token_pair(client, user):
    resp = await login(client, user.username)
    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"] and data["refresh_token"]


async def test_login_wrong_password(client, user):
    assert (await login(client, user.username, "wrong-pass")).status_code == 401
    assert (await login(client, "nobody")).status_code == 401


async def test_login_unconfirmed(client, make_user):
    u = await make_user(username="carol", confirmed=False)
    resp = await login(client, u.username)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Email not confirmed"


async def test_refresh_rotates_tokens(client, user):
    tokens = (await login(client, user.username)).json()
    resp = await client.post(
        "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert resp.status_code == 200
    new_tokens = resp.json()
    # old refresh token is revoked after rotation
    resp = await client.post(
        "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert new_tokens["refresh_token"] != tokens["refresh_token"]
    assert resp.status_code == 401
    me = await client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
    )
    assert me.status_code == 200


async def test_refresh_rejects_access_token_and_unknown(client, user):
    resp = await client.post(
        "/api/auth/refresh", json={"refresh_token": create_access_token(user.username)}
    )
    assert resp.status_code == 401
    resp = await client.post(
        "/api/auth/refresh", json={"refresh_token": create_refresh_token(user.username)}
    )
    assert resp.status_code == 401  # not the stored token


async def test_logout_revokes_refresh_token(client, user):
    tokens = (await login(client, user.username)).json()
    body = {"refresh_token": tokens["refresh_token"]}
    assert (await client.post("/api/auth/logout", json=body)).status_code == 200
    assert (await client.post("/api/auth/refresh", json=body)).status_code == 401


async def test_confirm_email(client, make_user, db_session):
    u = await make_user(username="dave", confirmed=False)
    token = create_email_token(u.email)
    resp = await client.get(f"/api/auth/confirmed_email/{token}")
    assert resp.json()["message"] == "Email confirmed"
    resp = await client.get(f"/api/auth/confirmed_email/{token}")
    assert resp.json()["message"] == "Email already confirmed"


async def test_confirm_email_errors(client):
    assert (await client.get("/api/auth/confirmed_email/bad")).status_code == 401
    token = create_email_token("ghost@example.com")
    assert (await client.get(f"/api/auth/confirmed_email/{token}")).status_code == 400


async def test_request_email(client, make_user, mail_mock, user):
    u = await make_user(username="erin", confirmed=False)
    resp = await client.post("/api/auth/request_email", json={"email": u.email})
    assert resp.json()["message"] == "Check your email for confirmation"
    mail_mock["confirm"].assert_awaited_once()
    resp = await client.post("/api/auth/request_email", json={"email": user.email})
    assert resp.json()["message"] == "Email already confirmed"


async def test_forgot_password_does_not_leak_emails(client, user, mail_mock):
    r1 = await client.post("/api/auth/forgot_password", json={"email": user.email})
    r2 = await client.post(
        "/api/auth/forgot_password", json={"email": "ghost@example.com"}
    )
    assert r1.status_code == r2.status_code == 200
    assert r1.json() == r2.json()
    mail_mock["reset"].assert_awaited_once()


async def test_reset_password_flow(client, user, db_session):
    token = create_reset_token(user)

    form = await client.get(f"/api/auth/reset_password/{token}")
    assert form.status_code == 200 and "new_password" in form.text

    resp = await client.post(
        "/api/auth/reset_password", json={"token": token, "new_password": "brandnew1"}
    )
    assert resp.status_code == 200
    assert (await login(client, user.username, "brandnew1")).status_code == 200
    assert (await login(client, user.username)).status_code == 401

    # the same token cannot be used twice
    resp = await client.post(
        "/api/auth/reset_password", json={"token": token, "new_password": "another1"}
    )
    assert resp.status_code == 400


async def test_reset_password_invalid_token(client, user):
    resp = await client.post(
        "/api/auth/reset_password",
        json={"token": create_access_token(user.username), "new_password": "brandnew1"},
    )
    assert resp.status_code == 400
    assert (await client.get("/api/auth/reset_password/garbage")).status_code == 401


async def test_reset_password_unknown_user(client):
    ghost = User(email="ghost@example.com", hashed_password="x")
    resp = await client.post(
        "/api/auth/reset_password",
        json={"token": create_reset_token(ghost), "new_password": "brandnew1"},
    )
    assert resp.status_code == 400
