"""Shared test fixtures.

Integration tests run the real FastAPI app against an in-memory SQLite
database and an in-memory fake Redis (``fakeredis``); e-mail sending and
Cloudinary are mocked.
"""

import os

os.environ.setdefault("DB_URL", "sqlite+aiosqlite:///:memory:")
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ.setdefault("JWT_SECRET", "test-secret-key-that-is-long-enough-123")

from unittest.mock import AsyncMock  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from fakeredis import FakeAsyncRedis  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from main import app  # noqa: E402
from src.database.db import get_db  # noqa: E402
from src.database.models import Base, User, UserRole  # noqa: E402
from src.services import cache  # noqa: E402
from src.services.auth import Hash, create_access_token  # noqa: E402

PASSWORD = "secret123"


@pytest_asyncio.fixture
async def session_maker():
    """Fresh in-memory database for every test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(session_maker):
    """A session for preparing / checking data directly in tests."""
    async with session_maker() as session:
        yield session


@pytest_asyncio.fixture
async def redis():
    """In-memory Redis used by the cache module."""
    client = FakeAsyncRedis(decode_responses=True)
    cache.set_redis(client)
    yield client
    cache.set_redis(None)
    await client.aclose()


@pytest.fixture
def mail_mock(monkeypatch):
    """Replace e-mail sending with mocks and return them."""
    confirm, reset = AsyncMock(), AsyncMock()
    monkeypatch.setattr("src.api.auth.send_confirm_email", confirm)
    monkeypatch.setattr("src.api.auth.send_reset_password_email", reset)
    return {"confirm": confirm, "reset": reset}


@pytest_asyncio.fixture
async def client(session_maker, redis, mail_mock):
    """HTTP client for the app wired to the test database and fake Redis."""

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def make_user(db_session):
    """Factory that inserts a user straight into the database."""

    async def _make(
        username="alice",
        email=None,
        role=UserRole.USER,
        confirmed=True,
        password=PASSWORD,
    ) -> User:
        user = User(
            username=username,
            email=email or f"{username}@example.com",
            hashed_password=Hash.get_password_hash(password),
            role=role,
            confirmed=confirmed,
            avatar="https://www.gravatar.com/avatar/x",
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    return _make


@pytest_asyncio.fixture
async def user(make_user):
    """A confirmed regular user."""
    return await make_user()


@pytest_asyncio.fixture
async def admin(make_user):
    """A confirmed admin."""
    return await make_user(username="admin", role=UserRole.ADMIN)


def auth_header(user: User) -> dict:
    """Authorization header with a fresh access token for ``user``."""
    return {"Authorization": f"Bearer {create_access_token(user.username)}"}


@pytest.fixture
def user_headers(user):
    return auth_header(user)


@pytest.fixture
def admin_headers(admin):
    return auth_header(admin)
