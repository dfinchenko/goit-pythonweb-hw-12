"""Unit tests for UserRepository (database session is mocked)."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User, UserRole
from src.repository.users import UserRepository
from src.schemas import UserCreate


@pytest.fixture
def session():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def repo(session):
    return UserRepository(session)


@pytest.fixture
def user():
    return User(
        id=1,
        username="alice",
        email="alice@example.com",
        hashed_password="hash",
        confirmed=False,
        role=UserRole.USER,
    )


def returns(session, value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    session.execute.return_value = result


@pytest.mark.parametrize(
    "method, arg",
    [
        ("get_user_by_id", 1),
        ("get_user_by_username", "alice"),
        ("get_user_by_email", "alice@example.com"),
    ],
)
async def test_getters(repo, session, user, method, arg):
    returns(session, user)
    assert await getattr(repo, method)(arg) is user
    session.execute.assert_awaited_once()


async def test_getter_not_found(repo, session):
    returns(session, None)
    assert await repo.get_user_by_username("ghost") is None


async def test_create_user_defaults_to_user_role(repo, session):
    body = UserCreate(username="bob", email="bob@example.com", password="secret1")
    user = await repo.create_user(body, "hashed", avatar="http://avatar")
    assert user.username == "bob"
    assert user.hashed_password == "hashed"
    assert user.avatar == "http://avatar"
    assert user.role == UserRole.USER
    session.add.assert_called_once_with(user)
    session.commit.assert_awaited_once()


async def test_create_admin(repo, session):
    body = UserCreate(username="root", email="root@example.com", password="secret1")
    user = await repo.create_user(body, "hashed", role=UserRole.ADMIN)
    assert user.role == UserRole.ADMIN


async def test_confirm_email(repo, session, user):
    assert (await repo.confirm_email(user)).confirmed is True
    session.commit.assert_awaited_once()


async def test_update_avatar(repo, session, user):
    assert (await repo.update_avatar(user, "http://new")).avatar == "http://new"


async def test_update_password_revokes_refresh_token(repo, session, user):
    user.refresh_token = "old"
    updated = await repo.update_password(user, "new-hash")
    assert updated.hashed_password == "new-hash"
    assert updated.refresh_token is None


async def test_update_refresh_token(repo, session, user):
    assert (await repo.update_refresh_token(user, "tok")).refresh_token == "tok"


async def test_update_role(repo, session, user):
    assert (await repo.update_role(user, UserRole.ADMIN)).role == UserRole.ADMIN
