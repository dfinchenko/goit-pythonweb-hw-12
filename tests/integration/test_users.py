"""Integration tests for /api/users routes, roles and user caching."""

from unittest.mock import patch

from src.database.models import UserRole
from src.services import cache


async def test_me(client, user, user_headers):
    resp = await client.get("/api/users/me", headers=user_headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == user.username
    assert resp.json()["role"] == "user"


async def test_me_unauthorized(client):
    assert (await client.get("/api/users/me")).status_code == 401


async def test_me_unknown_user(client, make_user):
    from src.services.auth import create_access_token

    headers = {"Authorization": f"Bearer {create_access_token('ghost')}"}
    assert (await client.get("/api/users/me", headers=headers)).status_code == 401


async def test_current_user_is_served_from_cache(client, user, user_headers, redis):
    assert await redis.get(f"user:{user.username}") is None
    await client.get("/api/users/me", headers=user_headers)  # miss -> DB -> cache
    assert await redis.get(f"user:{user.username}") is not None

    with patch(
        "src.services.auth.UserRepository.get_user_by_username"
    ) as db_lookup:
        resp = await client.get("/api/users/me", headers=user_headers)
    assert resp.status_code == 200
    db_lookup.assert_not_called()  # second request did not hit the database


async def test_avatar_forbidden_for_regular_user(client, user_headers):
    resp = await client.patch(
        "/api/users/avatar",
        files={"file": ("a.png", b"img", "image/png")},
        headers=user_headers,
    )
    assert resp.status_code == 403


async def test_avatar_admin_can_update_and_cache_is_invalidated(
    client, admin, admin_headers, redis
):
    await client.get("/api/users/me", headers=admin_headers)
    assert await redis.get(f"user:{admin.username}")
    with patch(
        "src.api.users.UploadFileService.upload_file", return_value="http://cdn/new.png"
    ):
        resp = await client.patch(
            "/api/users/avatar",
            files={"file": ("a.png", b"img", "image/png")},
            headers=admin_headers,
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["avatar"] == "http://cdn/new.png"
    assert await redis.get(f"user:{admin.username}") is None
    me = await client.get("/api/users/me", headers=admin_headers)
    assert me.json()["avatar"] == "http://cdn/new.png"


async def test_change_role(client, user, admin_headers, user_headers):
    resp = await client.patch(
        f"/api/users/{user.id}/role", json={"role": "admin"}, headers=user_headers
    )
    assert resp.status_code == 403
    resp = await client.patch(
        f"/api/users/{user.id}/role", json={"role": "admin"}, headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"
    me = await client.get("/api/users/me", headers=user_headers)
    assert me.json()["role"] == "admin"


async def test_change_role_errors(client, admin, admin_headers):
    resp = await client.patch(
        "/api/users/999/role", json={"role": "admin"}, headers=admin_headers
    )
    assert resp.status_code == 404
    resp = await client.patch(
        f"/api/users/{admin.id}/role", json={"role": "user"}, headers=admin_headers
    )
    assert resp.status_code == 400


async def test_create_admin_cli(db_session, user):
    from src.create_admin import create_admin

    assert await create_admin(user.username, user.email, "x" * 8, db_session) == "promoted"
    assert user.role == UserRole.ADMIN
    assert await create_admin("root", "root@example.com", "secret123", db_session) == "created"
