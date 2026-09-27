"""Business logic for users."""

import logging

from libgravatar import Gravatar
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User, UserRole
from src.repository.users import UserRepository
from src.schemas import UserCreate
from src.services.auth import Hash
from src.services.cache import invalidate_user

logger = logging.getLogger(__name__)


class UserService:
    """User operations. Every change of a user invalidates its cache entry.

    Args:
        db: An open async database session.
    """

    def __init__(self, db: AsyncSession):
        self.repository = UserRepository(db)

    async def create_user(self, body: UserCreate) -> User:
        """Register a user with a hashed password and a Gravatar avatar.

        The role is always ``user`` — admins are created with
        ``python -m src.create_admin`` or promoted by another admin.
        """
        avatar = None
        try:
            avatar = Gravatar(body.email).get_image()
        except Exception as exc:  # pragma: no cover - libgravatar never fails in practice
            logger.warning("Gravatar error: %s", exc)
        return await self.repository.create_user(
            body, Hash.get_password_hash(body.password), avatar
        )

    async def get_user_by_id(self, user_id: int) -> User | None:
        """Return a user by id."""
        return await self.repository.get_user_by_id(user_id)

    async def get_user_by_username(self, username: str) -> User | None:
        """Return a user by username."""
        return await self.repository.get_user_by_username(username)

    async def get_user_by_email(self, email: str) -> User | None:
        """Return a user by e-mail."""
        return await self.repository.get_user_by_email(email)

    async def confirm_email(self, user: User) -> User:
        """Confirm the user's e-mail."""
        user = await self.repository.confirm_email(user)
        await invalidate_user(user.username)
        return user

    async def update_avatar(self, user_id: int, url: str) -> User:
        """Set a new avatar URL."""
        user = await self.repository.get_user_by_id(user_id)
        user = await self.repository.update_avatar(user, url)
        await invalidate_user(user.username)
        return user

    async def reset_password(self, user: User, new_password: str) -> User:
        """Set a new password and log the user out of all sessions."""
        user = await self.repository.update_password(
            user, Hash.get_password_hash(new_password)
        )
        await invalidate_user(user.username)
        return user

    async def set_refresh_token(self, user: User, token: str | None) -> User:
        """Store the current refresh token (``None`` logs the user out)."""
        return await self.repository.update_refresh_token(user, token)

    async def change_role(self, user: User, role: UserRole) -> User:
        """Change the user's role."""
        user = await self.repository.update_role(user, role)
        await invalidate_user(user.username)
        return user
