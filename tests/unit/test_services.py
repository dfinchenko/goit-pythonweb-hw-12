"""Unit tests for auth helpers, Redis cache, e-mail and upload services."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from redis.exceptions import ConnectionError as RedisConnectionError

from src.database.models import User, UserRole
from src.services import cache, email
from src.services.auth import (
    ACCESS,
    EMAIL_VERIFY,
    PASSWORD_RESET,
    REFRESH,
    Hash,
    create_access_token,
    create_email_token,
    create_refresh_token,
    create_reset_token,
    decode_token,
    get_current_admin,
    password_fingerprint,
)
from src.services.upload_file import UploadFileService


def make_user(**kw) -> User:
    data = dict(
        id=7,
        username="alice",
        email="alice@example.com",
        hashed_password=Hash.get_password_hash("secret123"),
        avatar=None,
        confirmed=True,
        role=UserRole.USER,
        created_at=datetime(2026, 1, 1, 12, 0),
    )
    data.update(kw)
    return User(**data)


def test_hash_roundtrip():
    hashed = Hash.get_password_hash("secret123")
    assert hashed != "secret123"
    assert Hash.verify_password("secret123", hashed)
    assert not Hash.verify_password("wrong", hashed)
    assert not Hash.verify_password("secret123", "not-a-bcrypt-hash")


@pytest.mark.parametrize(
    "factory, token_type",
    [
        (create_access_token, ACCESS),
        (create_refresh_token, REFRESH),
        (create_email_token, EMAIL_VERIFY),
    ],
)
def test_tokens_have_type(factory, token_type):
    payload = decode_token(factory("alice"), token_type)
    assert payload["sub"] == "alice"


def test_token_of_other_type_is_rejected():
    with pytest.raises(HTTPException) as exc:
        decode_token(create_refresh_token("alice"), ACCESS)
    assert exc.value.status_code == 401


def test_garbage_token_is_rejected():
    with pytest.raises(HTTPException):
        decode_token("not.a.jwt", ACCESS)


def test_reset_token_contains_password_fingerprint():
    user = make_user()
    payload = decode_token(create_reset_token(user), PASSWORD_RESET)
    assert payload["sub"] == user.email
    assert payload["pwd"] == password_fingerprint(user.hashed_password)


async def test_get_current_admin():
    admin = make_user(role=UserRole.ADMIN)
    assert await get_current_admin(admin) is admin
    with pytest.raises(HTTPException) as exc:
        await get_current_admin(make_user())
    assert exc.value.status_code == 403


async def test_cache_roundtrip(redis):
    user = make_user(avatar="http://a")
    assert await cache.get_cached_user("alice") is None
    await cache.cache_user(user)
    cached = await cache.get_cached_user("alice")
    assert (cached.id, cached.email, cached.role, cached.avatar) == (
        7,
        "alice@example.com",
        UserRole.USER,
        "http://a",
    )
    assert cached.hashed_password is None  # secrets are never cached
    assert 0 < await redis.ttl("user:alice") <= 900
    await cache.invalidate_user("alice")
    assert await cache.get_cached_user("alice") is None


async def test_cache_survives_redis_outage():
    broken = MagicMock()
    for name in ("get", "set", "delete"):
        setattr(broken, name, AsyncMock(side_effect=RedisConnectionError("down")))
    cache.set_redis(broken)
    try:
        assert await cache.get_cached_user("alice") is None
        await cache.cache_user(make_user())
        await cache.invalidate_user("alice")
    finally:
        cache.set_redis(None)


def test_get_redis_is_lazy_singleton():
    cache.set_redis(None)
    try:
        assert cache.get_redis() is cache.get_redis()
    finally:
        cache.set_redis(None)


async def test_send_emails_use_templates():
    with patch.object(email, "FastMail") as fm:
        fm.return_value.send_message = AsyncMock()
        await email.send_confirm_email("a@example.com", "alice", "http://h/")
        await email.send_reset_password_email("a@example.com", "alice", "http://h/", "t")
        templates = [c.kwargs["template_name"] for c in fm.return_value.send_message.call_args_list]
        assert templates == ["verify_email.html", "reset_password.html"]


async def test_send_email_connection_error_is_logged():
    from fastapi_mail.errors import ConnectionErrors

    with patch.object(email, "FastMail") as fm:
        fm.return_value.send_message = AsyncMock(side_effect=ConnectionErrors("x"))
        await email.send_confirm_email("a@example.com", "alice", "http://h/")


def test_upload_file_service():
    with patch("src.services.upload_file.cloudinary") as cld:
        cld.uploader.upload.return_value = {"version": 3}
        cld.CloudinaryImage.return_value.build_url.return_value = "http://img"
        service = UploadFileService("name", "key", "secret")
        file = MagicMock()
        assert service.upload_file(file, "alice") == "http://img"
        cld.uploader.upload.assert_called_once_with(
            file.file, public_id="ContactsApp/alice", overwrite=True
        )


async def test_session_manager_rolls_back_on_error():
    from sqlalchemy.exc import SQLAlchemyError

    from src.database.db import DatabaseSessionManager, get_db

    manager = DatabaseSessionManager("sqlite+aiosqlite:///:memory:")
    with pytest.raises(SQLAlchemyError):
        async with manager.session():
            raise SQLAlchemyError("boom")
    gen = get_db()
    assert await gen.__anext__() is not None
    await gen.aclose()
