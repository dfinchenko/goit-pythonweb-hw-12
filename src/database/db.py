"""Async database engine and session management."""

import contextlib
from typing import AsyncIterator

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.conf.config import settings


class DatabaseSessionManager:
    """Owns the async engine and produces database sessions.

    Args:
        url: SQLAlchemy async database URL.
    """

    def __init__(self, url: str):
        self._engine: AsyncEngine = create_async_engine(url)
        self._session_maker = async_sessionmaker(
            autoflush=False, expire_on_commit=False, bind=self._engine
        )

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield a session and roll it back if a database error occurs.

        Yields:
            AsyncSession: an open database session.

        Raises:
            SQLAlchemyError: re-raised after the rollback.
        """
        session = self._session_maker()
        try:
            yield session
        except SQLAlchemyError:
            await session.rollback()
            raise
        finally:
            await session.close()


sessionmanager = DatabaseSessionManager(settings.DB_URL)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that provides a database session per request.

    Yields:
        AsyncSession: an open database session.
    """
    async with sessionmanager.session() as session:
        yield session
